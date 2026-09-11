"""official catalog: soft-deactivation flag on skus

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-11

Adds a non-destructive `is_active` flag to the SKU catalog so legacy demo
materials with transaction history can be retired logically (soft-delete)
without breaking foreign keys or the append-only ledger.

"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("skus", "is_active")
