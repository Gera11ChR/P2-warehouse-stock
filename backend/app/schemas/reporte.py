"""DTOs de los reportes oficiales de Entrega y Consumo (actas).

Reemplazan al reporte legacy de despliegues (CSV descartado). Cada acta es
un SNAPSHOT jsonb persistido por PostgreSQL en el momento del evento
(REQ-P2-REP-003/004): el payload JSON y el XLSX se derivan de ese snapshot,
nunca del stock mutable actual. Los números (incl. `cantidad_consumida`)
vienen calculados por SQL; Python solo los transporta.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ActaTipo = Literal["ENTREGA", "CONSUMO"]


# B-4 (dictamen sec-ops): `acta_id`, `movimiento_id`, `seguimiento_id`,
# `material_id` y `usuario` son IDs internos del dominio. Se exponen
# deliberadamente (el frontend los necesita para la exportación individual)
# acotados por el aislamiento por equipo; nunca se expone el snapshot crudo.
class ActaItemOut(BaseModel):
    material_id: int
    codigo: str | None = None
    descripcion: str
    categoria: str | None = None
    u_m: str | None = None
    # ENTREGA: cantidad entregada al equipo.
    cantidad: int | None = None
    # CONSUMO: tomada / sobrante / consumida (calculadas en SQL).
    cantidad_tomada: int | None = None
    cantidad_sobrante: int | None = None
    cantidad_consumida: int | None = None


class ActaOut(BaseModel):
    acta_id: int
    tipo: ActaTipo
    movimiento_id: int | None = None
    seguimiento_id: int | None = None
    equipo_id: int | None = None
    equipo_nombre: str | None = None
    usuario: str | None = None
    observaciones: str | None = None
    fecha: datetime
    items: list[ActaItemOut]


class ActaListOut(BaseModel):
    actas: list[ActaOut]
