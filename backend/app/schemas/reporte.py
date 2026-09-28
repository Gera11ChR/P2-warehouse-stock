"""DTOs del reporte de despliegues (REQ: reportes de campo).

Esquema plano por línea de material con los nombres de catálogo resueltos
(categoría y U.M.), orientado tanto al payload JSON como a la exportación
CSV con sanitización anti-inyección de fórmulas.
"""

from datetime import date, datetime

from pydantic import BaseModel


class ReporteDespliegueItemOut(BaseModel):
    material_id: int
    codigo: str | None
    descripcion: str
    categoria: str | None
    um: str | None
    cantidad_tomada: int
    cantidad_sobrante: int | None
    cantidad_consumida: int | None


class ReporteDespliegueOut(BaseModel):
    despliegue_id: int
    equipo_id: int
    equipo_nombre: str
    fecha: date
    estado: str
    usuario: str
    observaciones: str | None
    created_at: datetime
    closed_at: datetime | None
    items: list[ReporteDespliegueItemOut]


class ReporteDespliegueListOut(BaseModel):
    despliegues: list[ReporteDespliegueOut]
