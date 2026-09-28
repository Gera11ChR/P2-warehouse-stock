from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import (
    CatalogoMaterial,
    Categoria,
    Equipo,
    EquipoIntegrante,
    EquipoMaterialConfig,
    InventarioEquipo,
    Ums,
)
from app.schemas.equipo import (
    EquipoConfigLocalOut,
    EquipoConfigLocalUpdate,
    EquipoCreate,
    EquipoOut,
    EquipoUpdate,
)
from app.schemas.inventario import InventarioEquipoOut
from app.security import (
    ActorContext,
    assert_authenticated,
    assert_equipo_access,
    get_current_actor,
)

router = APIRouter(prefix="/equipos", tags=["equipos"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

_CatLocal = aliased(Categoria)
_UmsLocal = aliased(Ums)


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
    equipo_id: int, session: SessionDep, actor_ctx: ActorDep
) -> list[InventarioEquipoOut]:
    """Inventario autónomo del equipo (REQ-DOMAIN-001/002, Task 3.6).

    Query directa a `inventario_equipos` (la vista sparse ya no existe):
    solo filas físicas con stock real originado en movimientos TEAMS/DEVOL
    auditados. Cero fantasmas: se omiten materiales inactivos y filas de
    stock 0 (REQ-API-001). Cada fila traza su movimiento de origen vía
    `ultimo_movimiento_id`. Un equipo nuevo devuelve [] (200) — inventario
    autónomo vacío, jamás 404 por catálogo vacío.

    Extensión 0014: LEFT JOIN a `equipo_material_config` con valores
    EFECTIVOS por COALESCE (stock_minimo_efectivo, categoria_efectiva,
    um_efectivo). Sin configuración local, los efectivos replican
    exactamente el comportamiento previo (alerta contra cm.stock_minimo).

    Aislamiento por equipo (REQ-VIEW-001 + SEC-003): la consulta segura
    exige integrante del equipo o administrador (403 en caso contrario)."""
    equipo = await _obtener(session, equipo_id)
    if equipo is None:
        raise BusinessRuleError(
            "Equipo no encontrado",
            coordinates=[{"equipo_id": equipo_id}],
            status_code=404,
        )
    await assert_equipo_access(actor_ctx, session, equipo_id)
    stock_minimo_efectivo = func.coalesce(
        EquipoMaterialConfig.stock_minimo_local, CatalogoMaterial.stock_minimo
    ).label("stock_minimo_efectivo")
    categoria_efectiva = func.coalesce(
        _CatLocal.nombre, Categoria.nombre
    ).label("categoria_efectiva")
    um_efectivo = func.coalesce(
        _UmsLocal.nombre, CatalogoMaterial.u_m
    ).label("um_efectivo")
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
            EquipoMaterialConfig.stock_minimo_local,
            EquipoMaterialConfig.categoria_local_id,
            EquipoMaterialConfig.um_local_id,
            stock_minimo_efectivo,
            categoria_efectiva,
            um_efectivo,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == InventarioEquipo.material_id,
        )
        .outerjoin(
            EquipoMaterialConfig,
            and_(
                EquipoMaterialConfig.equipo_id == InventarioEquipo.equipo_id,
                EquipoMaterialConfig.material_id == InventarioEquipo.material_id,
            ),
        )
        .outerjoin(Categoria, Categoria.id == CatalogoMaterial.categoria_id)
        .outerjoin(
            _CatLocal, _CatLocal.id == EquipoMaterialConfig.categoria_local_id
        )
        .outerjoin(_UmsLocal, _UmsLocal.id == EquipoMaterialConfig.um_local_id)
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
                f.stock_actual <= f.stock_minimo_efectivo
                if f.stock_minimo_efectivo is not None
                else False
            ),
            ultimo_movimiento_id=f.ultimo_movimiento_id,
            stock_minimo_local=f.stock_minimo_local,
            categoria_local_id=f.categoria_local_id,
            um_local_id=f.um_local_id,
            stock_minimo_efectivo=f.stock_minimo_efectivo,
            categoria_efectiva=f.categoria_efectiva,
            um_efectivo=f.um_efectivo,
        )
        for f in filas
    ]


@router.patch(
    "/{equipo_id}/inventario/{material_id}",
    response_model=EquipoConfigLocalOut,
)
async def configurar_inventario_local(
    equipo_id: int,
    material_id: int,
    payload: EquipoConfigLocalUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> EquipoConfigLocalOut:
    """Configuración operativa LOCAL del material en el equipo
    (`equipo_material_config`, 0014): stock mínimo, categoría y U.M. propias
    del equipo — sin tocar el catálogo maestro ni el stock.

    Upsert con asignación EXPLÍCITA de campos (jamás model_dump+setattr en
    bucle) precedido de `set_config('app.actor', …)` para que el trigger
    tg_auditar_equipo_material_config audite CONFIG_EQUIPO_MODIFICADA con el
    actor del header X-Actor (Constitution 6.2)."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        equipo = await session.get(Equipo, equipo_id)
        if equipo is None or not equipo.is_active:
            raise BusinessRuleError(
                "Equipo no encontrado",
                coordinates=[{"equipo_id": equipo_id}],
                status_code=404,
            )
        await assert_equipo_access(actor_ctx, session, equipo_id)
        material = await session.get(CatalogoMaterial, material_id)
        if material is None or not material.is_active:
            raise BusinessRuleError(
                "Material no encontrado",
                coordinates=[{"material_id": material_id}],
                status_code=404,
            )
        if payload.categoria_local_id is not None:
            categoria = await session.get(Categoria, payload.categoria_local_id)
            if categoria is None or not categoria.is_active:
                raise BusinessRuleError(
                    "Categoría local inexistente",
                    coordinates=[{"categoria_local_id": payload.categoria_local_id}],
                    status_code=404,
                )
        if payload.um_local_id is not None:
            um = await session.get(Ums, payload.um_local_id)
            if um is None or not um.is_active:
                raise BusinessRuleError(
                    "Unidad de medida local inexistente",
                    coordinates=[{"um_local_id": payload.um_local_id}],
                    status_code=404,
                )
        await session.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor_ctx.actor_id},
        )
        config = await session.get(
            EquipoMaterialConfig, (equipo_id, material_id)
        )
        if config is None:
            config = EquipoMaterialConfig(
                equipo_id=equipo_id, material_id=material_id
            )
            session.add(config)
        # Asignación explícita campo a campo (sin bucles setattr).
        if payload.stock_minimo_local is not None:
            config.stock_minimo_local = payload.stock_minimo_local
        if payload.categoria_local_id is not None:
            config.categoria_local_id = payload.categoria_local_id
        if payload.um_local_id is not None:
            config.um_local_id = payload.um_local_id
        await session.flush()
        await session.refresh(config)
        return EquipoConfigLocalOut.model_validate(config)


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
        # V1 (sec-ops): sin aislamiento, cualquier actor podría reescribir
        # `integrantes` y auto-alta para saltarse el aislamiento de los
        # flujos de equipo. Solo el administrador o un integrante actual
        # del equipo puede modificarlo/eliminarlo.
        await assert_equipo_access(actor_ctx, session, equipo_id)
        update = payload.model_dump(exclude_unset=True, exclude={"integrantes"})
        if "nombre" in update:
            equipo.nombre = update["nombre"]
        if "descripcion" in update:
            equipo.descripcion = update["descripcion"]
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
        # V1 (sec-ops): misma regla de aislamiento que en PATCH.
        await assert_equipo_access(actor_ctx, session, equipo_id)
        equipo.is_active = False
        await session.flush()
    response.status_code = 204
    return response
