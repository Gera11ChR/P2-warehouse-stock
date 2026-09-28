from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
