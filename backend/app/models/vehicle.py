from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    plate_or_designation: Mapped[str | None] = mapped_column(String(50))
    assigned_crew: Mapped[dict | None] = mapped_column(JSONB)


class FleetAllocation(Base):
    __tablename__ = "fleet_allocations"
    __table_args__ = (
        CheckConstraint(
            "allocated_quantity > 0", name="ck_fleet_allocations_positive"
        ),
    )

    allocation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[str] = mapped_column(
        ForeignKey("vehicles.vehicle_id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(
        ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
