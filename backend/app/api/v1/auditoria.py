from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditoriaEvento, CatalogoMaterial, Categoria
from app.schemas.auditoria import AuditoriaListOut, AuditoriaOut
from app.security import (
    ActorContext,
    assert_authenticated,
    equipos_visibles,
    get_current_actor,
)
from sqlalchemy import and_, or_

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=AuditoriaListOut)
async def list_eventos(
    session: SessionDep,
    actor_ctx: ActorDep,
    material_id: int | None = None,
    tipo_accion: str | None = None,
    usuario: str | None = None,
    descripcion: str | None = None,
    limit: int = 100,
) -> AuditoriaListOut:
    """Ledger inmutable append-only (Constitution 2.4/6.2): solo lectura.

    REQ-API-008: LEFT JOIN al catálogo de materiales SIN filtro `is_active`
    — los eventos históricos de materiales desactivados permanecen íntegros
    y legibles; jamás se filtran eventos históricos por actividad.
    `estado_activo` solo alimenta la etiqueta [Inactivo] del frontend.
    El filtro `descripcion` aplica ILIKE sobre cm.descripcion
    (REQ-UI-006)."""
    stmt = (
        select(
            AuditoriaEvento,
            CatalogoMaterial.descripcion,
            CatalogoMaterial.codigo,
            CatalogoMaterial.is_active,
            Categoria.nombre,
        )
        .outerjoin(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == AuditoriaEvento.material_id,
        )
        .outerjoin(Categoria, Categoria.id == CatalogoMaterial.categoria_id)
    )
    assert_authenticated(actor_ctx)
    # Aislamiento (A-2, dictamen sec-ops): el actor regular solo ve eventos
    # ligados a sus secciones de alcance o a sus equipos, más los eventos
    # sin ubicación (catálogo, U.M., operadores FO); el administrador ve el
    # ledger completo.
    if not actor_ctx.es_admin:
        scopes = set(actor_ctx.scoped_almacen_ids)
        equipos = await equipos_visibles(actor_ctx, session) or set()
        condiciones = [
            AuditoriaEvento.almacen_origen_id.is_(None),
            AuditoriaEvento.almacen_destino_id.is_(None),
            AuditoriaEvento.equipo_origen_id.is_(None),
            AuditoriaEvento.equipo_destino_id.is_(None),
        ]
        sin_ubicacion = and_(*condiciones)
        if scopes:
            condiciones.append(
                or_(
                    AuditoriaEvento.almacen_origen_id.in_(scopes),
                    AuditoriaEvento.almacen_destino_id.in_(scopes),
                )
            )
        if equipos:
            condiciones.append(
                or_(
                    AuditoriaEvento.equipo_origen_id.in_(equipos),
                    AuditoriaEvento.equipo_destino_id.in_(equipos),
                )
            )
        stmt = stmt.where(or_(sin_ubicacion, *condiciones))
    if material_id is not None:
        stmt = stmt.where(AuditoriaEvento.material_id == material_id)
    if tipo_accion:
        stmt = stmt.where(AuditoriaEvento.tipo_accion == tipo_accion)
    if usuario:
        stmt = stmt.where(AuditoriaEvento.usuario == usuario)
    if descripcion:
        stmt = stmt.where(CatalogoMaterial.descripcion.ilike(f"%{descripcion}%"))
    stmt = stmt.order_by(AuditoriaEvento.id.desc()).limit(min(limit, 500))
    filas = (await session.execute(stmt)).all()
    eventos = [
        AuditoriaOut(
            id=evento.id,
            usuario=evento.usuario,
            tipo_accion=evento.tipo_accion,
            material_id=evento.material_id,
            equipo_origen_id=evento.equipo_origen_id,
            equipo_destino_id=evento.equipo_destino_id,
            almacen_origen_id=evento.almacen_origen_id,
            almacen_destino_id=evento.almacen_destino_id,
            cantidad=evento.cantidad,
            resultado=evento.resultado,
            detalles=evento.detalles,
            created_at=evento.created_at,
            descripcion=cm_descripcion,
            codigo=cm_codigo,
            categoria=cat_nombre,
            estado_activo=cm_is_active,
        )
        for evento, cm_descripcion, cm_codigo, cm_is_active, cat_nombre in filas
    ]
    return AuditoriaListOut(eventos=eventos)
