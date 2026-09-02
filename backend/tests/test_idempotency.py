import asyncio
import uuid
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.db import engine
from app.main import app
from app.models import AuditLog, StockTransfer, TransferLineItem

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


@pytest.fixture(scope="module")
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


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
                "DELETE FROM stock_movements; DELETE FROM audit_logs; "
                "DELETE FROM mfa_attempts; DELETE FROM mfa_elevations; "
                "DELETE FROM transfer_line_items; DELETE FROM stock_transfers; "
                "DELETE FROM user_warehouse_scopes;"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('actor-a', 'WH-1'), ('actor-a', 'WH-2'), "
                "('actor-b', 'WH-1'), ('actor-b', 'WH-2')"
            )
        )


def _headers(actor: str, key: str) -> dict:
    return {"X-Actor": actor, "Idempotency-Key": key}


def _payload() -> dict:
    return {
        "source_warehouse_id": "WH-1",
        "destination_warehouse_id": "WH-2",
        "lines": [{"sku": "SKU-A", "quantity": 10}],
    }


async def _rows() -> tuple[int, int, int]:
    async with engine.begin() as conn:
        transfers = (
            await conn.execute(select(func.count()).select_from(StockTransfer))
        ).scalar_one()
        lines = (
            await conn.execute(select(func.count()).select_from(TransferLineItem))
        ).scalar_one()
        audits = (
            await conn.execute(select(func.count()).select_from(AuditLog))
        ).scalar_one()
        return transfers, lines, audits


@pytest.mark.asyncio
async def test_double_post_returns_original_with_no_new_rows(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    key = uuid.uuid4().hex

    first = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("actor-a", key)
    )
    assert first.status_code == 201
    first_body = first.json()

    second = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("actor-a", key)
    )
    assert second.status_code == 200
    assert second.json()["transfer_id"] == first_body["transfer_id"]
    assert second.json()["status"] == first_body["status"]

    assert await _rows() == (1, 1, 1)


@pytest.mark.asyncio
async def test_cross_actor_key_reuse_returns_409_without_disclosure(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    key = uuid.uuid4().hex

    first = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("actor-a", key)
    )
    assert first.status_code == 201

    conflict = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("actor-b", key)
    )
    assert conflict.status_code == 409
    body = conflict.json()
    assert body["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert "transfer_id" not in body
    assert "transfer_id" not in body["error"]

    assert await _rows() == (1, 1, 1)


@pytest.mark.asyncio
async def test_invalid_idempotency_keys_rejected_422(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    for bad_key in ["", "a" * 65, "bad key!", "key\x00inject", "key.with.dot"]:
        response = await client.post(
            "/api/v1/stock-transfers",
            json=_payload(),
            headers=_headers("actor-a", bad_key),
        )
        assert response.status_code == 422, f"key={bad_key!r} got {response.status_code}"

    assert await _rows() == (0, 0, 0)


@pytest.mark.asyncio
async def test_concurrent_same_key_posts_create_exactly_one_transfer(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    key = uuid.uuid4().hex

    async def post() -> httpx.Response:
        return await client.post(
            "/api/v1/stock-transfers",
            json=_payload(),
            headers=_headers("actor-a", key),
        )

    first, second = await asyncio.gather(post(), post())
    assert first.status_code in (200, 201)
    assert second.status_code in (200, 201)
    assert first.json()["transfer_id"] == second.json()["transfer_id"]

    assert await _rows() == (1, 1, 1)
