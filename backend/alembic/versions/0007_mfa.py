"""MFA infrastructure: encrypted TOTP seeds, action-bound elevations, attempts

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-02

TOTP seeds are stored encrypted at rest (envelope encryption via the runtime
P2_MFA_ENCRYPTION_KEY) - seeds cannot be one-way hashed because verification
needs them. Elevations are single-use, transfer-bound, short-TTL. Attempts are
append-only for lockout accounting and 6.2 auditing.

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_mfa_seeds",
        sa.Column("actor_id", sa.String(100), primary_key=True),
        sa.Column("encrypted_seed", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "mfa_elevations",
        sa.Column(
            "elevation_id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column(
            "transfer_id",
            sa.Uuid(),
            sa.ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_mfa_elevations_actor_transfer_action",
        "mfa_elevations",
        ["actor_id", "transfer_id", "action"],
    )

    op.create_table(
        "mfa_attempts",
        sa.Column("attempt_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_mfa_attempts_actor_created", "mfa_attempts", ["actor_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_mfa_attempts_actor_created", table_name="mfa_attempts")
    op.drop_table("mfa_attempts")
    op.drop_index(
        "ix_mfa_elevations_actor_transfer_action", table_name="mfa_elevations"
    )
    op.drop_table("mfa_elevations")
    op.drop_table("user_mfa_seeds")
