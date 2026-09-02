from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Sku(Base):
    __tablename__ = "skus"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    unit_of_measure: Mapped[str | None] = mapped_column(String(20))
    min_stock: Mapped[int | None] = mapped_column(Integer)
