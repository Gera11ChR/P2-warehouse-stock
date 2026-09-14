from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class HistorialImportacion(Base):
    """Trazabilidad de cargas masivas CSV/XLSX/XML (SDD §6). Errores de
    validación estructural almacenados en JSONB para forensia."""

    __tablename__ = "historial_importaciones"
    __table_args__ = (
        CheckConstraint(
            "formato IN ('CSV','XLSX','XML')", name="ck_importaciones_formato"
        ),
        CheckConstraint(
            "estado IN ('COMPLETO','PARCIAL','FALLIDO')",
            name="ck_importaciones_estado",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errores: Mapped[list | None] = mapped_column(JSON)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
