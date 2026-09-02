"""fleet entities: vehicles and fleet_allocations (canonical spec 001)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02

fleet_allocations gains warehouse_id: in the per-warehouse model every
allocation deducts stock from a specific warehouse (material binding, 2.2).

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("vehicle_id", sa.String(50), primary_key=True),
        sa.Column("plate_or_designation", sa.String(50), nullable=True),
        sa.Column("assigned_crew", JSONB(), nullable=True),
    )

    op.create_table(
        "fleet_allocations",
        sa.Column("allocation_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "vehicle_id",
            sa.String(50),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="RESTRICT"),
            nullable=False,
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
        sa.Column("allocated_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "allocated_quantity > 0", name="ck_fleet_allocations_positive"
        ),
    )


def downgrade() -> None:
    op.drop_table("fleet_allocations")
    op.drop_table("vehicles")
