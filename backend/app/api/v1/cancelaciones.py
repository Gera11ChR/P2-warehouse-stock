from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.cancelacion import CanceladoOut, CancelarMovimientoRequest
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import transaccional

router = APIRouter(prefix="/movimientos", tags=["cancelaciones"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.post("/{movimiento_id}/cancelar", response_model=CanceladoOut)
async def cancelar_movimiento(
    movimiento_id: int,
    payload: CancelarMovimientoRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> CanceladoOut:
    """Reversión forense delegada a fn_cancelar_movimiento.

    Restituye matemáticamente los inventarios origen/destino, registra motivo
    y usuario autorizador (CURRENT_USER) y transiciona CONFIRMADO -> CANCELADO
    en una única transacción PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.cancelar_movimiento(
            session,
            movimiento_id=movimiento_id,
            motivo=payload.motivo,
        )
    return CanceladoOut(movimiento_id=movimiento_id, estado="CANCELADO")
