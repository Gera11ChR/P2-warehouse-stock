"""inventory dashboard: skus classification fields, fiber variants, team inventory

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-04

Expands the SKU catalog with a Spanish classification (categoria, tipo) and a
widened unit_of_measure vocabulary, and adds the operator-facing WMS entities:
fiber-optic variants (remaining meters) and team inventory assignments.

"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("categoria", sa.String(100), nullable=True))
    op.add_column(
        "skus",
        sa.Column(
            "tipo",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'GENERAL'"),
        ),
    )
    op.create_check_constraint(
        "ck_skus_tipo", "skus", "tipo IN ('GENERAL','FIBRA')"
    )
    op.alter_column(
        "skus",
        "unit_of_measure",
        existing_type=sa.String(20),
        type_=sa.String(50),
        existing_nullable=True,
    )

    op.create_table(
        "fiber_variants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("variante", sa.String(100), nullable=False),
        sa.Column("metros_restantes", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "warehouse_id",
            sa.String(50),
            sa.ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "metros_restantes >= 0", name="ck_fiber_variants_metros_non_negative"
        ),
        sa.CheckConstraint(
            "cantidad >= 0", name="ck_fiber_variants_cantidad_non_negative"
        ),
    )

    op.create_table(
        "team_inventory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("equipo", sa.String(100), nullable=False),
        sa.Column("usuario", sa.String(100), nullable=False),
        sa.Column(
            "sku",
            sa.String(50),
            sa.ForeignKey("skus.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column(
            "ultima_modificacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "cantidad >= 0", name="ck_team_inventory_cantidad_non_negative"
        ),
    )


def downgrade() -> None:
    op.drop_table("team_inventory")
    op.drop_table("fiber_variants")
    op.alter_column(
        "skus",
        "unit_of_measure",
        existing_type=sa.String(50),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.drop_constraint("ck_skus_tipo", "skus", type_="check")
    op.drop_column("skus", "tipo")
    op.drop_column("skus", "categoria")
