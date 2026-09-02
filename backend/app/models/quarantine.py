from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LegacyStockQuarantine(Base):
    __tablename__ = "legacy_stock_quarantine"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_legacy_stock_quarantine_sku"),
    )

    quarantine_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(
        ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
