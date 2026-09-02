"""expand: seed CENTRAL warehouse, backfill warehouse_inventory from skus, quarantine negatives

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-02

Quarantine is durable: negative legacy balances stay in skus untouched (no data
loss) and are recorded in legacy_stock_quarantine for documented resolution
(Constitution 2.1 / 4.3). Downgrade is zero-data-loss: only backfill rows whose
quantity still equals skus.current_stock are removed; CENTRAL is deleted only
when no inventory rows remain.

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_stock_quarantine",
        sa.Column("quarantine_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("current_stock", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column(
            "quarantined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("sku", name="uq_legacy_stock_quarantine_sku"),
    )

    op.execute(
        "INSERT INTO warehouses (warehouse_id, name) "
        "VALUES ('CENTRAL', 'Central Warehouse') "
        "ON CONFLICT (warehouse_id) DO NOTHING"
    )

    op.execute(
        "INSERT INTO legacy_stock_quarantine (sku, current_stock, reason) "
        "SELECT sku, current_stock, 'NEGATIVE_LEGACY_STOCK' "
        "FROM skus WHERE current_stock < 0 "
        "ON CONFLICT (sku) DO NOTHING"
    )

    op.execute(
        "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
        "SELECT 'CENTRAL', sku, current_stock FROM skus "
        "WHERE current_stock >= 0 "
        "ON CONFLICT (warehouse_id, sku) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM warehouse_inventory wi "
        "USING skus s "
        "WHERE wi.warehouse_id = 'CENTRAL' "
        "AND wi.sku = s.sku "
        "AND wi.on_hand_quantity = s.current_stock"
    )
    op.execute(
        "DELETE FROM warehouses WHERE warehouse_id = 'CENTRAL' "
        "AND NOT EXISTS (SELECT 1 FROM warehouse_inventory WHERE warehouse_id = 'CENTRAL')"
    )
    op.drop_table("legacy_stock_quarantine")
