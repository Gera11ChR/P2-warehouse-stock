from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Sku, StockTransfer, WarehouseInventory
from app.schemas.kpi import KpisOut
from app.security import ActorContext, get_current_actor

router = APIRouter(prefix="/kpis", tags=["kpis"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=KpisOut)
async def get_kpis(session: SessionDep, _actor: ActorDep) -> KpisOut:
    total_materiales = (
        await session.execute(select(func.count()).select_from(Sku))
    ).scalar_one()
    stock_total = (
        await session.execute(
            select(func.coalesce(func.sum(WarehouseInventory.on_hand_quantity), 0))
        )
    ).scalar_one()
    alertas_stock = (
        await session.execute(
            select(func.count(func.distinct(Sku.sku)))
            .join(WarehouseInventory, WarehouseInventory.sku == Sku.sku)
            .where(
                Sku.min_stock.is_not(None),
                WarehouseInventory.on_hand_quantity <= Sku.min_stock,
            )
        )
    ).scalar_one()
    transferencias_hoy = (
        await session.execute(
            select(func.count())
            .select_from(StockTransfer)
            .where(func.date(StockTransfer.created_at) == func.current_date())
        )
    ).scalar_one()
    return KpisOut.model_validate(
        {
            "total_materiales": total_materiales,
            "stock_total": stock_total,
            "alertas_stock": alertas_stock,
            "transferencias_hoy": transferencias_hoy,
        }
    )
