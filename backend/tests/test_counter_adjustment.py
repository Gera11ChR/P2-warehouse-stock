from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.models import StockMovement, StockTransfer, TransferLineItem
from app.services.transfer import ReceiveLine, TransferService

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


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
                "VALUES ('WH-1', 'SKU-A', 50), ('WH-2', 'SKU-A', 0) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = "
                "EXCLUDED.on_hand_quantity"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM stock_movements; DELETE FROM audit_logs; "
                "DELETE FROM mfa_attempts; DELETE FROM mfa_elevations; "
                "DELETE FROM transfer_line_items; DELETE FROM stock_transfers;"
            )
        )


async def _create_dispatched(dispatched: int) -> tuple:
    async with SessionLocal() as session:
        async with session.begin():
            transfer = StockTransfer(
                idempotency_key=uuid4().hex[:64],
                actor_id="actor-x",
                source_warehouse_id="WH-1",
                destination_warehouse_id="WH-2",
                status="APPROVED",
                requested_by="actor-x",
            )
            session.add(transfer)
            await session.flush()
            session.add(
                TransferLineItem(
                    transfer_id=transfer.transfer_id,
                    sku="SKU-A",
                    dispatched_quantity=dispatched,
                )
            )
            await session.flush()
            await TransferService.dispatch(
                session, transfer_id=transfer.transfer_id, actor="actor-x"
            )
            await session.flush()
            line = (
                await session.execute(
                    select(TransferLineItem).where(
                        TransferLineItem.transfer_id == transfer.transfer_id
                    )
                )
            ).scalar_one()
            return transfer.transfer_id, line.line_id


async def _ledger_snapshot() -> list[tuple]:
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
            return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


@pytest.mark.asyncio
async def test_shortage_produces_exactly_one_referencing_adjustment() -> None:
    await _seed()
    transfer_id, line_id = await _create_dispatched(20)
    before = await _ledger_snapshot()
    assert len(before) == 1

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_id, 8)],
                actor="actor-x",
            )

    after = await _ledger_snapshot()
    assert len(after) == 3

    out_row = after[0]
    in_row = after[1]
    adjustment = after[2]

    assert out_row[0:4] == before[0][0:4]
    assert in_row[1:4] == ("TRANSFER_IN", 20, "WH-2")
    assert adjustment[1] == "ADJUSTMENT"
    assert adjustment[2] == -12
    assert adjustment[3] == "WH-2"
    assert adjustment[4] == in_row[0]

    async with SessionLocal() as session:
        async with session.begin():
            dest = (
                await session.execute(
                    text(
                        "SELECT on_hand_quantity FROM warehouse_inventory "
                        "WHERE warehouse_id = 'WH-2' AND sku = 'SKU-A'"
                    )
                )
            ).scalar_one()
            assert dest == 8


@pytest.mark.asyncio
async def test_full_receive_produces_no_adjustment() -> None:
    await _seed()
    transfer_id, line_id = await _create_dispatched(20)

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_id, 20)],
                actor="actor-x",
            )

    after = await _ledger_snapshot()
    assert [row[1] for row in after] == ["TRANSFER_OUT", "TRANSFER_IN"]


@pytest.mark.asyncio
async def test_total_loss_zero_receive_records_full_write_off() -> None:
    await _seed()
    transfer_id, line_id = await _create_dispatched(20)

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_id, 0)],
                actor="actor-x",
            )

    after = await _ledger_snapshot()
    assert len(after) == 3
    assert after[1][1:3] == ("TRANSFER_IN", 20)
    assert after[2][1:3] == ("ADJUSTMENT", -20)
    assert after[2][4] == after[1][0]

    async with SessionLocal() as session:
        async with session.begin():
            dest = (
                await session.execute(
                    text(
                        "SELECT on_hand_quantity FROM warehouse_inventory "
                        "WHERE warehouse_id = 'WH-2' AND sku = 'SKU-A'"
                    )
                )
            ).scalar_one()
            assert dest == 0
