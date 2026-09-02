import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.db import SessionLocal, engine
from app.errors import BusinessRuleError
from app.models import AuditLog, FleetAllocation, StockMovement
from app.services.inventory import AdjustmentItem, InventoryService

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


async def _seed_inventory() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('WH-1', 'W1'), ('WH-2', 'W2') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text("INSERT INTO skus (sku) VALUES ('SKU-A'), ('SKU-B') ON CONFLICT DO NOTHING")
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 0), ('WH-2', 'SKU-A', 0), "
                "('WH-1', 'SKU-B', 100), ('WH-2', 'SKU-B', 0) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = "
                "EXCLUDED.on_hand_quantity"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM stock_movements; DELETE FROM audit_logs; "
                "DELETE FROM fleet_allocations;"
            )
        )
        await conn.execute(
            text("INSERT INTO vehicles (vehicle_id) VALUES ('V-1') ON CONFLICT DO NOTHING")
        )


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.asyncio
async def test_ten_concurrent_adjustments_exact_balance() -> None:
    await _seed_inventory()

    async def adjust_once() -> None:
        async with SessionLocal() as session:
            async with session.begin():
                await InventoryService.adjust_stock(
                    session,
                    warehouse_id="WH-1",
                    sku="SKU-A",
                    quantity_change=5,
                    actor="actor-conc",
                )

    await asyncio.gather(*(adjust_once() for _ in range(10)))

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
                )
            )
            assert result.scalar_one() == 50
            assert await _count(session, StockMovement) == 10
            assert await _count(session, AuditLog) == 10


@pytest.mark.asyncio
async def test_insufficient_stock_rolls_back_without_movement() -> None:
    await _seed_inventory()

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await InventoryService.adjust_stock(
                    session,
                    warehouse_id="WH-1",
                    sku="SKU-B",
                    quantity_change=-101,
                    actor="actor-insufficient",
                )

    assert exc_info.value.to_http_detail()["error"]["code"] == "BUSINESS_RULE_VIOLATION"
    assert exc_info.value.coordinates[0]["on_hand"] == 100

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-B'"
                )
            )
            assert result.scalar_one() == 100
            assert await _count(session, StockMovement) == 0
            assert await _count(session, AuditLog) == 0


@pytest.mark.asyncio
async def test_bulk_adjustment_all_or_nothing_with_coordinates() -> None:
    await _seed_inventory()

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await InventoryService.adjust_stock_bulk(
                    session,
                    [
                        AdjustmentItem("WH-1", "SKU-A", 10),
                        AdjustmentItem("WH-1", "NO-SKU", 5),
                        AdjustmentItem("WH-1", "SKU-B", -200),
                    ],
                    actor="actor-bulk",
                )

    detail = exc_info.value.to_http_detail()
    assert [c["line_index"] for c in detail["error"]["coordinates"]] == [1, 2]

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
                )
            )
            assert result.scalar_one() == 0
            assert await _count(session, StockMovement) == 0
            assert await _count(session, AuditLog) == 0


@pytest.mark.asyncio
async def test_bulk_adjustment_applies_when_valid() -> None:
    await _seed_inventory()

    async with SessionLocal() as session:
        async with session.begin():
            movements = await InventoryService.adjust_stock_bulk(
                session,
                [
                    AdjustmentItem("WH-1", "SKU-A", 10),
                    AdjustmentItem("WH-1", "SKU-B", -20),
                ],
                actor="actor-bulk-ok",
            )
            assert len(movements) == 2

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
                )
            )
            assert result.scalar_one() == 10
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-B'"
                )
            )
            assert result.scalar_one() == 80
            assert await _count(session, StockMovement) == 2
            assert await _count(session, AuditLog) == 1


@pytest.mark.asyncio
async def test_fleet_allocation_deducts_and_records() -> None:
    await _seed_inventory()

    async with SessionLocal() as session:
        async with session.begin():
            allocation = await InventoryService.allocate_to_vehicle(
                session,
                vehicle_id="V-1",
                warehouse_id="WH-1",
                sku="SKU-B",
                quantity=30,
                actor="actor-fleet",
            )
            assert allocation.allocation_id is not None

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "SELECT on_hand_quantity FROM warehouse_inventory "
                    "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-B'"
                )
            )
            assert result.scalar_one() == 70
            assert await _count(session, FleetAllocation) == 1
            assert await _count(session, StockMovement) == 1
            assert await _count(session, AuditLog) == 1
