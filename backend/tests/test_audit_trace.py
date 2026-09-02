import uuid
from pathlib import Path

import httpx
import pyotp
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog
from app.services.mfa import provision_seed

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

FIXED_SEED = "JBSWY3DPEHPK3PXP"
TRACE = "trace-lifecycle-integration-1"


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
                "VALUES ('WH-1', 'SKU-A', 200), ('WH-2', 'SKU-A', 0) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = "
                "EXCLUDED.on_hand_quantity"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM mfa_attempts; DELETE FROM mfa_elevations; "
                "DELETE FROM user_mfa_seeds; DELETE FROM audit_logs; "
                "DELETE FROM stock_movements; DELETE FROM transfer_line_items; "
                "DELETE FROM stock_transfers; DELETE FROM user_warehouse_scopes;"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id) "
                "VALUES ('actor-x', 'WH-1'), ('actor-x', 'WH-2')"
            )
        )


async def _audit_rows() -> list[tuple[str, str, dict]]:
    async with SessionLocal() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(AuditLog.action, AuditLog.actor, AuditLog.details).order_by(
                        AuditLog.log_id
                    )
                )
            ).all()
            return [(row[0], row[1], row[2] or {}) for row in rows]


def _headers(actor: str, *, with_trace: bool = True) -> dict:
    headers = {"X-Actor": actor}
    if with_trace:
        headers["X-Trace-Id"] = TRACE
    return headers


@pytest.mark.asyncio
async def test_full_lifecycle_emits_one_traced_audit_row_per_transition(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    async with SessionLocal() as session:
        async with session.begin():
            await provision_seed(session, actor="actor-x", seed=FIXED_SEED)

    created = await client.post(
        "/api/v1/stock-transfers",
        json={
            "source_warehouse_id": "WH-1",
            "destination_warehouse_id": "WH-2",
            "lines": [{"sku": "SKU-A", "quantity": 150}],
        },
        headers={**_headers("actor-x"), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert created.status_code == 201
    transfer_id = created.json()["transfer_id"]
    line_id = created.json()["lines"][0]["line_id"]

    code = pyotp.TOTP(FIXED_SEED).now()
    elevation = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/elevations",
        json={"action": "APPROVE", "totp_code": code},
        headers=_headers("actor-x"),
    )
    assert elevation.status_code == 201
    elevation_id = elevation.json()["elevation_id"]

    approved = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve",
        headers={**_headers("actor-x"), "X-Elevation-Id": elevation_id},
    )
    assert approved.status_code == 200

    dispatched = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/dispatch",
        headers=_headers("actor-x"),
    )
    assert dispatched.status_code == 200

    received = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/receive",
        json=[{"line_id": line_id, "received_quantity": 150}],
        headers=_headers("actor-x"),
    )
    assert received.status_code == 200

    rows = await _audit_rows()
    actions = [row[0] for row in rows]

    for expected in [
        "TRANSFER_CREATE",
        "TOTP_VERIFY_OK",
        "MFA_ELEVATION_ISSUED",
        "MFA_ELEVATION_CONSUMED",
        "TRANSFER_APPROVE",
        "TRANSFER_DISPATCH",
        "TRANSFER_RECEIVE",
    ]:
        assert actions.count(expected) == 1, f"{expected} count != 1 in {actions}"

    for action, actor, details in rows:
        assert actor == "actor-x", (action, actor)
        assert details["trace_id"] == TRACE, (action, details)

    create_row = next(row for row in rows if row[0] == "TRANSFER_CREATE")
    assert create_row[2]["lines"] == [{"sku": "SKU-A", "quantity": 150}]
    dispatch_row = next(row for row in rows if row[0] == "TRANSFER_DISPATCH")
    assert dispatch_row[2]["lines"] == [{"sku": "SKU-A", "dispatched_quantity": 150}]
    receive_row = next(row for row in rows if row[0] == "TRANSFER_RECEIVE")
    assert receive_row[2]["lines"] == [
        {"line_id": line_id, "sku": "SKU-A", "received_quantity": 150}
    ]


@pytest.mark.asyncio
async def test_authorization_denial_is_audited_with_trace(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    response = await client.post(
        "/api/v1/stock-transfers",
        json={
            "source_warehouse_id": "WH-1",
            "destination_warehouse_id": "WH-2",
            "lines": [{"sku": "SKU-A", "quantity": 10}],
        },
        headers={
            "X-Actor": "no-scope-actor",
            "X-Trace-Id": "trace-deny-1",
            "Idempotency-Key": uuid.uuid4().hex,
        },
    )
    assert response.status_code == 403

    rows = await _audit_rows()
    denied = [row for row in rows if row[0] == "AUTHZ_DENIED"]
    assert len(denied) == 1
    assert denied[0][1] == "no-scope-actor"
    assert denied[0][2]["trace_id"] == "trace-deny-1"
    assert denied[0][2]["path"] == "/api/v1/stock-transfers"


@pytest.mark.asyncio
async def test_generated_trace_id_returned_and_stamped(
    client: httpx.AsyncClient,
) -> None:
    await _seed()

    response = await client.post(
        "/api/v1/stock-transfers",
        json={
            "source_warehouse_id": "WH-1",
            "destination_warehouse_id": "WH-2",
            "lines": [{"sku": "SKU-A", "quantity": 10}],
        },
        headers={
            "X-Actor": "actor-x",
            "Idempotency-Key": uuid.uuid4().hex,
        },
    )
    assert response.status_code == 201
    generated = response.headers.get("X-Trace-Id")
    assert generated

    rows = await _audit_rows()
    create_rows = [row for row in rows if row[0] == "TRANSFER_CREATE"]
    assert len(create_rows) == 1
    assert create_rows[0][2]["trace_id"] == generated
