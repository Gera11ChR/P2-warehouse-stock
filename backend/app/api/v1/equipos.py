from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import Equipo, EquipoIntegrante
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate
from app.security import ActorContext, assert_authenticated, get_current_actor

router = APIRouter(prefix="/equipos", tags=["equipos"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


def _to_out(equipo: Equipo) -> EquipoOut:
    return EquipoOut(
        equipo_id=equipo.equipo_id,
        nombre=equipo.nombre,
        descripcion=equipo.descripcion,
        is_active=equipo.is_active,
        integrantes=[i.usuario for i in equipo.integrantes],
    )


async def _obtener(session: AsyncSession, equipo_id: int) -> Equipo | None:
    return (
        await session.execute(
            select(Equipo)
            .options(selectinload(Equipo.integrantes))
            .where(Equipo.equipo_id == equipo_id, Equipo.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()


@router.get("", response_model=list[EquipoOut])
async def list_equipos(session: SessionDep, _actor: ActorDep) -> list[EquipoOut]:
    stmt = (
        select(Equipo)
        .options(selectinload(Equipo.integrantes))
        .where(Equipo.is_active == True)  # noqa: E712
        .order_by(Equipo.equipo_id.asc())
    )
    equipos = (await session.execute(stmt)).scalars().all()
    return [_to_out(e) for e in equipos]


@router.post("", response_model=EquipoOut, status_code=201)
async def crear_equipo(
    payload: EquipoCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> EquipoOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        equipo = Equipo(
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            integrantes=[
                EquipoIntegrante(usuario=u) for u in payload.integrantes
            ],
        )
        session.add(equipo)
        await session.flush()
        return _to_out(equipo)


@router.get("/{equipo_id}", response_model=EquipoOut)
async def obtener_equipo(
    equipo_id: int, session: SessionDep, _actor: ActorDep
) -> EquipoOut:
    equipo = await _obtener(session, equipo_id)
    if equipo is None:
        raise BusinessRuleError(
            "Equipo no encontrado",
            coordinates=[{"equipo_id": equipo_id}],
            status_code=404,
        )
    return _to_out(equipo)


@router.patch("/{equipo_id}", response_model=EquipoOut)
async def actualizar_equipo(
    equipo_id: int,
    payload: EquipoUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> EquipoOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        equipo = await _obtener(session, equipo_id)
        if equipo is None:
            raise BusinessRuleError(
                "Equipo no encontrado",
                coordinates=[{"equipo_id": equipo_id}],
                status_code=404,
            )
        update = payload.model_dump(exclude_unset=True, exclude={"integrantes"})
        for field, value in update.items():
            setattr(equipo, field, value)
        if payload.integrantes is not None:
            equipo.integrantes = [
                EquipoIntegrante(usuario=u) for u in payload.integrantes
            ]
        await session.flush()
        return _to_out(equipo)


@router.delete("/{equipo_id}", status_code=204)
async def eliminar_equipo(
    equipo_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
) -> Response:
    assert_authenticated(actor_ctx)
    async with session.begin():
        equipo = await _obtener(session, equipo_id)
        if equipo is None:
            raise BusinessRuleError(
                "Equipo no encontrado",
                coordinates=[{"equipo_id": equipo_id}],
                status_code=404,
            )
        equipo.is_active = False
        await session.flush()
    response.status_code = 204
    return response
