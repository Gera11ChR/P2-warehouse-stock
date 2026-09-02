from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.config import DATABASE_URL
from app.db import SessionLocal, engine
from app.models import StockMovement, StockTransfer, TransferLineItem
from app.services.transfer import CreateLine, ReceiveLine, TransferService

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
SYNC_URL = DATABASE_URL.replace("+psycopg://", "://", 1)


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('WH-1', 'W1'), ('WH-2', 'W2') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text("INSERT INTO skus (sku) VALUES ('SKU-A') ON CONFLICT DO NOTHING")
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 100), ('WH-2', 'SKU-A', 30) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = "
                "EXCLUDED.on_hand_quantity"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM mfa_attempts; DELETE FROM mfa_elevations; "
                "DELETE FROM audit_logs; DELETE FROM stock_movements; "
                "DELETE FROM transfer_line_items; DELETE FROM stock_transfers;"
            )
        )


async def _balances() -> dict[str, int]:
    async with SessionLocal() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    text(
                        "SELECT warehouse_id, on_hand_quantity "
                        "FROM warehouse_inventory WHERE sku = 'SKU-A'"
                    )
                )
            ).all()
            return {row[0]: row[1] for row in rows}


async def _in_transit_quantity(transfer_id) -> int:
    async with SessionLocal() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(
                        TransferLineItem.dispatched_quantity,
                        TransferLineItem.received_quantity,
                    ).where(TransferLineItem.transfer_id == transfer_id)
                )
            ).all()
            return sum(
                dispatched - (received or 0) for dispatched, received in rows
            )


async def _movement_sum(warehouse_id: str, sku: str) -> int:
    async with SessionLocal() as session:
        async with session.begin():
            return (
                await session.execute(
                    select(
                        text("COALESCE(SUM(quantity_change), 0)")
                    ).select_from(StockMovement).where(
                        StockMovement.warehouse_id == warehouse_id,
                        StockMovement.sku == sku,
                    )
                )
            ).scalar_one()


async def _movement_snapshot() -> list[tuple]:
    async with SessionLocal() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(
                        StockMovement.movement_id,
                        StockMovement.movement_type,
                        StockMovement.quantity_change,
                        StockMovement.warehouse_id,
                        StockMovement.references_movement_id,
                    ).order_by(StockMovement.movement_id)
                )
            ).all()
            return [tuple(row) for row in rows]


@pytest.mark.asyncio
async def test_material_conservation_through_lifecycle() -> None:
    await _seed()

    assert await _balances() == {"WH-1": 100, "WH-2": 30}
    initial_total = 130

    async with SessionLocal() as session:
        async with session.begin():
            transfer, created = await TransferService.create(
                session,
                source_warehouse_id="WH-1",
                destination_warehouse_id="WH-2",
                lines=[CreateLine(sku="SKU-A", quantity=25)],
                actor="actor-inv",
                idempotency_key=uuid4().hex[:64],
            )
            assert created is True
            transfer_id = transfer.transfer_id
            line = (
                await session.execute(
                    select(TransferLineItem).where(
                        TransferLineItem.transfer_id == transfer_id
                    )
                )
            ).scalar_one()
            line_id = line.line_id

    assert await _movement_sum("WH-1", "SKU-A") == 0

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.dispatch(
                session, transfer_id=transfer_id, actor="actor-inv"
            )

    balances = await _balances()
    assert balances["WH-1"] == 75
    assert balances["WH-2"] == 30
    assert all(value >= 0 for value in balances.values())
    assert await _in_transit_quantity(transfer_id) == 25
    assert sum(balances.values()) + await _in_transit_quantity(transfer_id) == initial_total
    assert await _movement_sum("WH-1", "SKU-A") == -25

    async with SessionLocal() as session:
        async with session.begin():
            status = (
                await session.execute(
                    select(StockTransfer.status).where(
                        StockTransfer.transfer_id == transfer_id
                    )
                )
            ).scalar_one()
            assert status == "IN_TRANSIT"

    snapshot_after_dispatch = await _movement_snapshot()

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_id=line_id, received_quantity=20)],
                actor="actor-inv",
            )

    balances = await _balances()
    assert balances["WH-1"] == 75
    assert balances["WH-2"] == 50
    assert all(value >= 0 for value in balances.values())

    async with SessionLocal() as session:
        async with session.begin():
            adjustment_sum = (
                await session.execute(
                    select(text("COALESCE(SUM(quantity_change), 0)")).select_from(
                        StockMovement
                    ).where(
                        StockMovement.transfer_id == transfer_id,
                        StockMovement.movement_type == "ADJUSTMENT",
                    )
                )
            ).scalar_one()
            assert adjustment_sum == -5

    assert sum(balances.values()) == initial_total + adjustment_sum

    snapshot_after_receive = await _movement_snapshot()
    assert snapshot_after_receive[: len(snapshot_after_dispatch)] == snapshot_after_dispatch

    assert await _movement_sum("WH-1", "SKU-A") == -25
    assert await _movement_sum("WH-2", "SKU-A") == 20

    async with SessionLocal() as session:
        async with session.begin():
            final_source = (await _balances())["WH-1"]
            assert final_source - 100 == await _movement_sum("WH-1", "SKU-A")
            assert (await _balances())["WH-2"] - 30 == await _movement_sum("WH-2", "SKU-A")


def test_db_check_constraint_rejects_negative_balance() -> None:
    with psycopg.connect(SYNC_URL, autocommit=True) as conn:
        conn.execute(
            "UPDATE warehouse_inventory SET on_hand_quantity = 100 "
            "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE warehouse_inventory SET on_hand_quantity = -1 "
                "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
            )
        conn.execute(
            "UPDATE warehouse_inventory SET on_hand_quantity = 100 "
            "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
        )


@pytest.mark.asyncio
async def test_insufficient_dispatch_never_creates_negative_balance() -> None:
    await _seed()

    async with SessionLocal() as session:
        async with session.begin():
            transfer, _ = await TransferService.create(
                session,
                source_warehouse_id="WH-2",
                destination_warehouse_id="WH-1",
                lines=[CreateLine(sku="SKU-A", quantity=999)],
                actor="actor-inv",
                idempotency_key=uuid4().hex[:64],
            )
            transfer_id = transfer.transfer_id
            await TransferService.approve(
                session, transfer_id=transfer_id, actor="admin-inv"
            )

    from app.errors import BusinessRuleError

    with pytest.raises(BusinessRuleError):
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.dispatch(
                    session, transfer_id=transfer_id, actor="actor-inv"
                )

    balances = await _balances()
    assert balances == {"WH-1": 100, "WH-2": 30}
    assert all(value >= 0 for value in balances.values())
    assert await _movement_sum("WH-2", "SKU-A") == 0
