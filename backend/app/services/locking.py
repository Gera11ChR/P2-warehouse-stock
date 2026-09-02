from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StockTransfer, WarehouseInventory

InventoryKey = tuple[str, str]


def build_inventory_lock_stmt(keys: list[InventoryKey]) -> Select:
    unique = sorted({(warehouse_id, sku) for warehouse_id, sku in keys})
    return (
        select(WarehouseInventory)
        .where(
            or_(
                *(
                    (WarehouseInventory.warehouse_id == warehouse_id)
                    & (WarehouseInventory.sku == sku)
                    for warehouse_id, sku in unique
                )
            )
        )
        .order_by(WarehouseInventory.warehouse_id.asc(), WarehouseInventory.sku.asc())
        .with_for_update()
    )


async def lock_inventory_rows(
    session: AsyncSession, keys: list[InventoryKey]
) -> dict[InventoryKey, WarehouseInventory]:
    unique = sorted({(warehouse_id, sku) for warehouse_id, sku in keys})
    if not unique:
        return {}
    rows = (
        (await session.execute(build_inventory_lock_stmt(keys))).scalars().all()
    )
    return {(row.warehouse_id, row.sku): row for row in rows}


async def lock_transfer_row(
    session: AsyncSession, transfer_id: UUID
) -> StockTransfer | None:
    stmt = (
        select(StockTransfer)
        .where(StockTransfer.transfer_id == transfer_id)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()
