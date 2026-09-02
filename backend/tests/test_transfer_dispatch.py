import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.db import SessionLocal, engine
from app.errors import (
    BusinessRuleError,
    TransferNotFoundError,
    TransferStateConflictError,
)
from app.models import AuditLog, StockMovement, StockTransfer, TransferLineItem
from app.services.transfer import TransferService

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


async def _create_transfer(status: str = "APPROVED", lines: list[tuple[str, int]] | None = None):
    lines = lines or [("SKU-A", 20)]
    async with SessionLocal() as session:
        async with session.begin():
            transfer = StockTransfer(
                idempotency_key=uuid4().hex[:64],
                actor_id="actor-x",
                source_warehouse_id="WH-1",
                destination_warehouse_id="WH-2",
                status=status,
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
            return transfer.transfer_id


async def _state(transfer_id) -> str:
    async with SessionLocal() as session:
        async with session.begin():
            return (
                await session.execute(
                    select(StockTransfer.status).where(
                        StockTransfer.transfer_id == transfer_id
                    )
                )
            ).scalar_one()


async def _counts() -> tuple[int, int, int, int]:
    async with SessionLocal() as session:
        async with session.begin():
            movements = (
                await session.execute(select(func.count()).select_from(StockMovement))
            ).scalar_one()
            audits = (
                await session.execute(select(func.count()).select_from(AuditLog))
            ).scalar_one()
            sku_a = (
                await session.execute(
                    text(
                        "SELECT on_hand_quantity FROM warehouse_inventory "
                        "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-A'"
                    )
                )
            ).scalar_one()
            sku_b = (
                await session.execute(
                    text(
                        "SELECT on_hand_quantity FROM warehouse_inventory "
                        "WHERE warehouse_id = 'WH-1' AND sku = 'SKU-B'"
                    )
                )
            ).scalar_one()
            return movements, audits, sku_a, sku_b


@pytest.mark.asyncio
async def test_concurrent_double_dispatch_exactly_one_success_one_conflict() -> None:
    await _seed()
    transfer_id = await _create_transfer()

    async def attempt() -> str:
        try:
            async with SessionLocal() as session:
                async with session.begin():
                    await TransferService.dispatch(
                        session, transfer_id=transfer_id, actor="actor-x"
                    )
            return "ok"
        except TransferStateConflictError:
            return "conflict"

    results = sorted(await asyncio.gather(attempt(), attempt()))
    assert results == ["conflict", "ok"]

    assert await _state(transfer_id) == "IN_TRANSIT"
    movements, audits, sku_a, _ = await _counts()
    assert movements == 1
    assert audits == 1
    assert sku_a == 30


@pytest.mark.asyncio
async def test_dispatch_replay_after_completion_conflicts_without_double_apply() -> None:
    await _seed()
    transfer_id = await _create_transfer()

    async with SessionLocal() as session:
        async with session.begin():
            await TransferService.dispatch(session, transfer_id=transfer_id, actor="actor-x")

    with pytest.raises(TransferStateConflictError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.dispatch(session, transfer_id=transfer_id, actor="actor-x")

    assert exc_info.value.current_status == "IN_TRANSIT"
    movements, audits, sku_a, _ = await _counts()
    assert (movements, audits, sku_a) == (1, 1, 30)


@pytest.mark.asyncio
async def test_dispatch_illegal_state_conflicts() -> None:
    await _seed()
    transfer_id = await _create_transfer(status="PENDING_APPROVAL")

    with pytest.raises(TransferStateConflictError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.dispatch(session, transfer_id=transfer_id, actor="actor-x")

    assert exc_info.value.current_status == "PENDING_APPROVAL"
    assert await _state(transfer_id) == "PENDING_APPROVAL"
    movements, audits, sku_a, _ = await _counts()
    assert (movements, audits, sku_a) == (0, 0, 50)


@pytest.mark.asyncio
async def test_dispatch_insufficient_stock_rolls_back_entire_transfer() -> None:
    await _seed()
    transfer_id = await _create_transfer(lines=[("SKU-A", 20), ("SKU-B", 30)])

    with pytest.raises(BusinessRuleError) as exc_info:
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.dispatch(session, transfer_id=transfer_id, actor="actor-x")

    coordinates = exc_info.value.coordinates
    assert [c["sku"] for c in coordinates] == ["SKU-B"]

    assert await _state(transfer_id) == "APPROVED"
    movements, audits, sku_a, sku_b = await _counts()
    assert (movements, audits, sku_a, sku_b) == (0, 0, 50, 10)


@pytest.mark.asyncio
async def test_dispatch_unknown_transfer_not_found() -> None:
    with pytest.raises(TransferNotFoundError):
        async with SessionLocal() as session:
            async with session.begin():
                await TransferService.dispatch(session, transfer_id=uuid4(), actor="actor-x")
