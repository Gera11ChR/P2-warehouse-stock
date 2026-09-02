import uuid
from pathlib import Path

import httpx
import pyotp
import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.main import app
from app.schemas.transfer import (
    ReceiveLinePayload,
    TransferCreate,
    TransferLineCreate,
)
from app.services.mfa import provision_seed

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

FIXED_SEED = "JBSWY3DPEHPK3PXP"


async def _approve_headers(
    client: httpx.AsyncClient, actor: str, transfer_id: str
) -> dict:
    async with SessionLocal() as session:
        async with session.begin():
            await provision_seed(session, actor=actor, seed=FIXED_SEED)
    code = pyotp.TOTP(FIXED_SEED).now()
    response = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/elevations",
        json={"action": "APPROVE", "totp_code": code},
        headers={"X-Actor": actor},
    )
    assert response.status_code == 201, response.text
    return {
        "X-Actor": actor,
        "X-Elevation-Id": response.json()["elevation_id"],
    }


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
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'SKU-A', 200) "
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
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id, granted_by) "
                "VALUES ('actor-x', 'WH-1', 'admin'), ('actor-x', 'WH-2', 'admin') "
                "ON CONFLICT DO NOTHING"
            )
        )


def _headers() -> dict:
    return {
        "X-Actor": "actor-x",
        "Idempotency-Key": uuid.uuid4().hex[:64],
    }


def _create_payload(**overrides) -> dict:
    payload = {
        "source_warehouse_id": "WH-1",
        "destination_warehouse_id": "WH-2",
        "lines": [{"sku": "SKU-A", "quantity": 10}],
    }
    payload.update(overrides)
    return payload


def test_transfer_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TransferCreate.model_validate(_create_payload(hack="evil"))
    assert "extra_forbidden" in str(exc_info.value)


def test_transfer_create_rejects_server_derived_fields() -> None:
    for field, value in [
        ("status", "IN_TRANSIT"),
        ("transfer_id", str(uuid.uuid4())),
        ("requested_by", "hacker"),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("idempotency_key", "forged"),
    ]:
        with pytest.raises(ValidationError) as exc_info:
            TransferCreate.model_validate(_create_payload(**{field: value}))
        assert "extra_forbidden" in str(exc_info.value)


def test_transfer_line_create_rejects_unknown_and_bad_quantity() -> None:
    with pytest.raises(ValidationError):
        TransferLineCreate.model_validate({"sku": "SKU-A", "quantity": 5, "received_quantity": 3})
    with pytest.raises(ValidationError):
        TransferLineCreate.model_validate({"sku": "SKU-A", "quantity": 0})


def test_receive_line_payload_rejects_unknown_and_negative() -> None:
    with pytest.raises(ValidationError):
        ReceiveLinePayload.model_validate(
            {"line_id": 1, "received_quantity": 5, "sku": "SKU-A"}
        )
    with pytest.raises(ValidationError):
        ReceiveLinePayload.model_validate({"line_id": 1, "received_quantity": -1})


@pytest.mark.asyncio
async def test_create_transfer_endpoint_201(client: httpx.AsyncClient) -> None:
    await _seed()
    response = await client.post(
        "/api/v1/stock-transfers", json=_create_payload(), headers=_headers()
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["transfer_id"]
    assert body["lines"][0]["sku"] == "SKU-A"


@pytest.mark.asyncio
async def test_create_rejects_server_field_in_body(client: httpx.AsyncClient) -> None:
    await _seed()
    response = await client.post(
        "/api/v1/stock-transfers",
        json=_create_payload(status="IN_TRANSIT"),
        headers=_headers(),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_over_threshold_pending_then_approve_dispatch(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    response = await client.post(
        "/api/v1/stock-transfers",
        json=_create_payload(lines=[{"sku": "SKU-A", "quantity": 150}]),
        headers=_headers(),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING_APPROVAL"
    transfer_id = response.json()["transfer_id"]

    assert (
        await client.post(
            f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers()
        )
    ).status_code == 409

    approved = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve",
        headers=await _approve_headers(client, "actor-x", transfer_id),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    dispatched = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers()
    )
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "IN_TRANSIT"


@pytest.mark.asyncio
async def test_reject_endpoint(client: httpx.AsyncClient) -> None:
    await _seed()
    response = await client.post(
        "/api/v1/stock-transfers",
        json=_create_payload(lines=[{"sku": "SKU-A", "quantity": 150}]),
        headers=_headers(),
    )
    transfer_id = response.json()["transfer_id"]
    rejected = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/reject", headers=_headers()
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_cancel_endpoint_then_dispatch_conflict(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    response = await client.post(
        "/api/v1/stock-transfers", json=_create_payload(), headers=_headers()
    )
    transfer_id = response.json()["transfer_id"]
    cancelled = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/cancel", headers=_headers()
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (
        await client.post(
            f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers()
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_receive_endpoint_happy_path_and_validation(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    created = await client.post(
        "/api/v1/stock-transfers", json=_create_payload(), headers=_headers()
    )
    transfer_id = created.json()["transfer_id"]
    line_id = created.json()["lines"][0]["line_id"]

    assert (
        await client.post(
            f"/api/v1/stock-transfers/{transfer_id}/dispatch", headers=_headers()
        )
    ).status_code == 200

    over = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/receive",
        json=[{"line_id": line_id, "received_quantity": 999}],
        headers=_headers(),
    )
    assert over.status_code == 422

    received = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/receive",
        json=[{"line_id": line_id, "received_quantity": 10}],
        headers=_headers(),
    )
    assert received.status_code == 200
    assert received.json()["status"] == "RECEIVED"


@pytest.mark.asyncio
async def test_list_and_detail_endpoints(client: httpx.AsyncClient) -> None:
    await _seed()
    created = await client.post(
        "/api/v1/stock-transfers", json=_create_payload(), headers=_headers()
    )
    transfer_id = created.json()["transfer_id"]

    listed = await client.get("/api/v1/stock-transfers", headers=_headers())
    assert listed.status_code == 200
    assert any(t["transfer_id"] == transfer_id for t in listed.json()["transfers"])

    detail = await client.get(
        f"/api/v1/stock-transfers/{transfer_id}", headers=_headers()
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "APPROVED"

    assert (
        await client.get(
            f"/api/v1/stock-transfers/{uuid.uuid4()}", headers=_headers()
        )
    ).status_code == 404
