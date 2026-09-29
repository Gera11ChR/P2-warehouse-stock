from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.material import (
    BusquedaGranelParams,
    CategoriaCreate,
    CategoriaOut,
    CategoriaUpdate,
    MaterialCreate,
    MaterialListOut,
    MaterialOut,
    MaterialUpdate,
    UmsCreate,
    UmsOut,
    UmsUpdate,
)
from app.security import (
    ActorContext,
    assert_authenticated,
    get_current_actor,
    require_admin,
)
from app.services import catalogo as catalogo_svc
from app.services import transaccional
from app.models import Categoria
from sqlalchemy import select

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


def busqueda_granel_params(
    desde_numero_lista: int | None = None,
    hasta_numero_lista: int | None = None,
    desde_descripcion: str | None = None,
    hasta_descripcion: str | None = None,
) -> BusquedaGranelParams:
    """Dependencia que reconstruye `BusquedaGranelParams` desde los query
    params del Buscador a granel (REQ-API-006/007).

    El modelo concentra TODA la validación de rango (ge=1,
    hasta >= desde) y las violaciones se traducen a 422 con el detalle de
    Pydantic. No se usa un query-model directo porque FastAPI solo aplana
    modelos de query cuando son el ÚNICO parámetro; conviviendo con los
    filtros clásicos (buscar, sku, etc.) se necesita esta dependencia."""
    try:
        return BusquedaGranelParams(
            desde_numero_lista=desde_numero_lista,
            hasta_numero_lista=hasta_numero_lista,
            desde_descripcion=desde_descripcion,
            hasta_descripcion=hasta_descripcion,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=jsonable_encoder(exc.errors())
        ) from exc


@router.get("", response_model=MaterialListOut)
async def list_materiales(
    session: SessionDep,
    _actor: ActorDep,
    params: Annotated[BusquedaGranelParams, Depends(busqueda_granel_params)],
    buscar: str | None = None,
    categoria_id: int | None = None,
    desde_id_lista: int | None = None,
    hasta_id_lista: int | None = None,
    desde_sku: str | None = None,
    hasta_sku: str | None = None,
) -> MaterialListOut:
    """Listado del catálogo activo con rango ordinal opcional
    (Buscador a granel, REQ-API-006/007).

    `BusquedaGranelParams` valida los rangos (ge=1, hasta >= desde → 422);
    el posicionamiento ordinal determinista se resuelve 100 % en backend y
    la respuesta devuelve `start_index` para que el frontend renderice
    números de lista continuos 1-indexed sin descargar el catálogo
    completo (Principio 4)."""
    materiales, start_index = await catalogo_svc.listar(
        session,
        buscar=buscar,
        categoria_id=categoria_id,
        desde_id_lista=desde_id_lista,
        hasta_id_lista=hasta_id_lista,
        desde_sku=desde_sku,
        hasta_sku=hasta_sku,
        desde_numero_lista=params.desde_numero_lista,
        hasta_numero_lista=params.hasta_numero_lista,
        desde_descripcion=params.desde_descripcion,
        hasta_descripcion=params.hasta_descripcion,
    )
    return MaterialListOut(start_index=start_index, materiales=materiales)


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
            await transaccional.cargar_stock_inicial_ruteada(
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
    """Alta de categoría (solo administradores, coherente con el alta de
    U.M.). El alta incidental vía `nueva_categoria` dentro de la edición de
    material sigue disponible para actores regulares."""
    require_admin(actor_ctx)
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


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut)
async def actualizar_categoria(
    categoria_id: int,
    payload: CategoriaUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> CategoriaOut:
    """Renombrado administrativo de categoría (solo administradores).

    El trigger tg_auditar_categoria registra CATEGORIA_MODIFICADA
    atribuyendo el actor vía `app.actor` (Constitution 6.2)."""
    require_admin(actor_ctx)
    async with session.begin():
        return await catalogo_svc.actualizar_categoria(
            session, categoria_id, payload.nombre, actor=actor_ctx.actor_id
        )


@router.delete("/categorias/{categoria_id}", status_code=204)
async def eliminar_categoria(
    categoria_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
) -> Response:
    """Eliminación lógica de categoría (is_active=FALSE), solo
    administradores. Auditada como CATEGORIA_ELIMINADA."""
    require_admin(actor_ctx)
    async with session.begin():
        await catalogo_svc.eliminar_categoria(
            session, categoria_id, actor=actor_ctx.actor_id
        )
    response.status_code = 204
    return response


@router.get("/um", response_model=list[UmsOut])
async def list_ums(session: SessionDep, _actor: ActorDep) -> list[UmsOut]:
    """Maestro activo de Unidades de Medida (lectura pública del selector)."""
    return await catalogo_svc.listar_ums(session)


@router.post("/um", response_model=UmsOut, status_code=201)
async def crear_um(
    payload: UmsCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> UmsOut:
    """Alta de Unidad de Medida (solo administradores)."""
    require_admin(actor_ctx)
    async with session.begin():
        return await catalogo_svc.crear_um(
            session, payload.nombre, actor=actor_ctx.actor_id
        )


@router.put("/um/{um_id}", response_model=UmsOut)
async def actualizar_um(
    um_id: int,
    payload: UmsUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> UmsOut:
    """Renombrado administrativo de U.M. (solo administradores), auditado
    como UM_MODIFICADA vía tg_auditar_um."""
    require_admin(actor_ctx)
    async with session.begin():
        return await catalogo_svc.actualizar_um(
            session, um_id, payload.nombre, actor=actor_ctx.actor_id
        )


@router.delete("/um/{um_id}", status_code=204)
async def eliminar_um(
    um_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
) -> Response:
    """Eliminación lógica de U.M. (is_active=FALSE), solo administradores.
    Auditada como UM_ELIMINADA."""
    require_admin(actor_ctx)
    async with session.begin():
        await catalogo_svc.eliminar_um(session, um_id, actor=actor_ctx.actor_id)
    response.status_code = 204
    return response


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
    """Edición de material (alcance Inventario General, REQ-UI-004).

    El stock JAMÁS se actualiza por ORM: si `stock_actual` viene en el
    payload, el ajuste se enruta a `fn_ajustar_stock_general` →
    `fn_ajustar_stock_almacen` (Constitution 2.4): el diferencial, la
    validación de no-negatividad y la auditoría viven en PostgreSQL.
    Atomicidad 4.1: todo ocurre dentro del mismo `session.begin()` — si el
    ajuste falla, la edición del material también revierte."""
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
        if payload.stock_actual is not None:
            # El validator del schema (_check_stock_motivo) garantiza motivo
            # no vacío cuando stock_actual está presente.
            assert payload.motivo is not None
            await transaccional.ajustar_stock_general(
                session,
                material_id=material.id_lista,
                nuevo_stock=payload.stock_actual,
                motivo=payload.motivo,
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
