"""ACTIVIDADES por Unidad (0029, paquete 2026-10-actividades-unidad) —
router FastAPI.

Captura y lectura del registro documental de actividades. INVARIANTE 5
(Zero Transactional Logic in Python): folio, fecha, snapshot de materiales
con valor_unitario, unicidad 1:1 con el seguimiento CERRADA y el evento
ACTIVIDAD_CONFIRMADA los decide `fn_crear_actividad` en PostgreSQL
(services.transaccional). Este router solo transporta el payload validado
por el DTO (extra="forbid") y resuelve lecturas.

Aislamiento por unidad (Constitution 3.1): el administrador pasa directo;
el actor regular debe ser integrante (security.assert_equipo_access), con
404 antes de 403 (semántica del flujo seguimientos) y `assert_authenticated`
en el POST (default-deny).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.actividad import (
    ActividadCreate,
    ActividadListOut,
    ActividadOut,
    ActividadPendienteOut,
)
from app.security import (
    ActorContext,
    assert_authenticated,
    assert_equipo_access,
    get_current_actor,
)
from app.services import actividades as actividades_svc
from app.services import transaccional

router = APIRouter(prefix="/equipos", tags=["actividades"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

# Códigos del contrato (plan §3.2) documentados en OpenAPI para el consumidor
# (State-Agent): solo descripción, el comportamiento lo fijan los handlers.
_R_400 = {"description": "Identificador numérico fuera de rango INT4 (NUMERIC_OUT_OF_RANGE)"}
_R_403 = {"description": "Actor sin acceso a la Unidad (no integrante ni administrador)"}
_R_404 = {"description": "Unidad no encontrada o inactiva"}
_R_409 = {
    "description": "Seguimiento no cerrado (SEGUIMIENTO_NO_CERRADO) o con actividad "
    "ya confirmada (ACTIVIDAD_DUPLICADA)"
}


async def _prechequear_equipo(
    session: AsyncSession, actor_ctx: ActorContext, equipo_id: int
) -> None:
    """404 si la Unidad no existe/está inactiva ANTES del chequeo de
    aislamiento, preservando la semántica 404 > 403."""
    await transaccional.prechequear_equipo(session, equipo_id=equipo_id)
    await assert_equipo_access(actor_ctx, session, equipo_id)


@router.get(
    "/{equipo_id}/actividades/pendiente",
    response_model=ActividadPendienteOut,
    responses={400: _R_400, 403: _R_403, 404: _R_404},
)
async def actividad_pendiente(
    equipo_id: int, session: SessionDep, actor_ctx: ActorDep
) -> ActividadPendienteOut:
    """Seguimiento CERRADA más reciente de la Unidad sin actividad, con sus
    materiales consumidos y el valor unitario vigente (RF-2). `seguimiento:
    null` si no hay (RF-3)."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    return await actividades_svc.obtener_actividad_pendiente(session, equipo_id)


@router.post(
    "/{equipo_id}/actividades",
    response_model=ActividadOut,
    status_code=201,
    responses={
        400: _R_400,
        403: _R_403,
        404: {
            "description": "Unidad no encontrada (o seguimiento inexistente para la "
            "Unidad: SEGUIMIENTO_NO_ENCONTRADO)"
        },
        409: _R_409,
    },
)
async def crear_actividad(
    equipo_id: int,
    payload: ActividadCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> ActividadOut:
    """Confirmación delegada a fn_crear_actividad: folio global correlativo,
    fecha now(), snapshot de materiales, unicidad 1:1 con el seguimiento
    CERRADA y evento ACTIVIDAD_CONFIRMADA íntegros en PostgreSQL. El folio
    devuelto es el asignado por la base (nunca aceptado del cliente)."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        actividad_id = await transaccional.crear_actividad(
            session,
            equipo_id=equipo_id,
            seguimiento_id=payload.seguimiento_id,
            vehiculo=payload.vehiculo,
            clientes=payload.clientes,
            direcciones=payload.direcciones,
            actividades=payload.actividades,
            comentarios=payload.comentarios,
            usuario=actor_ctx.actor_id,
        )
        return await actividades_svc.obtener_actividad(
            session, equipo_id, actividad_id
        )


@router.get(
    "/{equipo_id}/actividades",
    response_model=ActividadListOut,
    responses={400: _R_400, 403: _R_403, 404: _R_404},
)
async def listar_actividades(
    equipo_id: int, session: SessionDep, actor_ctx: ActorDep
) -> ActividadListOut:
    """Historial de actividades confirmadas de la Unidad, más reciente
    primero (RF-16)."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    return await actividades_svc.listar_actividades(session, equipo_id)
