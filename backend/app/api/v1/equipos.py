from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import CatalogoMaterial, Equipo, EquipoIntegrante, InventarioEquipo
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate
from app.schemas.inventario import InventarioEquipoOut
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
    """Alta de equipo (REQ-DOMAIN-001/002, Task 3.5).

    INVARIANTE EXPLÍCITA: NO se insertan filas de inventario. El inventario
    autónomo del equipo nace VACÍO (cero herencia del catálogo global) y
    solo se puebla por movimientos TEAMS/DEVOL auditados
    (fn_procesar_movimiento). GET /{equipo_id}/inventario devuelve [] (200)
    para un equipo nuevo."""
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


@router.get("/{equipo_id}/inventario", response_model=list[InventarioEquipoOut])
async def inventario_equipo(
    equipo_id: int, session: SessionDep, _actor: ActorDep
) -> list[InventarioEquipoOut]:
    """Inventario autónomo del equipo (REQ-DOMAIN-001/002, Task 3.6).

    Query directa a `inventario_equipos` (la vista sparse ya no existe):
    solo filas físicas con stock real originado en movimientos TEAMS/DEVOL
    auditados. Cero fantasmas: se omiten materiales inactivos y filas de
    stock 0 (REQ-API-001). Cada fila traza su movimiento de origen vía
    `ultimo_movimiento_id`. Un equipo nuevo devuelve [] (200) — inventario
    autónomo vacío, jamás 404 por catálogo vacío."""
    equipo = await _obtener(session, equipo_id)
    if equipo is None:
        raise BusinessRuleError(
            "Equipo no encontrado",
            coordinates=[{"equipo_id": equipo_id}],
            status_code=404,
        )
    stmt = (
        select(
            InventarioEquipo.equipo_id,
            InventarioEquipo.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            CatalogoMaterial.u_m,
            CatalogoMaterial.stock_minimo,
            InventarioEquipo.stock_actual,
            InventarioEquipo.ultimo_movimiento_id,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == InventarioEquipo.material_id,
        )
        .where(
            InventarioEquipo.equipo_id == equipo_id,
            CatalogoMaterial.is_active == True,  # noqa: E712
            InventarioEquipo.stock_actual > 0,
        )
        .order_by(InventarioEquipo.material_id.asc())
    )
    filas = (await session.execute(stmt)).all()
    return [
        InventarioEquipoOut(
            equipo_id=f.equipo_id,
            material_id=f.material_id,
            codigo=f.codigo,
            descripcion=f.descripcion,
            u_m=f.u_m,
            stock_minimo=f.stock_minimo,
            stock_actual=f.stock_actual,
            alerta_stock=(
                f.stock_actual <= f.stock_minimo
                if f.stock_minimo is not None
                else False
            ),
            ultimo_movimiento_id=f.ultimo_movimiento_id,
        )
        for f in filas
    ]


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
