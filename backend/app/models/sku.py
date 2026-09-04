from sqlalchemy import CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SKU_TYPES = ("GENERAL", "FIBRA")


class Sku(Base):
    __tablename__ = "skus"
    __table_args__ = (
        CheckConstraint("tipo IN ('GENERAL','FIBRA')", name="ck_skus_tipo"),
    )

    sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50))
    min_stock: Mapped[int | None] = mapped_column(Integer)
    categoria: Mapped[str | None] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'GENERAL'")
    )
