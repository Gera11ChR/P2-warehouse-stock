from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from app.schemas._tipos import CantidadDecimal

# Valor Total (RF-4): Decimal sin cota de dígitos (E9: una suma de productos
# puede exceder 12 dígitos sin truncarse), serializado como número JSON con
# el mismo patrón que las cantidades (pérdida de sub-unidad por encima de
# ≈9×10¹² MXN aceptada y documentada en plan §2.1, R6).
ValorTotalJson = Annotated[
    Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")
]


class SeccionOut(BaseModel):
    """Sección del maestro. `tipo` es `str` (no Literal): los tipos legacy
    `FO_PAQUETE`/`FO_EN_USO` son valores HISTÓRICOS del ledger y siguen
    apareciendo en datos previos a la migración 0027 (RF-9)."""

    model_config = ConfigDict(from_attributes=True)

    almacen_id: int
    nombre: str
    tipo: str
    is_active: bool


class SeccionTransferibleOut(BaseModel):
    """Sección válida como origen/destino de movimientos TEAMS/DEVOL (RF-9):
    GENERAL activas + la sección única de ruteo FO (transferible aunque
    is_active=False). Las secciones legacy FO_PAQUETE/FO_EN_USO NO se
    emiten (no son seleccionables en el dominio vivo)."""

    almacen_id: int
    nombre: str
    tipo: Literal["GENERAL", "FO"]
    transferible: bool = True


class SeccionStockOut(BaseModel):
    """Fila de stock de una sección (JOIN catálogo, solo lectura).
    `valor_unitario` proviene del catálogo maestro por JOIN (RF-3)."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: CantidadDecimal
    valor_unitario: CantidadDecimal
    alerta_stock: bool


class InventarioEquipoOut(BaseModel):
    """Fila del inventario autónomo del equipo (REQ-DOMAIN-001/002).

    Reemplaza a `CatalogoEquipoOut` y a la vista sparse deprecada
    `vw_inventario_equipo_completo`: solo filas físicas de
    `inventario_equipos` con stock real originado en movimientos TEAMS/DEVOL
    auditados. Cero fantasmas: no se renderizan filas de stock 0 ni
    materiales inactivos. `ultimo_movimiento_id` traza cada fila a su
    movimiento de origen. Se construye con query directa
    (from_attributes=False); la métrica la gobierna `u_m`.
    `valor_unitario` proviene del catálogo maestro (solo lectura en
    Unidades, RF-3/C-2)."""

    equipo_id: int
    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: CantidadDecimal
    valor_unitario: CantidadDecimal
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


# ── Inventario FO unificado (RF-1, migración 0027) ────────────────────────
# Una sola locación "Inventario FO" por material (sin `modulo`). Los tipos
# `FibraModulo`/`ModuloFo` quedaron ELIMINADOS del contrato; los valores
# `PAQUETE`/`EN_USO` solo sobreviven como datos históricos del ledger.


class FibraStockOut(BaseModel):
    """Fila de stock del Inventario FO unificado (RF-1) con el esquema
    estándar: CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO,
    ALERTA STOCK y VALOR UNITARIO (JOIN al catálogo maestro, RF-3).
    Reemplaza el legado "carretes en stock / metros disponibles"
    (fiber_variants deprecado, REQ-DOMAIN-006)."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: CantidadDecimal
    valor_unitario: CantidadDecimal
    alerta_stock: bool


class FibraCargaInicialRequest(BaseModel):
    """Carga inicial de stock en el Inventario FO unificado, delegada a
    `fn_cargar_stock_inicial_fibra` (idempotente por material). El alta
    inicial admite `motivo` opcional. Sin `modulo`: enviarlo → 422
    (`extra="forbid"`, RF-1)."""

    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    cantidad: CantidadDecimal
    motivo: str | None = Field(default=None, max_length=500)


class FibraAjusteRequest(BaseModel):
    """Ajuste administrativo de stock FO. Ergonomía
    `justificacion_opcional` (REQ-ERG-005): `motivo` es OPCIONAL — se acepta
    `null`, cadena vacía o campo omitido; el evento AJUSTE_INVENTARIO_FO
    registra el motivo tal como llega (Constitution 2.4: ledger inmutable).
    Sin `modulo` (RF-1)."""

    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    nuevo_stock: CantidadDecimal
    motivo: str | None = Field(default=None, max_length=500)


class FibraOperacionOut(BaseModel):
    """Eco mínimo del alcance operado por una operación de inventario FO
    (carga inicial o ajuste administrativo), siguiendo el patrón de
    `AjusteOut`. Sin `modulo` (dictamen @sec-ops, condición N4)."""

    material_id: int


class FibraMaterialUpdateRequest(BaseModel):
    """Edición de material desde el Inventario FO unificado
    (REQ-CATFO-001/002, REQ-STOCK-001/002/003).

    Espejo de `MaterialUpdate` (schemas/material.py) adaptado a Fibra
    Óptica: sin `is_active`, sin `modulo` y sin el campo legacy `tipo`. El
    stock NO se actualiza por ORM: si `stock_actual` viene en el payload,
    el servicio enruta el ajuste a `fn_ajustar_stock_fibra` (el
    diferencial, el bloqueo FOR UPDATE y la auditoría 'AJUSTE_INVENTARIO_FO'
    viven en PostgreSQL — Constitution 2.4, jamás UPDATE directo de stock).
    `valor_unitario` es editable SOLO por administradores (gate RBAC por
    PRESENCIA en el PATCH /fibra/materiales/{id}, RF-8); un `null`
    explícito es no-op (E15). Selector dual de categorías: `categoria_id`
    (rama A) o `nueva_categoria` (rama B), mutuamente excluyentes.

    Ergonomía `justificacion_opcional` (REQ-ERG-004): `motivo` es OPCIONAL
    incluso cuando se envía `stock_actual` — se acepta `null`, cadena vacía
    o campo omitido, y el evento AJUSTE_INVENTARIO_FO registra el motivo
    tal como llega (NULL permitido)."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = None
    nueva_categoria: str | None = Field(default=None, max_length=100)
    u_m: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    stock_actual: CantidadDecimal | None = None
    valor_unitario: CantidadDecimal | None = None
    motivo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_categoria_dual(self) -> "FibraMaterialUpdateRequest":
        if self.categoria_id is not None and self.nueva_categoria:
            raise ValueError(
                "Use solo una rama del selector dual: categoria_id o nueva_categoria."
            )
        return self


class FibraMaterialOut(BaseModel):
    """Material materializado del Inventario FO tras PATCH (join catálogo
    maestro + `inventario_fibra`): esquema estándar + categoría. Se
    construye con query directa (from_attributes=False); `alerta_stock`
    respeta la misma semántica de `FibraStockOut`. Sin `modulo` (RF-1)."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: CantidadDecimal
    valor_unitario: CantidadDecimal
    alerta_stock: bool
    categoria: str | None
    categoria_id: int | None


class ResumenGeneralOut(BaseModel):
    """Valor Total del inventario (General + Inventario FO) calculado por
    PostgreSQL con aritmética NUMERIC exacta (`fn_valor_total_inventario`,
    RF-4): redondeo a 3 decimales solo al final; `0` cuando no hay
    existencias (nunca null). `valor_total` se serializa como número JSON
    (plan §2.2)."""

    valor_total: ValorTotalJson
    moneda: Literal["MXN"]
