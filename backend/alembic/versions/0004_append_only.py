"""append-only enforcement: audit_logs, derived current_stock view, ledger REVOKE

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02

Defense-in-depth for Constitution 2.4: UPDATE/DELETE are revoked from PUBLIC on
the append-only ledgers (stock_movements, audit_logs) so no future endpoint or
role can mutate history unless explicitly granted.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("log_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        "CREATE VIEW current_stock_view AS "
        "SELECT s.sku, COALESCE(SUM(wi.on_hand_quantity), 0) AS current_stock "
        "FROM skus s "
        "LEFT JOIN warehouse_inventory wi ON wi.sku = s.sku "
        "GROUP BY s.sku"
    )

    op.execute("REVOKE UPDATE, DELETE ON stock_movements, audit_logs FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP VIEW current_stock_view")
    op.drop_table("audit_logs")
