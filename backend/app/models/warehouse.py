from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class WarehouseInventory(Base):
    __tablename__ = "warehouse_inventory"
    __table_args__ = (
        CheckConstraint(
            "on_hand_quantity >= 0", name="ck_warehouse_inventory_non_negative"
        ),
        Index("ix_warehouse_inventory_sku", "sku"),
    )

    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), primary_key=True
    )
    sku: Mapped[str] = mapped_column(
        ForeignKey("skus.sku", ondelete="RESTRICT"), primary_key=True
    )
    on_hand_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
