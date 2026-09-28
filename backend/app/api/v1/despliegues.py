"""Flujo DESPLIEGUE de campo (0014) — apertura, listado, detalle y cierre.

INVARIANTE 5 (Zero Transactional Logic in Python): el backend jamás calcula
stock ni muta `despliegues`/`despliegue_items`/`inventario_equipos`. Toda la
aritmética corre en PostgreSQL vía `fn_crear_despliegue` y
`fn_cerrar_despliegue` (services.transaccional), bajo FOR UPDATE y con
auditoría inmutable ('DESPLIEGUE_CREADO' / 'DESPLIEGUE_CERRADO').

Aislamiento por equipo (Constitution 3.1): el actor debe ser integrante del
equipo; el administrador recibe pase transversal (security.assert_equipo_access).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.despliegue import (
    CerrarDespliegueRequest,
    DespliegueCreate,
    DespliegueListOut,
    DespliegueOut,
)
from app.security import (
    ActorContext,
    assert_authenticated,
    assert_equipo_access,
    get_current_actor,
)
from app.services import despliegues as despliegues_svc
from app.services import transaccional

router = APIRouter(prefix="/equipos", tags=["despliegues"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


async def _prechequear_equipo(
    session: AsyncSession, actor_ctx: ActorContext, equipo_id: int
) -> None:
    """404 si el equipo no existe/está inactivo ANTES del chequeo de
    aislamiento, preservando la semántica 404 > 403."""
    await transaccional.prechequear_equipo(session, equipo_id=equipo_id)
    await assert_equipo_access(actor_ctx, session, equipo_id)


@router.post("/{equipo_id}/despliegues", response_model=DespliegueOut, status_code=201)
async def crear_despliegue(
    equipo_id: int,
    payload: DespliegueCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> DespliegueOut:
    """Apertura de despliegue (ABIERTA) delegada a fn_crear_despliegue:
    validación de materiales, cero duplicados, UN SOLO despliegue abierto
    por equipo y evento 'DESPLIEGUE_CREADO' íntegros en PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        despliegue_id = await transaccional.crear_despliegue(
            session,
            equipo_id=equipo_id,
            observaciones=payload.observaciones,
            items=[
                {"material_id": i.material_id, "cantidad_tomada": i.cantidad_tomada}
                for i in payload.items
            ],
            usuario=actor_ctx.actor_id,
        )
        return await despliegues_svc.obtener_despliegue(
            session, equipo_id, despliegue_id
        )


@router.get("/{equipo_id}/despliegues", response_model=DespliegueListOut)
async def listar_despliegues(
    equipo_id: int, session: SessionDep, actor_ctx: ActorDep
) -> DespliegueListOut:
    """Historial de despliegues del equipo (ABIERTA y CERRADA), más
    reciente primero. Aislamiento por integrante de equipo."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    despliegues = await despliegues_svc.listar_despliegues_equipo(
        session, equipo_id
    )
    return DespliegueListOut(despliegues=despliegues)


@router.get("/{equipo_id}/despliegues/{despliegue_id}", response_model=DespliegueOut)
async def obtener_despliegue(
    equipo_id: int,
    despliegue_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> DespliegueOut:
    """Despliegue individual con verificación de pertenencia al equipo."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    return await despliegues_svc.obtener_despliegue(
        session, equipo_id, despliegue_id
    )


@router.post(
    "/{equipo_id}/despliegues/{despliegue_id}/cerrar",
    response_model=DespliegueOut,
)
async def cerrar_despliegue(
    equipo_id: int,
    despliegue_id: int,
    payload: CerrarDespliegueRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> DespliegueOut:
    """Cierre con sobrantes delegado a fn_cerrar_despliegue: valida cada
    sobrante (0 ≤ sobrante ≤ tomada), descuenta el consumido del inventario
    del equipo bajo FOR UPDATE y audita 'DESPLIEGUE_CERRADO' por línea.
    Las líneas omitidas se cierran con sobrante 0. Clasificación 404/409
    por pre-chequeo; la autoridad transaccional permanece en PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        # Pre-chequeo de pertenencia al equipo (404 si no corresponde).
        await despliegues_svc.obtener_despliegue(session, equipo_id, despliegue_id)
        await transaccional.cerrar_despliegue(
            session,
            despliegue_id=despliegue_id,
            sobrantes=[
                {
                    "material_id": s.material_id,
                    "cantidad_sobrante": s.cantidad_sobrante,
                }
                for s in payload.sobrantes
            ],
            usuario=actor_ctx.actor_id,
            observaciones_cierre=payload.observaciones_cierre,
        )
        return await despliegues_svc.obtener_despliegue(
            session, equipo_id, despliegue_id
        )
