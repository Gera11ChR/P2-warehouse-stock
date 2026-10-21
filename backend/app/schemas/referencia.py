"""DTOs de la Referencia de materiales por Unidad (0030, paquete
2026-10-referencia-materiales-unidades, plan §4.1).

Contrato Backend-First congelable en T7 (REQ-REF-005..009): los nombres,
tipos y límites de estos DTOs son la fuente del snapshot OpenAPI. Todos los
modelos de ENTRADA son `extra="forbid"` (campos no declarados → 422,
Constitución §3) y `cantidad_semanal` reutiliza `CantidadMovimiento`
(> 0, hasta 12 dígitos en total y 3 decimales — C-13/REQ-REF-007); la
salida usa `CantidadDecimal` para serializar como número JSON, como el
resto de los Outs del contrato.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas._tipos import CantidadDecimal, CantidadMovimiento


class ReferenciaLineaCreate(BaseModel):
    """Línea de alta: `material_id` positivo dentro de INT4 (C-13) y su
    Cantidad Semanal (REQ-REF-006/007). La cantidad es visual: no es stock
    y no se valida contra él (RN-5/RN-7)."""

    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0, le=2147483647)
    cantidad_semanal: CantidadMovimiento


class ReferenciaCreate(BaseModel):
    """Alta masiva todo-o-nada de la Referencia (REQ-REF-006): de 1 a 50
    líneas (límite defensivo del paquete, C-8). El origen de la interfaz
    (Inventario General / Inventario FO) NO forma parte del contrato."""

    model_config = ConfigDict(extra="forbid")

    lineas: list[ReferenciaLineaCreate] = Field(
        min_length=1, max_length=50
    )


class ReferenciaUpdate(BaseModel):
    """Modificación de una línea: solo la Cantidad Semanal
    (REQ-REF-008, C-11/Q4). No permite cambiar el material."""

    model_config = ConfigDict(extra="forbid")

    cantidad_semanal: CantidadMovimiento


class ReferenciaLineaOut(BaseModel):
    """Línea listada (REQ-REF-005): `codigo`/`descripcion` se leen del
    catálogo EN VIVO en cada consulta y `u_m` es la U.M. efectiva de la
    Unidad (la local de `equipo_material_config` o, si no hay, la del
    catálogo — C-1/Q2/P-9). Solo lectura."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    cantidad_semanal: CantidadDecimal


class ReferenciaListOut(BaseModel):
    """Listado `{items, total}` (REQ-REF-005): `total` cuenta solo los
    ítems listados; las líneas con material inactivo se conservan pero no
    se listan. El POST responde con las líneas creadas y `total` = creadas
    (REQ-REF-006)."""

    items: list[ReferenciaLineaOut]
    total: int
