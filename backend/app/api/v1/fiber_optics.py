from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import FiberVariant, Sku, Warehouse
from app.schemas.fiber import FiberVariantCreate, FiberVariantListOut, FiberVariantOut
from app.security import ActorContext, assert_authenticated, assert_scope, get_current_actor
from app.services.audit import make_audit

router = APIRouter(prefix="/fiber-optics", tags=["fiber-optics"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


def _to_out(
    variant: FiberVariant, descripcion: str | None, almacen: str | None
) -> FiberVariantOut:
    return FiberVariantOut.model_validate(
        {
            "id": variant.id,
            "codigo": variant.sku,
            "descripcion": descripcion,
            "variante": variant.variante,
            "metros_restantes": variant.metros_restantes,
            "stock_actual": variant.cantidad,
            "almacen": almacen,
        }
    )


@router.get("", response_model=FiberVariantListOut)
async def list_fiber_variants(
    session: SessionDep, _actor: ActorDep
) -> FiberVariantListOut:
    rows = (
        (
            await session.execute(
                select(FiberVariant, Sku.description, Warehouse.name)
                .outerjoin(Sku, Sku.sku == FiberVariant.sku)
                .outerjoin(Warehouse, Warehouse.warehouse_id == FiberVariant.warehouse_id)
                .where(Sku.is_active == True)
                .order_by(FiberVariant.sku.asc())
            )
        )
        .all()
    )
    return FiberVariantListOut.model_validate(
        {"items": [_to_out(v, d, w) for v, d, w in rows]}
    )


@router.post("", response_model=FiberVariantOut, status_code=201)
async def create_fiber_variant(
    payload: FiberVariantCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FiberVariantOut:
    assert_authenticated(actor_ctx)
    if payload.almacen_id is not None:
        assert_scope(actor_ctx, {payload.almacen_id})
    async with session.begin():
        sku = await session.get(Sku, payload.codigo)
        if sku is None or not sku.is_active:
            raise BusinessRuleError(
                "SKU no encontrado", coordinates=[{"codigo": payload.codigo}]
            )
        variant = FiberVariant(
            sku=payload.codigo,
            variante=payload.variante,
            metros_restantes=payload.metros_restantes,
            cantidad=payload.cantidad,
            warehouse_id=payload.almacen_id,
        )
        session.add(variant)
        session.add(
            make_audit(
                action="FIBER_VARIANT_CREATE",
                actor=actor_ctx.actor_id,
                details={"codigo": payload.codigo, "variante": payload.variante},
            )
        )
        await session.flush()
        almacen = None
        if variant.warehouse_id is not None:
            warehouse = await session.get(Warehouse, variant.warehouse_id)
            almacen = warehouse.name if warehouse is not None else None
        return _to_out(variant, sku.description, almacen)
