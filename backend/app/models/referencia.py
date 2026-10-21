from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReferenciaMaterial(Base):
    """Referencia de materiales de una Unidad (`referencia_materiales`, 0030).

    Tabla de configuración VISUAL por Unidad: `(equipo_id, material_id,
    cantidad_semanal)` con PK compuesta y FKs `ON DELETE RESTRICT`
    (REQ-REF-005..009, plan §3.1, P-2). `cantidad_semanal` NO es un saldo
    (RN-7): no le aplican las Stored Functions de stock ni la invariante de
    saldo no negativo; toda mutación se audita en la misma transacción por
    el trigger `tg_auditar_referencia_materiales` (REQ-REF-012,
    Constitución §6.2). Solo lectura desde el backend salvo en
    `app/services/referencia.py` (REQ-REF-011: cero escrituras fuera de
    esta tabla; ni una Unidad ni un material con Referencia pueden borrarse
    físicamente).
    """

    __tablename__ = "referencia_materiales"
    __table_args__ = (
        CheckConstraint(
            "cantidad_semanal > 0", name="ck_referencia_cantidad_positiva"
        ),
    )

    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    cantidad_semanal: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
