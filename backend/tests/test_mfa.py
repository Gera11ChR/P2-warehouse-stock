import uuid
from pathlib import Path

import httpx
import pyotp
import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import select, text

from app.db import SessionLocal, engine
from app.main import app
from app.models import AuditLog, UserMfaSeed
from app.schemas.transfer import MfaElevationRequest
from app.services.mfa import provision_seed

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

FIXED_SEED = "JBSWY3DPEHPK3PXP"


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


def _headers(actor: str = "actor-x", key: str | None = None) -> dict:
    headers = {"X-Actor": actor}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


async def _create_pending(client: httpx.AsyncClient, actor: str = "actor-x") -> str:
    response = await client.post(
        "/api/v1/stock-transfers",
        json={
            "source_warehouse_id": "WH-1",
            "destination_warehouse_id": "WH-2",
            "lines": [{"sku": "SKU-A", "quantity": 150}],
        },
        headers=_headers(actor, uuid.uuid4().hex),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING_APPROVAL"
    return response.json()["transfer_id"]


async def _provision(actor: str = "actor-x") -> None:
    async with SessionLocal() as session:
        async with session.begin():
            await provision_seed(session, actor=actor, seed=FIXED_SEED)


async def _elevate(
    client: httpx.AsyncClient, transfer_id: str, *, actor: str = "actor-x", code: str | None = None
) -> httpx.Response:
    if code is None:
        code = pyotp.TOTP(FIXED_SEED).now()
    return await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/elevations",
        json={"action": "APPROVE", "totp_code": code},
        headers=_headers(actor),
    )


async def _audit_actions() -> list[str]:
    async with SessionLocal() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(AuditLog.action).order_by(AuditLog.log_id)
                )
            ).scalars()
            return list(rows)


@pytest.mark.asyncio
async def test_approve_without_elevation_returns_403(client: httpx.AsyncClient) -> None:
    await _seed()
    transfer_id = await _create_pending(client)

    response = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve", headers=_headers()
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MFA_REQUIRED"


@pytest.mark.asyncio
async def test_approve_with_valid_elevation_succeeds_single_use(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    transfer_id = await _create_pending(client)
    await _provision()

    elevation = await _elevate(client, transfer_id)
    assert elevation.status_code == 201
    elevation_id = elevation.json()["elevation_id"]

    approved = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve",
        headers={"X-Actor": "actor-x", "X-Elevation-Id": elevation_id},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    reused = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve",
        headers={"X-Actor": "actor-x", "X-Elevation-Id": elevation_id},
    )
    assert reused.status_code == 403
    assert reused.json()["error"]["code"] == "ELEVATION_INVALID"


@pytest.mark.asyncio
async def test_invalid_totp_code_rejected_and_audited(
    client: httpx.AsyncClient,
) -> None:
    await _seed()
    transfer_id = await _create_pending(client)
    await _provision()

    response = await _elevate(client, transfer_id, code="000000")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TOTP_INVALID"

    actions = await _audit_actions()
    assert "TOTP_VERIFY_FAILED" in actions


@pytest.mark.asyncio
async def test_lockout_after_max_failed_attempts(client: httpx.AsyncClient) -> None:
    await _seed()
    transfer_id = await _create_pending(client)
    await _provision()

    for _ in range(5):
        response = await _elevate(client, transfer_id, code="000000")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TOTP_INVALID"

    good_code = pyotp.TOTP(FIXED_SEED).now()
    locked = await _elevate(client, transfer_id, code=good_code)
    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "TOTP_LOCKED"

    actions = await _audit_actions()
    assert actions.count("TOTP_VERIFY_FAILED") == 5
    assert "TOTP_LOCKED" in actions


@pytest.mark.asyncio
async def test_expired_elevation_rejected(client: httpx.AsyncClient) -> None:
    await _seed()
    transfer_id = await _create_pending(client)
    await _provision()

    elevation = await _elevate(client, transfer_id)
    elevation_id = elevation.json()["elevation_id"]

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE mfa_elevations SET expires_at = now() - interval '1 minute' "
                "WHERE elevation_id = :eid"
            ),
            {"eid": uuid.UUID(elevation_id)},
        )

    response = await client.post(
        f"/api/v1/stock-transfers/{transfer_id}/approve",
        headers={"X-Actor": "actor-x", "X-Elevation-Id": elevation_id},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ELEVATION_INVALID"


@pytest.mark.asyncio
async def test_elevation_bound_to_its_transfer(client: httpx.AsyncClient) -> None:
    await _seed()
    transfer_a = await _create_pending(client)
    transfer_b = await _create_pending(client)
    await _provision()

    elevation = await _elevate(client, transfer_a)
    elevation_id = elevation.json()["elevation_id"]

    response = await client.post(
        f"/api/v1/stock-transfers/{transfer_b}/approve",
        headers={"X-Actor": "actor-x", "X-Elevation-Id": elevation_id},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ELEVATION_INVALID"


@pytest.mark.asyncio
async def test_seed_stored_encrypted_at_rest(client: httpx.AsyncClient) -> None:
    await _seed()
    await _provision()

    async with SessionLocal() as session:
        async with session.begin():
            row = (
                await session.execute(
                    select(UserMfaSeed.encrypted_seed).where(
                        UserMfaSeed.actor_id == "actor-x"
                    )
                )
            ).scalar_one()
            assert row != FIXED_SEED
            assert "JBSWY3DP" not in row


def test_elevation_request_schema_forbids_extra_and_validates_totp() -> None:
    with pytest.raises(ValidationError):
        MfaElevationRequest.model_validate(
            {"action": "APPROVE", "totp_code": "123456", "hack": 1}
        )
    with pytest.raises(ValidationError):
        MfaElevationRequest.model_validate({"action": "APPROVE", "totp_code": "abc123"})
    with pytest.raises(ValidationError):
        MfaElevationRequest.model_validate({"action": "", "totp_code": "123456"})
