import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.db import SessionLocal, engine
from app.errors import BusinessRuleError, TransferStateConflictError
from app.models import AuditLog, StockMovement, StockTransfer, TransferLineItem
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
            text("INSERT INTO skus (sku) VALUES ('SKU-A'), ('SKU-B') ON CONFLICT DO NOTHING")
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 50), ('WH-1', 'SKU-B', 10), "
                "('WH-2', 'SKU-A', 0), ('WH-2', 'SKU-B', 0) "
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


async def _create_dispatched_transfer(
    lines: list[tuple[str, int]] | None = None,
) -> tuple:
    lines = lines or [("SKU-A", 20)]
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
            for sku, quantity in lines:
                session.add(
                    TransferLineItem(
                        transfer_id=transfer.transfer_id,
                        sku=sku,
                        dispatched_quantity=quantity,
                    )
                )
            await session.flush()
            await TransferService.dispatch(
                session, transfer_id=transfer.transfer_id, actor="actor-x"
            )
            await session.flush()
            line_ids = [
                line.line_id
                for line in (
                    await session.execute(
                        select(TransferLineItem).where(
                            TransferLineItem.transfer_id == transfer.transfer_id
                        )
                    )
                ).scalars()
            ]
            return transfer.transfer_id, line_ids


async def _counts() -> tuple[int, int, int]:
    async with SessionLocal() as session:
        async with session.begin():
            movements = (
                await session.execute(select(func.count()).select_from(StockMovement))
            ).scalar_one()
            audits = (
                await session.execute(select(func.count()).select_from(AuditLog))
            ).scalar_one()
            dest = (
                await session.execute(
                    text(
                        "SELECT COALESCE(SUM(on_hand_quantity), 0) FROM warehouse_inventory "
                        "WHERE warehouse_id = 'WH-2'"
                    )
                )
            ).scalar_one()
            return movements, audits, dest


async def _status(transfer_id) -> str:
    async with SessionLocal() as session:
        async with session.begin():
            return (
                await session.execute(
                    select(StockTransfer.status).where(
                        StockTransfer.transfer_id == transfer_id
                    )
                )
            ).scalar_one()


@pytest.mark.asyncio
async def test_receive_full_credits_and_completes() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer()

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_ids[0], 20)],
                actor="actor-x",
            )

    assert await _status(transfer_id) == "RECEIVED"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (2, 2, 20)


@pytest.mark.asyncio
async def test_receive_over_quantity_rejected_with_coordinates_zero_credits() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer()

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.receive(
                    session,
                    transfer_id=transfer_id,
                    lines=[ReceiveLine(line_ids[0], 25)],
                    actor="actor-x",
                )

    coordinates = exc_info.value.coordinates
    assert coordinates[0]["field"] == "received_quantity"
    assert coordinates[0]["dispatched_quantity"] == 20
    assert await _status(transfer_id) == "IN_TRANSIT"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (1, 1, 0)


@pytest.mark.asyncio
async def test_receive_duplicate_line_rejected_zero_credits() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer()

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.receive(
                    session,
                    transfer_id=transfer_id,
                    lines=[
                        ReceiveLine(line_ids[0], 10),
                        ReceiveLine(line_ids[0], 10),
                    ],
                    actor="actor-x",
                )

    coordinates = exc_info.value.coordinates
    assert coordinates[0]["message"] == "duplicate line in receive payload"
    assert await _status(transfer_id) == "IN_TRANSIT"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (1, 1, 0)


@pytest.mark.asyncio
async def test_receive_foreign_line_rejected_zero_credits() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer()

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.receive(
                    session,
                    transfer_id=transfer_id,
                    lines=[ReceiveLine(999999, 5)],
                    actor="actor-x",
                )

    coordinates = exc_info.value.coordinates
    assert coordinates[0]["message"] == "line does not belong to this transfer"
    assert await _status(transfer_id) == "IN_TRANSIT"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (1, 1, 0)


@pytest.mark.asyncio
async def test_receive_missing_line_rejected_zero_credits() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer(
        lines=[("SKU-A", 20), ("SKU-B", 5)]
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.receive(
                    session,
                    transfer_id=transfer_id,
                    lines=[ReceiveLine(line_ids[0], 20)],
                    actor="actor-x",
                )

    coordinates = exc_info.value.coordinates
    assert coordinates[0]["message"] == "line missing from receive payload"
    assert await _status(transfer_id) == "IN_TRANSIT"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (2, 1, 0)


@pytest.mark.asyncio
async def test_receive_partial_quantity_allowed_and_received() -> None:
    await _seed()
    transfer_id, line_ids = await _create_dispatched_transfer()

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_ids[0], 8)],
                actor="actor-x",
            )

    assert await _status(transfer_id) == "RECEIVED"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (3, 2, 8)


@pytest.mark.asyncio
async def test_receive_illegal_state_conflicts() -> None:
    await _seed()
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
            transfer_id = transfer.transfer_id

    with pytest.raises(TransferStateConflictError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.receive(
                    session,
                    transfer_id=transfer_id,
                    lines=[ReceiveLine(1, 5)],
                    actor="actor-x",
                )

    assert exc_info.value.current_status == "APPROVED"
    assert await _status(transfer_id) == "APPROVED"


@pytest.mark.asyncio
async def test_receive_creates_missing_destination_inventory_row() -> None:
    await _seed()
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM warehouse_inventory WHERE warehouse_id = 'WH-2'")
        )
    transfer_id, line_ids = await _create_dispatched_transfer()

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.receive(
                session,
                transfer_id=transfer_id,
                lines=[ReceiveLine(line_ids[0], 20)],
                actor="actor-x",
            )

    assert await _status(transfer_id) == "RECEIVED"
    movements, audits, dest = await _counts()
    assert (movements, audits, dest) == (2, 2, 20)
