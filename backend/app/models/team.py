from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TeamInventory(Base):
    __tablename__ = "team_inventory"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="ck_team_inventory_cantidad_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo: Mapped[str] = mapped_column(String(100), nullable=False)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(
        String(50), ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    ultima_modificacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
