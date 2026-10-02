"""Lecturas del flujo CONSUMO de campo — entidad `seguimiento` — SOLO LECTURA.

El ciclo de vida ABIERTA -> CERRADA lo gestionan exclusivamente las stored
functions `fn_crear_seguimiento` / `fn_cerrar_seguimiento` vía
services.transaccional; este módulo solo resuelve lecturas con sus items
(ledger append-only). Cero escrituras directas sobre `seguimientos` /
`seguimiento_items` y cero aritmética de stock.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import BusinessRuleError
from app.models import Seguimiento
from app.schemas.seguimiento import SeguimientoOut


async def _obtener(
    session: AsyncSession, equipo_id: int, seguimiento_id: int
) -> Seguimiento:
    """Seguimiento con items verificando la pertenencia al equipo (404 en
    caso de no existir o pertenecer a otro equipo)."""
    seguimiento = (
        await session.execute(
            select(Seguimiento)
            .options(selectinload(Seguimiento.items))
            .where(Seguimiento.id == seguimiento_id)
        )
    ).scalar_one_or_none()
    if seguimiento is None or seguimiento.equipo_id != equipo_id:
        raise BusinessRuleError(
            "Seguimiento no encontrado",
            coordinates=[
                {"equipo_id": equipo_id, "seguimiento_id": seguimiento_id}
            ],
            status_code=404,
        )
    return seguimiento


async def listar_seguimientos_equipo(
    session: AsyncSession, equipo_id: int
) -> list[SeguimientoOut]:
    """Historial completo del equipo (ambos estados), más reciente primero."""
    stmt = (
        select(Seguimiento)
        .options(selectinload(Seguimiento.items))
        .where(Seguimiento.equipo_id == equipo_id)
        .order_by(Seguimiento.id.desc())
    )
    seguimientos = (await session.execute(stmt)).scalars().all()
    return [SeguimientoOut.model_validate(d) for d in seguimientos]


async def obtener_seguimiento(
    session: AsyncSession, equipo_id: int, seguimiento_id: int
) -> SeguimientoOut:
    """Seguimiento individual con verificación de pertenencia al equipo."""
    seguimiento = await _obtener(session, equipo_id, seguimiento_id)
    return SeguimientoOut.model_validate(seguimiento)
