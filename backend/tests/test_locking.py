import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from app.db import SessionLocal, engine
from app.errors import BusinessRuleError
from app.services.locking import (
    build_inventory_lock_stmt,
    lock_inventory_rows,
    lock_transfer_row,
)

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


def test_lock_stmt_compiles_with_deterministic_order() -> None:
    stmt = build_inventory_lock_stmt([("WH-2", "SKU-B"), ("WH-1", "SKU-A")])
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert (
        "ORDER BY warehouse_inventory.warehouse_id ASC, warehouse_inventory.sku ASC"
        in sql
    )
    assert "FOR UPDATE" in sql


def test_business_rule_error_http_detail_shape() -> None:
    err = BusinessRuleError(
        "Insufficient stock",
        coordinates=[{"sku": "SKU-A", "warehouse_id": "WH-1"}],
    )
    detail = err.to_http_detail()
    assert detail["error"]["code"] == "BUSINESS_RULE_VIOLATION"
    assert detail["error"]["message"] == "Insufficient stock"
    assert detail["error"]["coordinates"] == [{"sku": "SKU-A", "warehouse_id": "WH-1"}]


@pytest.mark.asyncio
async def test_lock_acquisition_serializes_in_protocol_order() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('WH-1', 'W1'), ('WH-2', 'W2') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO skus (sku) VALUES ('SKU-A'), ('SKU-B') "
                "ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 10), ('WH-2', 'SKU-B', 20) "
                "ON CONFLICT DO NOTHING"
            )
        )

    async with SessionLocal() as session_a:
        await session_a.execute(text("SELECT 1"))
        rows_a = await lock_inventory_rows(
            session_a, [("WH-2", "SKU-B"), ("WH-1", "SKU-A")]
        )
        assert sorted(rows_a) == [("WH-1", "SKU-A"), ("WH-2", "SKU-B")]

        async def acquire_same_set() -> bool:
            async with SessionLocal() as session_b:
                await session_b.execute(text("SELECT 1"))
                rows_b = await lock_inventory_rows(
                    session_b, [("WH-2", "SKU-B"), ("WH-1", "SKU-A")]
                )
                assert sorted(rows_b) == [("WH-1", "SKU-A"), ("WH-2", "SKU-B")]
                return True

        task = asyncio.create_task(acquire_same_set())
        await asyncio.sleep(0.5)
        assert not task.done()

        await session_a.commit()
        assert await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio
async def test_lock_transfer_row_returns_none_when_missing() -> None:
    import uuid

    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
        row = await lock_transfer_row(session, uuid.uuid4())
        assert row is None
