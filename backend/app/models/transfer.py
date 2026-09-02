from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

TRANSFER_STATUSES = (
    "PENDING_APPROVAL",
    "APPROVED",
    "IN_TRANSIT",
    "RECEIVED",
    "REJECTED",
    "CANCELLED",
)

MOVEMENT_TYPES = (
    "TRANSFER_OUT",
    "TRANSFER_IN",
    "ADJUSTMENT",
    "RECEIPT",
    "DISPATCH",
)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('PENDING_APPROVAL','APPROVED','IN_TRANSIT','RECEIVED','REJECTED','CANCELLED')",
            name="ck_stock_transfers_status",
        ),
        CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
        UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_stock_transfers_actor_idempotency"
        ),
    )

    transfer_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), nullable=False
    )
    destination_warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="PENDING_APPROVAL"
    )
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransferLineItem(Base):
    __tablename__ = "transfer_line_items"
    __table_args__ = (
        CheckConstraint(
            "dispatched_quantity > 0", name="ck_transfer_line_items_dispatch_positive"
        ),
        CheckConstraint(
            "received_quantity IS NULL OR "
            "(received_quantity >= 0 AND received_quantity <= dispatched_quantity)",
            name="ck_transfer_line_items_receive_range",
        ),
        UniqueConstraint("transfer_id", "sku", name="uq_transfer_line_items_transfer_sku"),
    )

    line_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(
        ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    dispatched_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int | None] = mapped_column(Integer)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN "
            "('TRANSFER_OUT','TRANSFER_IN','ADJUSTMENT','RECEIPT','DISPATCH')",
            name="ck_stock_movements_type",
        ),
        CheckConstraint("quantity_change <> 0", name="ck_stock_movements_nonzero"),
        Index("ix_stock_movements_warehouse_sku", "warehouse_id", "sku"),
    )

    movement_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transfer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stock_transfers.transfer_id", ondelete="RESTRICT")
    )
    references_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_movements.movement_id", ondelete="RESTRICT")
    )
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(
        ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
