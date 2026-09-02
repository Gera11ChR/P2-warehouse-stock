from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserWarehouseScope(Base):
    __tablename__ = "user_warehouse_scopes"

    actor_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT"), primary_key=True
    )
    granted_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
