from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditoriaOut(BaseModel):
    """Evento inmutable del ledger de Auditoría (Constitution 2.4/6.2).

    `descripcion`, `codigo`, `categoria` y `estado_activo` provienen de un
    LEFT JOIN al catálogo de materiales SIN filtro `is_active`
    (REQ-API-008): los eventos históricos de materiales desactivados
    permanecen íntegros y legibles, jamás se ocultan ni se mutan.
    `estado_activo` solo permite al frontend renderizar una etiqueta
    visual discreta `[Inactivo]` (REQ-UI-006)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario: str | None
    tipo_accion: str
    material_id: int | None
    equipo_origen_id: int | None
    equipo_destino_id: int | None
    almacen_origen_id: int | None
    almacen_destino_id: int | None
    cantidad: int | None
    resultado: str | None
    detalles: dict | None
    created_at: datetime
    descripcion: str | None
    codigo: str | None
    categoria: str | None
    estado_activo: bool | None


class AuditoriaListOut(BaseModel):
    eventos: list[AuditoriaOut]
