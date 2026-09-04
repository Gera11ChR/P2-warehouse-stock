from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FiberVariant(Base):
    __tablename__ = "fiber_variants"
    __table_args__ = (
        CheckConstraint(
            "metros_restantes >= 0", name="ck_fiber_variants_metros_non_negative"
        ),
        CheckConstraint("cantidad >= 0", name="ck_fiber_variants_cantidad_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(
        String(50), ForeignKey("skus.sku", ondelete="RESTRICT"), nullable=False
    )
    variante: Mapped[str] = mapped_column(String(100), nullable=False)
    metros_restantes: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    warehouse_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("warehouses.warehouse_id", ondelete="RESTRICT")
    )
