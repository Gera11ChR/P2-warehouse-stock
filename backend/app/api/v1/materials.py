from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import (
    FiberVariant,
    FleetAllocation,
    LegacyStockQuarantine,
    Sku,
    StockMovement,
    TeamInventory,
    TransferLineItem,
    WarehouseInventory,
)
from app.schemas.material import (
    MaterialCreate,
    MaterialListOut,
    MaterialOut,
    MaterialUpdate,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services.audit import make_audit

router = APIRouter(prefix="/materials", tags=["materials"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

_REFERENCING_MODELS = (
    WarehouseInventory,
    TeamInventory,
    FiberVariant,
    TransferLineItem,
    StockMovement,
    FleetAllocation,
    LegacyStockQuarantine,
)


def _to_out(sku: Sku) -> MaterialOut:
    return MaterialOut.model_validate(
        {
            "codigo": sku.sku,
            "descripcion": sku.description,
            "um": sku.unit_of_measure,
            "stock_minimo": sku.min_stock,
            "categoria": sku.categoria,
            "tipo": sku.tipo,
        }
    )


async def _assert_deletable(session: AsyncSession, sku: str) -> None:
    for model in _REFERENCING_MODELS:
        count = (
            await session.execute(
                select(func.count()).select_from(model).where(model.sku == sku)
            )
        ).scalar_one()
        if count:
            raise BusinessRuleError(
                "No se puede eliminar un material en uso",
                coordinates=[{"codigo": sku}],
            )


@router.get("", response_model=MaterialListOut)
async def list_materials(
    session: SessionDep,
    _actor: ActorDep,
    buscar: str | None = None,
    tipo: str | None = None,
) -> MaterialListOut:
    stmt = select(Sku).order_by(Sku.sku.asc())
    if buscar:
        stmt = stmt.where(
            or_(
                Sku.sku.ilike(f"%{buscar}%"),
                Sku.description.ilike(f"%{buscar}%"),
            )
        )
    if tipo:
        stmt = stmt.where(Sku.tipo == tipo)
    skus = (await session.execute(stmt)).scalars().all()
    return MaterialListOut.model_validate(
        {"materiales": [_to_out(sku) for sku in skus]}
    )


@router.post("", response_model=MaterialOut, status_code=201)
async def create_material(
    payload: MaterialCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MaterialOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        existing = await session.get(Sku, payload.codigo)
        if existing is not None:
            raise BusinessRuleError(
                "El material ya existe",
                coordinates=[{"codigo": payload.codigo}],
            )
        sku = Sku(
            sku=payload.codigo,
            description=payload.descripcion,
            unit_of_measure=payload.um,
            min_stock=payload.stock_minimo,
            categoria=payload.categoria,
            tipo=payload.tipo,
        )
        session.add(sku)
        session.add(
            make_audit(
                action="MATERIAL_CREATE",
                actor=actor_ctx.actor_id,
                details={"codigo": payload.codigo, "tipo": payload.tipo},
            )
        )
        await session.flush()
        return _to_out(sku)


@router.get("/{codigo}", response_model=MaterialOut)
async def get_material(codigo: str, session: SessionDep, _actor: ActorDep) -> MaterialOut:
    sku = await session.get(Sku, codigo)
    if sku is None:
        raise BusinessRuleError("Material no encontrado", coordinates=[{"codigo": codigo}])
    return _to_out(sku)


@router.patch("/{codigo}", response_model=MaterialOut)
async def update_material(
    codigo: str,
    payload: MaterialUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MaterialOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        sku = await session.get(Sku, codigo)
        if sku is None:
            raise BusinessRuleError(
                "Material no encontrado", coordinates=[{"codigo": codigo}]
            )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(
                sku,
                {
                    "descripcion": "description",
                    "um": "unit_of_measure",
                    "stock_minimo": "min_stock",
                    "categoria": "categoria",
                    "tipo": "tipo",
                }[field],
                value,
            )
        session.add(
            make_audit(
                action="MATERIAL_UPDATE",
                actor=actor_ctx.actor_id,
                details={"codigo": codigo},
            )
        )
        await session.flush()
        return _to_out(sku)


@router.delete("/{codigo}", status_code=204)
async def delete_material(
    codigo: str, session: SessionDep, actor_ctx: ActorDep, response: Response
) -> Response:
    assert_authenticated(actor_ctx)
    async with session.begin():
        sku = await session.get(Sku, codigo)
        if sku is None:
            raise BusinessRuleError(
                "Material no encontrado", coordinates=[{"codigo": codigo}]
            )
        await _assert_deletable(session, codigo)
        await session.delete(sku)
        session.add(
            make_audit(
                action="MATERIAL_DELETE",
                actor=actor_ctx.actor_id,
                details={"codigo": codigo},
            )
        )
        try:
            await session.flush()
        except IntegrityError:
            raise BusinessRuleError(
                "No se puede eliminar un material en uso",
                coordinates=[{"codigo": codigo}],
            ) from None
    response.status_code = 204
    return response
