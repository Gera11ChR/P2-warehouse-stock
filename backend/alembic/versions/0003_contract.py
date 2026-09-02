"""contract: drop skus.current_stock (derived aggregate takes over); downgrade reconstructs

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-02

The derived aggregate (SUM over warehouse_inventory) becomes the single source
of truth for global SKU stock. downgrade() reconstructs current_stock exactly
from the aggregate; SKUs with no warehouse inventory rows reconstruct to 0.

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE skus DROP CONSTRAINT IF EXISTS ck_skus_current_stock_non_negative"
    )
    op.drop_column("skus", "current_stock")


def downgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("current_stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE skus s SET current_stock = COALESCE("
        "(SELECT SUM(wi.on_hand_quantity) FROM warehouse_inventory wi "
        "WHERE wi.sku = s.sku), 0)"
    )
    op.create_check_constraint(
        "ck_skus_current_stock_non_negative", "skus", "current_stock >= 0"
    )
