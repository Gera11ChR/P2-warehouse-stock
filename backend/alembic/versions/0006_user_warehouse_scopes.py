"""user warehouse scopes: resource-scoped authorization data (3.2)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-02

actor_id is the authentication subject (JWT sub); warehouse_id grants an
operator write access to that warehouse. Re-validated server-side per request.

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_warehouse_scopes",
        sa.Column("actor_id", sa.String(100), primary_key=True),
        sa.Column(
            "warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("granted_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_warehouse_scopes")
