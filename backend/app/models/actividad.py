"""Modelo ORM de actividades por Unidad (0029, paquete
2026-10-actividades-unidad) — APPEND-ONLY.

Registro documental 1:1 con un seguimiento CERRADA: folio global
correlativo (`folio_num`, presentación `R0001`), fecha `created_at` = now(),
campos manuales (vehiculo, clientes, direcciones, actividades, comentarios)
y snapshot jsonb de materiales con `valor_unitario` congelado. La tabla es
inmutable por trigger (`tg_ledger_actividades_inmutable` → 
fn_bloquear_mutacion_ledger): el ORM solo la lee; la escritura la ejecuta
exclusivamente `fn_crear_actividad` vía services.transaccional.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActividadReporte(Base):
    """Actividad confirmada de una Unidad (0029). Sin relaciones ORM de
    escritura: la FK a seguimientos/equipos es RESTRICT y la integridad la
    administra PostgreSQL."""

    __tablename__ = "actividades_reportes"
    __table_args__ = (
        CheckConstraint("folio_num > 0", name="ck_actividades_folio_positivo"),
        CheckConstraint(
            "btrim(vehiculo) <> ''", name="ck_actividades_vehiculo_no_vacio"
        ),
        CheckConstraint(
            "btrim(clientes) <> ''", name="ck_actividades_clientes_no_vacio"
        ),
        CheckConstraint(
            "btrim(direcciones) <> ''", name="ck_actividades_direcciones_no_vacio"
        ),
        CheckConstraint(
            "jsonb_typeof(actividades) = 'array' "
            "AND jsonb_array_length(actividades) BETWEEN 1 AND 30",
            name="ck_actividades_actividades_rango",
        ),
        CheckConstraint(
            "jsonb_typeof(materiales) = 'array'",
            name="ck_actividades_materiales_array",
        ),
        UniqueConstraint("folio_num", name="uq_actividades_folio"),
        UniqueConstraint("seguimiento_id", name="uq_actividades_seguimiento"),
        Index("ix_actividades_equipo_created", "equipo_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folio_num: Mapped[int] = mapped_column(Integer, nullable=False)
    seguimiento_id: Mapped[int] = mapped_column(
        ForeignKey("seguimientos.id", ondelete="RESTRICT"), nullable=False
    )
    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), nullable=False
    )
    vehiculo: Mapped[str] = mapped_column(String(100), nullable=False)
    clientes: Mapped[str] = mapped_column(String(500), nullable=False)
    direcciones: Mapped[str] = mapped_column(String(500), nullable=False)
    actividades: Mapped[list] = mapped_column(JSONB, nullable=False)
    comentarios: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    materiales: Mapped[list] = mapped_column(JSONB, nullable=False)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
