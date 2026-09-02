"""initial schema: skus baseline + inter-site stock transfer model

Revision ID: 0001
Revises:
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skus",
        sa.Column("sku", sa.String(50), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_of_measure", sa.String(20), nullable=True),
        sa.Column("current_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "current_stock >= 0", name="ck_skus_current_stock_non_negative"
        ),
    )

    op.create_table(
        "warehouses",
        sa.Column("warehouse_id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "warehouse_inventory",
        sa.Column(
            "warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("on_hand_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "on_hand_quantity >= 0", name="ck_warehouse_inventory_non_negative"
        ),
    )
    op.create_index("ix_warehouse_inventory_sku", "warehouse_inventory", ["sku"])

    op.create_table(
        "stock_transfers",
        sa.Column(
            "transfer_id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column(
            "source_warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "destination_warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN "
            "('PENDING_APPROVAL','APPROVED','IN_TRANSIT','RECEIVED','REJECTED','CANCELLED')",
            name="ck_stock_transfers_status",
        ),
        sa.CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
        sa.UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_stock_transfers_actor_idempotency"
        ),
    )

    op.create_table(
        "transfer_line_items",
        sa.Column("line_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "transfer_id",
            sa.Uuid(),
            sa.ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dispatched_quantity", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "dispatched_quantity > 0", name="ck_transfer_line_items_dispatch_positive"
        ),
        sa.CheckConstraint(
            "received_quantity IS NULL OR "
            "(received_quantity >= 0 AND received_quantity <= dispatched_quantity)",
            name="ck_transfer_line_items_receive_range",
        ),
        sa.UniqueConstraint(
            "transfer_id", "sku", name="uq_transfer_line_items_transfer_sku"
        ),
    )

    op.create_table(
        "stock_movements",
        sa.Column("movement_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "transfer_id",
            sa.Uuid(),
            sa.ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "references_movement_id",
            sa.BigInteger(),
            sa.ForeignKey("stock_movements.movement_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_change", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "movement_type IN "
            "('TRANSFER_OUT','TRANSFER_IN','ADJUSTMENT','RECEIPT','DISPATCH')",
            name="ck_stock_movements_type",
        ),
        sa.CheckConstraint("quantity_change <> 0", name="ck_stock_movements_nonzero"),
    )
    op.create_index(
        "ix_stock_movements_warehouse_sku", "stock_movements", ["warehouse_id", "sku"]
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_warehouse_sku", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("transfer_line_items")
    op.drop_table("stock_transfers")
    op.drop_index("ix_warehouse_inventory_sku", table_name="warehouse_inventory")
    op.drop_table("warehouse_inventory")
    op.drop_table("warehouses")
    op.drop_table("skus")
