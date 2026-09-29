from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    almacen_id: int
    nombre: str
    tipo: str
    is_active: bool


class SeccionTransferibleOut(BaseModel):
    """Sección válida como origen/destino de movimientos TEAMS/DEVOL
    (0014): GENERAL activas + manejadores de ruteo FO_PAQUETE/FO_EN_USO
    (transferibles aunque is_active=False)."""

    almacen_id: int
    nombre: str
    tipo: Literal["GENERAL", "FO_PAQUETE", "FO_EN_USO"]
    transferible: bool = True


class SeccionStockOut(BaseModel):
    """Fila de stock de una sección (JOIN catálogo, solo lectura)."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool


class InventarioEquipoOut(BaseModel):
    """Fila del inventario autónomo del equipo (REQ-DOMAIN-001/002).

    Reemplaza a `CatalogoEquipoOut` y a la vista sparse deprecada
    `vw_inventario_equipo_completo`: solo filas físicas de
    `inventario_equipos` con stock real originado en movimientos TEAMS/DEVOL
    auditados. Cero fantasmas: no se renderizan filas de stock 0 ni
    materiales inactivos. `ultimo_movimiento_id` traza cada fila a su
    movimiento de origen. Se construye con query directa
    (from_attributes=False); la métrica la gobierna `u_m`."""

    equipo_id: int
    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool
    ultimo_movimiento_id: int | None
    # Configuración operativa LOCAL del equipo (0014) y sus valores
    # EFECTIVOS (COALESCE local → maestro). Sin configuración local, los
    # efectivos replican exactamente el comportamiento previo.
    stock_minimo_local: int | None = None
    categoria_local_id: int | None = None
    um_local_id: int | None = None
    stock_minimo_efectivo: int | None = None
    categoria_efectiva: str | None = None
    um_efectivo: str | None = None


# ── Fibra Óptica: inventarios independientes con esquema estándar ──────
# (REQ-DOMAIN-003/004/005: PAQUETE y EN_USO dejan de ser secciones del
# Inventario General; la métrica se determina exclusivamente vía U.M.)

FibraModulo = Literal["PAQUETE", "EN_USO"]


class FibraStockOut(BaseModel):
    """Fila de stock de un inventario FO (PAQUETE o EN_USO) con el esquema
    estándar: CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO,
    ALERTA STOCK. Reemplaza el legado "carretes en stock / metros
    disponibles" (fiber_variants deprecado, REQ-DOMAIN-006)."""

    modulo: FibraModulo
    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool


class FibraCargaInicialRequest(BaseModel):
    """Carga inicial de stock en un inventario FO, delegada a la función de
    carga inicial (idempotente). El alta inicial admite `motivo` opcional."""

    model_config = ConfigDict(extra="forbid")

    modulo: FibraModulo
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    cantidad: int = Field(ge=0)
    motivo: str | None = Field(default=None, max_length=500)


class FibraAjusteRequest(BaseModel):
    """Ajuste administrativo de stock FO con `motivo` obligatorio y no vacío
    (Constitution 2.4: ledger inmutable; toda corrección queda auditada)."""

    model_config = ConfigDict(extra="forbid")

    modulo: FibraModulo
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    nuevo_stock: int = Field(ge=0)
    motivo: str = Field(min_length=1, max_length=500)


class FibraOperacionOut(BaseModel):
    """Eco mínimo del alcance operado por una operación de inventario FO
    (carga inicial o ajuste administrativo), siguiendo el patrón de
    `AjusteOut`."""

    modulo: FibraModulo
    material_id: int


class FibraMaterialUpdateRequest(BaseModel):
    """Edición de material desde una sección FO (REQ-CATFO-001/002,
    REQ-STOCK-001/002/003).

    Espejo de `MaterialUpdate` (schemas/material.py) adaptado a Fibra
    Óptica: sin `is_active` y sin el campo legacy `tipo`. El stock NO se
    actualiza por ORM: si `stock_actual` viene en el payload, el servicio
    enruta el ajuste a `fn_ajustar_stock_fibra` con `motivo` obligatorio y
    no vacío (el diferencial, el bloqueo FOR UPDATE y la auditoría
    'AJUSTE_INVENTARIO_FO' viven en PostgreSQL — Constitution 2.4, jamás
    UPDATE directo de stock). Selector dual de categorías: `categoria_id`
    (rama A) o `nueva_categoria` (rama B), mutuamente excluyentes."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = None
    nueva_categoria: str | None = Field(default=None, max_length=100)
    u_m: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    stock_actual: int | None = Field(default=None, ge=0)
    motivo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_categoria_dual(self) -> "FibraMaterialUpdateRequest":
        if self.categoria_id is not None and self.nueva_categoria:
            raise ValueError(
                "Use solo una rama del selector dual: categoria_id o nueva_categoria."
            )
        return self

    @model_validator(mode="after")
    def _check_stock_motivo(self) -> "FibraMaterialUpdateRequest":
        """REQ-STOCK-001: si se envía `stock_actual`, el `motivo` es
        obligatorio y no vacío; todo ajuste de stock debe quedar trazado en
        el ledger de Auditoría (espejo de `_check_stock_motivo` de
        MaterialUpdate)."""
        if self.stock_actual is not None:
            if self.motivo is None or not self.motivo.strip():
                raise ValueError(
                    "motivo es obligatorio y no puede estar vacío cuando se "
                    "modifica stock_actual: todo ajuste de stock debe quedar "
                    "trazado en el ledger de Auditoría."
                )
        return self


class FibraMaterialOut(BaseModel):
    """Material materializado de un inventario FO tras PATCH (join catálogo
    maestro + `inventario_fibra`): esquema estándar + categoría. Se
    construye con query directa (from_attributes=False); `alerta_stock`
    respeta la misma semántica de `FibraStockOut`."""

    modulo: FibraModulo
    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool
    categoria: str | None
    categoria_id: int | None
