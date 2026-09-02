from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserMfaSeed(Base):
    __tablename__ = "user_mfa_seeds"

    actor_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    encrypted_seed: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MfaElevation(Base):
    __tablename__ = "mfa_elevations"
    __table_args__ = (
        Index("ix_mfa_elevations_actor_transfer_action", "actor_id", "transfer_id", "action"),
    )

    elevation_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    transfer_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MfaAttempt(Base):
    __tablename__ = "mfa_attempts"
    __table_args__ = (
        Index("ix_mfa_attempts_actor_created", "actor_id", "created_at"),
    )

    attempt_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
