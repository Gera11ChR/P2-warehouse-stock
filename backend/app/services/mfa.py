from datetime import datetime, timedelta, timezone
from uuid import UUID

import pyotp
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    MFA_ENCRYPTION_KEY,
    MFA_ELEVATION_TTL_SECONDS,
    TOTP_LOCKOUT_SECONDS,
    TOTP_MAX_ATTEMPTS,
    TOTP_WINDOW_SECONDS,
)
from app.db import SessionLocal
from app.errors import AuthorizationError
from app.models import MfaAttempt, MfaElevation, UserMfaSeed
from app.services.audit import make_audit


def _fernet() -> Fernet:
    return Fernet(MFA_ENCRYPTION_KEY.encode())


async def provision_seed(session: AsyncSession, *, actor: str, seed: str) -> None:
    token = _fernet().encrypt(seed.encode()).decode()
    stmt = (
        pg_insert(UserMfaSeed)
        .values(actor_id=actor, encrypted_seed=token)
        .on_conflict_do_update(
            index_elements=["actor_id"], set_={"encrypted_seed": token}
        )
    )
    await session.execute(stmt)


async def _failed_attempts_in_window(session: AsyncSession, *, actor: str) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=TOTP_WINDOW_SECONDS)
    return (
        await session.execute(
            select(func.count())
            .select_from(MfaAttempt)
            .where(
                MfaAttempt.actor_id == actor,
                MfaAttempt.success.is_(False),
                MfaAttempt.created_at >= cutoff,
            )
        )
    ).scalar_one()


async def _record_attempt(
    *,
    actor: str,
    transfer_id: UUID,
    action: str,
    success: bool,
    audit_action: str,
    extra: dict | None = None,
) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            session.add(MfaAttempt(actor_id=actor, success=success))
            session.add(
                make_audit(
                    action=audit_action,
                    actor=actor,
                    details={
                        "transfer_id": str(transfer_id),
                        "action": action,
                        **(extra or {}),
                    },
                )
            )


async def _audit_only(*, actor: str, audit_action: str, details: dict) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            session.add(make_audit(action=audit_action, actor=actor, details=details))


async def issue_elevation(
    session: AsyncSession,
    *,
    actor: str,
    transfer_id: UUID,
    action: str,
    totp_code: str,
) -> MfaElevation:
    async with SessionLocal() as audit_session:
        async with audit_session.begin():
            failures = await _failed_attempts_in_window(
                audit_session, actor=actor
            )

    if failures >= TOTP_MAX_ATTEMPTS:
        await _audit_only(
            actor=actor,
            audit_action="TOTP_LOCKED",
            details={
                "transfer_id": str(transfer_id),
                "action": action,
                "lockout_seconds": TOTP_LOCKOUT_SECONDS,
            },
        )
        raise AuthorizationError(
            f"TOTP locked out for {TOTP_LOCKOUT_SECONDS} seconds",
            code="TOTP_LOCKED",
            actor=actor,
        )

    seed_row = await session.get(UserMfaSeed, actor)
    if seed_row is None:
        raise AuthorizationError(
            "TOTP not provisioned for actor", code="TOTP_INVALID", actor=actor
        )

    seed = _fernet().decrypt(seed_row.encrypted_seed.encode()).decode()
    if not pyotp.TOTP(seed).verify(totp_code, valid_window=1):
        await _record_attempt(
            actor=actor,
            transfer_id=transfer_id,
            action=action,
            success=False,
            audit_action="TOTP_VERIFY_FAILED",
        )
        raise AuthorizationError(
            "Invalid TOTP code", code="TOTP_INVALID", actor=actor
        )

    await _record_attempt(
        actor=actor,
        transfer_id=transfer_id,
        action=action,
        success=True,
        audit_action="TOTP_VERIFY_OK",
    )

    elevation = MfaElevation(
        actor_id=actor,
        transfer_id=transfer_id,
        action=action,
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=MFA_ELEVATION_TTL_SECONDS),
    )
    session.add(elevation)
    await session.flush()

    session.add(
        make_audit(
            action="MFA_ELEVATION_ISSUED",
            actor=actor,
            details={
                "elevation_id": str(elevation.elevation_id),
                "transfer_id": str(transfer_id),
                "action": action,
                "expires_at": elevation.expires_at.isoformat(),
            },
        )
    )
    return elevation


async def verify_elevation(
    session: AsyncSession,
    *,
    actor: str,
    transfer_id: UUID,
    action: str,
    elevation_id: UUID,
) -> None:
    elevation = await session.get(MfaElevation, elevation_id)
    if (
        elevation is None
        or elevation.actor_id != actor
        or elevation.transfer_id != transfer_id
        or elevation.action != action
    ):
        await _audit_only(
            actor=actor,
            audit_action="MFA_ELEVATION_REJECTED",
            details={
                "elevation_id": str(elevation_id),
                "transfer_id": str(transfer_id),
                "action": action,
                "reason": "invalid_or_mismatched",
            },
        )
        raise AuthorizationError(
            "Invalid MFA elevation", code="ELEVATION_INVALID", actor=actor
        )
    if elevation.used_at is not None or elevation.expires_at <= datetime.now(
        timezone.utc
    ):
        await _audit_only(
            actor=actor,
            audit_action="MFA_ELEVATION_REJECTED",
            details={
                "elevation_id": str(elevation_id),
                "transfer_id": str(transfer_id),
                "action": action,
                "reason": "expired_or_used",
            },
        )
        raise AuthorizationError(
            "MFA elevation expired or already used",
            code="ELEVATION_INVALID",
            actor=actor,
        )
    elevation.used_at = datetime.now(timezone.utc)
    session.add(
        make_audit(
            action="MFA_ELEVATION_CONSUMED",
            actor=actor,
            details={
                "elevation_id": str(elevation_id),
                "transfer_id": str(transfer_id),
                "action": action,
            },
        )
    )
