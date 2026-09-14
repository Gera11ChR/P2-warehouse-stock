from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditoriaOut(BaseModel):
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


class AuditoriaListOut(BaseModel):
    eventos: list[AuditoriaOut]
