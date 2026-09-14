from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditoriaEvento(Base):
    """Ledger inmutable (Constitution 2.4): append-only. Los eventos críticos
    los insertan exclusivamente las Stored Functions y el trigger de catálogo.
    El backend solo lee; prohibido UPDATE/DELETE sobre esta tabla."""

    __tablename__ = "auditoria_eventos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario: Mapped[str | None] = mapped_column(String(100))
    tipo_accion: Mapped[str] = mapped_column(String(50), nullable=False)
    material_id: Mapped[int | None] = mapped_column(Integer)
    equipo_origen_id: Mapped[int | None] = mapped_column(Integer)
    equipo_destino_id: Mapped[int | None] = mapped_column(Integer)
    almacen_origen_id: Mapped[int | None] = mapped_column(Integer)
    almacen_destino_id: Mapped[int | None] = mapped_column(Integer)
    cantidad: Mapped[int | None] = mapped_column(Integer)
    resultado: Mapped[str | None] = mapped_column(String(20))
    detalles: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
