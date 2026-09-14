from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.material import (
    CategoriaCreate,
    CategoriaOut,
    MaterialCreate,
    MaterialListOut,
    MaterialOut,
    MaterialUpdate,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import catalogo as catalogo_svc
from app.services import transaccional
from app.models import Categoria
from sqlalchemy import select

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=MaterialListOut)
async def list_materiales(
    session: SessionDep,
    _actor: ActorDep,
    buscar: str | None = None,
    categoria_id: int | None = None,
    desde_id_lista: int | None = None,
    hasta_id_lista: int | None = None,
    desde_sku: str | None = None,
    hasta_sku: str | None = None,
) -> MaterialListOut:
    materiales = await catalogo_svc.listar(
        session,
        buscar=buscar,
        categoria_id=categoria_id,
        desde_id_lista=desde_id_lista,
        hasta_id_lista=hasta_id_lista,
        desde_sku=desde_sku,
        hasta_sku=hasta_sku,
    )
    return MaterialListOut(materiales=materiales)


@router.post("", response_model=MaterialOut, status_code=201)
async def crear_material(
    payload: MaterialCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MaterialOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        material = await catalogo_svc.crear(
            session, payload, actor=actor_ctx.actor_id
        )
        if payload.stock_inicial is not None:
            assert payload.seccion_id is not None
            await transaccional.cargar_stock_inicial(
                session,
                almacen_id=payload.seccion_id,
                material_id=material.id_lista,
                cantidad=payload.stock_inicial,
                motivo="Carga inicial en alta de catálogo",
            )
        return material


@router.get("/categorias", response_model=list[CategoriaOut])
async def list_categorias(session: SessionDep, _actor: ActorDep) -> list[CategoriaOut]:
    stmt = select(Categoria).where(Categoria.is_active == True).order_by(  # noqa: E712
        Categoria.nombre.asc()
    )
    categorias = (await session.execute(stmt)).scalars().all()
    return [CategoriaOut.model_validate(c) for c in categorias]


@router.post("/categorias", response_model=CategoriaOut, status_code=201)
async def crear_categoria(
    payload: CategoriaCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> CategoriaOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        existente = (
            await session.execute(
                select(Categoria).where(Categoria.nombre == payload.nombre.strip())
            )
        ).scalar_one_or_none()
        if existente is not None:
            raise BusinessRuleError(
                "La categoría ya existe",
                coordinates=[{"nombre": payload.nombre}],
                status_code=409,
            )
        categoria = Categoria(nombre=payload.nombre.strip())
        session.add(categoria)
        await session.flush()
        return CategoriaOut.model_validate(categoria)


@router.get("/{id_lista}", response_model=MaterialOut)
async def obtener_material(
    id_lista: int, session: SessionDep, _actor: ActorDep
) -> MaterialOut:
    material = await catalogo_svc.obtener(session, id_lista)
    if material is None:
        raise BusinessRuleError(
            "Material no encontrado",
            coordinates=[{"id_lista": id_lista}],
            status_code=404,
        )
    return material


@router.patch("/{id_lista}", response_model=MaterialOut)
async def actualizar_material(
    id_lista: int,
    payload: MaterialUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MaterialOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        material = await catalogo_svc.actualizar(
            session, id_lista, payload, actor=actor_ctx.actor_id
        )
        if material is None:
            raise BusinessRuleError(
                "Material no encontrado",
                coordinates=[{"id_lista": id_lista}],
                status_code=404,
            )
        return material


@router.delete("/{id_lista}", status_code=204)
async def eliminar_material(
    id_lista: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
) -> Response:
    assert_authenticated(actor_ctx)
    async with session.begin():
        eliminado = await catalogo_svc.eliminar(
            session, id_lista, actor=actor_ctx.actor_id
        )
        if not eliminado:
            raise BusinessRuleError(
                "Material no encontrado",
                coordinates=[{"id_lista": id_lista}],
                status_code=404,
            )
    response.status_code = 204
    return response
