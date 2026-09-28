"""Lecturas del flujo DESPLIEGUE de campo (0014) — SOLO LECTURA.

El ciclo de vida ABIERTA -> CERRADA lo gestionan exclusivamente las stored
functions `fn_crear_despliegue` / `fn_cerrar_despliegue` vía
services.transaccional; este módulo solo resuelve lecturas con sus items
(ledger append-only). Cero escrituras directas sobre `despliegues` /
`despliegue_items` y cero aritmética de stock.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import BusinessRuleError
from app.models import Despliegue
from app.schemas.despliegue import DespliegueOut


async def _obtener(
    session: AsyncSession, equipo_id: int, despliegue_id: int
) -> Despliegue:
    """Despliegue con items verificando la pertenencia al equipo (404 en
    caso de no existir o pertenecer a otro equipo)."""
    despliegue = (
        await session.execute(
            select(Despliegue)
            .options(selectinload(Despliegue.items))
            .where(Despliegue.id == despliegue_id)
        )
    ).scalar_one_or_none()
    if despliegue is None or despliegue.equipo_id != equipo_id:
        raise BusinessRuleError(
            "Despliegue no encontrado",
            coordinates=[
                {"equipo_id": equipo_id, "despliegue_id": despliegue_id}
            ],
            status_code=404,
        )
    return despliegue


async def listar_despliegues_equipo(
    session: AsyncSession, equipo_id: int
) -> list[DespliegueOut]:
    """Historial completo del equipo (ambos estados), más reciente primero."""
    stmt = (
        select(Despliegue)
        .options(selectinload(Despliegue.items))
        .where(Despliegue.equipo_id == equipo_id)
        .order_by(Despliegue.id.desc())
    )
    despliegues = (await session.execute(stmt)).scalars().all()
    return [DespliegueOut.model_validate(d) for d in despliegues]


async def obtener_despliegue(
    session: AsyncSession, equipo_id: int, despliegue_id: int
) -> DespliegueOut:
    """Despliegue individual con verificación de pertenencia al equipo."""
    despliegue = await _obtener(session, equipo_id, despliegue_id)
    return DespliegueOut.model_validate(despliegue)
