import uuid
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db import engine
from app.main import app

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
                "VALUES ('WH-1', 'W1'), ('WH-2', 'W2'), ('WH-3', 'W3'), "
                "('WH-4', 'W4') "
                "ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text("INSERT INTO skus (sku) VALUES ('SKU-A') ON CONFLICT DO NOTHING")
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 200), ('WH-2', 'SKU-A', 0), "
                "('WH-3', 'SKU-A', 0), ('WH-4', 'SKU-A', 0) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = "
                "EXCLUDED.on_hand_quantity"
            )
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
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id, granted_by) "
                "VALUES ('ops-1', 'WH-1', 'admin'), ('ops-2', 'WH-2', 'admin') "
                "ON CONFLICT DO NOTHING"
            )
        )


def _headers(actor: str) -> dict:
    return {"X-Actor": actor, "Idempotency-Key": uuid.uuid4().hex[:64]}


def _payload(**overrides) -> dict:
    payload = {
        "source_warehouse_id": "WH-1",
        "destination_warehouse_id": "WH-2",
        "lines": [{"sku": "SKU-A", "quantity": 10}],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_requires_scope_on_both_warehouses(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    response = await client.post(
        "/api/v1/stock-transfers",
        json=_payload(),
        headers=_headers("ops-1"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    assert response.json()["error"]["required_scope"] == ["WH-2"]

    listed = await client.get("/api/v1/stock-transfers", headers=_headers("ops-1"))
    assert listed.json()["transfers"] == []


@pytest.mark.asyncio
async def test_list_filters_by_actor_scope(client: httpx.AsyncClient) -> None:
    await _seed()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('both', 'WH-1'), ('both', 'WH-2')"
            )
        )

    in_scope = await client.post(
        "/api/v1/stock-transfers",
        json=_payload(source_warehouse_id="WH-1", destination_warehouse_id="WH-2"),
        headers=_headers("both"),
    )
    assert in_scope.status_code == 201

    out_of_scope = await client.post(
        "/api/v1/stock-transfers",
        json=_payload(source_warehouse_id="WH-3", destination_warehouse_id="WH-3"),
        headers=_headers("both"),
    )
    assert out_of_scope.status_code == 403

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO stock_transfers (transfer_id, idempotency_key, actor_id, "
                "source_warehouse_id, destination_warehouse_id, status, requested_by) "
                "VALUES (gen_random_uuid(), 'foreign-key-1', 'other-actor', "
                "'WH-3', 'WH-4', 'APPROVED', 'other-actor')"
            )
        )

    listed = await client.get("/api/v1/stock-transfers", headers=_headers("both"))
    transfers = listed.json()["transfers"]
    assert len(transfers) == 1
    assert transfers[0]["transfer_id"] == in_scope.json()["transfer_id"]

    as_ops1 = await client.get("/api/v1/stock-transfers", headers=_headers("ops-1"))
    ops1_transfers = as_ops1.json()["transfers"]
    assert all(
        t["source_warehouse_id"] == "WH-1" or t["destination_warehouse_id"] == "WH-1"
        for t in ops1_transfers
    )


@pytest.mark.asyncio
async def test_detail_out_of_scope_returns_404_not_403(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('creator', 'WH-2'), ('creator', 'WH-3')"
            )
        )

    created = await client.post(
        "/api/v1/stock-transfers",
        json=_payload(source_warehouse_id="WH-2", destination_warehouse_id="WH-3"),
        headers=_headers("creator"),
    )
    assert created.status_code == 201
    transfer_id = created.json()["transfer_id"]

    assert (
        await client.get(
            f"/api/v1/stock-transfers/{transfer_id}", headers=_headers("creator")
        )
    ).status_code == 200

    as_ops1 = await client.get(
        f"/api/v1/stock-transfers/{transfer_id}", headers=_headers("ops-1")
    )
    assert as_ops1.status_code == 404


@pytest.mark.asyncio
async def test_dispatch_requires_source_scope(client: httpx.AsyncClient) -> None:
    await _seed()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('both', 'WH-1'), ('both', 'WH-2')"
            )
        )

    created = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("both")
    )
    transfer_id = created.json()["transfer_id"]

    forbidden = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers("ops-2")
    )
    assert forbidden.status_code == 403

    ok = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers("ops-1")
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "IN_TRANSIT"


@pytest.mark.asyncio
async def test_receive_requires_destination_scope(client: httpx.AsyncClient) -> None:
    await _seed()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('both', 'WH-1'), ('both', 'WH-2')"
            )
        )

    created = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("both")
    )
    transfer_id = created.json()["transfer_id"]
    line_id = created.json()["lines"][0]["line_id"]

    assert (
        await client.post(
            f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers("both")
        )
    ).status_code == 200

    forbidden = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/receive",
        json=[{"line_id": line_id, "received_quantity": 10}],
        headers=_headers("ops-1"),
    )
    assert forbidden.status_code == 403

    ok = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/receive",
        json=[{"line_id": line_id, "received_quantity": 10}],
        headers=_headers("ops-2"),
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "RECEIVED"


@pytest.mark.asyncio
async def test_cancel_allowed_for_creator_and_scoped_operator_only(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('both', 'WH-1'), ('both', 'WH-2')"
            )
        )

    created = await client.post(
        "/api/v1/stock-transfers", json=_payload(), headers=_headers("both")
    )
    transfer_id = created.json()["transfer_id"]

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('stranger', 'WH-3')"
            )
        )

    stranger = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/cancel", headers=_headers("stranger")
    )
    assert stranger.status_code == 403

    scoped_operator = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/cancel", headers=_headers("ops-2")
    )
    assert scoped_operator.status_code == 200
    assert scoped_operator.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_actor_without_scopes_gets_403_and_empty_list(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    response = await client.post(
        "/api/v1/stock-transfers",
        json=_payload(),
        headers=_headers("nobody"),
    )
    assert response.status_code == 403

    listed = await client.get("/api/v1/stock-transfers", headers=_headers("nobody"))
    assert listed.status_code == 200
    assert listed.json()["transfers"] == []
