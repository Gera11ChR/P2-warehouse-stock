from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Sku, Warehouse, WarehouseInventory
from app.schemas.inventory import InventoryListOut, InventoryRowOut
from app.security import ActorContext, get_current_actor

router = APIRouter(prefix="/inventory", tags=["inventory"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=InventoryListOut)
async def list_inventory(
    session: SessionDep,
    _actor: ActorDep,
    buscar: str | None = None,
    categoria: str | None = None,
    um: str | None = None,
    almacen: str | None = None,
    desde_sku: str | None = None,
    hasta_sku: str | None = None,
) -> InventoryListOut:
    stmt = (
        select(Sku, WarehouseInventory, Warehouse)
        .join(WarehouseInventory, WarehouseInventory.sku == Sku.sku)
        .join(Warehouse, Warehouse.warehouse_id == WarehouseInventory.warehouse_id)
    )
    if buscar:
        stmt = stmt.where(
            or_(
                Sku.sku.ilike(f"%{buscar}%"),
                Sku.description.ilike(f"%{buscar}%"),
            )
        )
    if categoria:
        stmt = stmt.where(Sku.categoria == categoria)
    if um:
        stmt = stmt.where(Sku.unit_of_measure == um)
    if almacen:
        stmt = stmt.where(WarehouseInventory.warehouse_id == almacen)
    if desde_sku:
        stmt = stmt.where(Sku.sku >= desde_sku)
    if hasta_sku:
        stmt = stmt.where(Sku.sku <= hasta_sku)
    stmt = stmt.order_by(Sku.sku.asc(), WarehouseInventory.warehouse_id.asc())

    rows = (await session.execute(stmt)).all()
    items = [
        InventoryRowOut.model_validate(
            {
                "codigo": sku.sku,
                "descripcion": sku.description,
                "um": sku.unit_of_measure,
                "categoria": sku.categoria,
                "tipo": sku.tipo,
                "stock_actual": inventory.on_hand_quantity,
                "stock_minimo": sku.min_stock,
                "alerta_stock": (
                    sku.min_stock is not None
                    and inventory.on_hand_quantity <= sku.min_stock
                ),
                "almacen": warehouse.name,
                "almacen_id": warehouse.warehouse_id,
            }
        )
        for sku, inventory, warehouse in rows
    ]
    return InventoryListOut.model_validate({"items": items})
