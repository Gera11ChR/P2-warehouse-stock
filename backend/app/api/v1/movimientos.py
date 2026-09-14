from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.movimiento import (
    MovimientoBorradorCreate,
    MovimientoBorradorUpdate,
    MovimientoListOut,
    MovimientoOut,
    ProcesadoOut,
    ProcesarRequest,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import movimientos as movimientos_svc
from app.services import transaccional

router = APIRouter(prefix="/movimientos", tags=["movimientos"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.post("", response_model=MovimientoOut, status_code=201)
async def crear_borrador(
    payload: MovimientoBorradorCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MovimientoOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        return await movimientos_svc.crear_borrador(
            session, payload, actor=actor_ctx.actor_id
        )


@router.get("", response_model=MovimientoListOut)
async def list_movimientos(
    session: SessionDep,
    _actor: ActorDep,
    estado: str | None = None,
    tipo_movimiento: str | None = None,
) -> MovimientoListOut:
    movimientos = await movimientos_svc.listar(
        session, estado=estado, tipo_movimiento=tipo_movimiento
    )
    return MovimientoListOut(movimientos=movimientos)


@router.get("/{movimiento_id}", response_model=MovimientoOut)
async def obtener_movimiento(
    movimiento_id: int, session: SessionDep, _actor: ActorDep
) -> MovimientoOut:
    return await movimientos_svc.obtener(session, movimiento_id)


@router.patch("/{movimiento_id}", response_model=MovimientoOut)
async def actualizar_borrador(
    movimiento_id: int,
    payload: MovimientoBorradorUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MovimientoOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        return await movimientos_svc.actualizar_borrador(
            session, movimiento_id, payload, actor=actor_ctx.actor_id
        )


@router.delete("/{movimiento_id}", status_code=204)
async def eliminar_borrador(
    movimiento_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
) -> Response:
    assert_authenticated(actor_ctx)
    async with session.begin():
        await movimientos_svc.eliminar_borrador(
            session, movimiento_id, actor=actor_ctx.actor_id
        )
    response.status_code = 204
    return response


@router.post("/procesar", response_model=ProcesadoOut)
async def procesar(
    payload: ProcesarRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> ProcesadoOut:
    """Punto de delegación transaccional obligatoria (Invariante 5).

    Cero cálculo de stock en Python: fn_procesar_movimiento descuenta origen,
    incrementa destino, audita y confirma atómicamente dentro de PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.procesar_movimiento(
            session, movimiento_id=payload.movimiento_id
        )
    return ProcesadoOut(movimiento_id=payload.movimiento_id, estado="CONFIRMADO")
