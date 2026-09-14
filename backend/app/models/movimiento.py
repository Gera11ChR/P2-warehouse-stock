from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

MOVIMIENTO_TIPOS = ("TEAMS", "DEVOL")
MOVIMIENTO_ESTADOS = ("BORRADOR", "CONFIRMADO", "CANCELADO")


class MovimientoCabecera(Base):
    """Cabecera de transferencia TEAMS o devolución DEVOL. El ciclo de vida es
    BORRADOR -> CONFIRMADO (vía fn_procesar_movimiento) y CONFIRMADO ->
    CANCELADO (vía fn_cancelar_movimiento). El backend solo crea/edita/elimina
    BORRADORES; las transiciones de estado las ejecuta PostgreSQL."""

    __tablename__ = "movimientos_cabecera"
    __table_args__ = (
        CheckConstraint(
            "tipo_movimiento IN ('TEAMS','DEVOL')",
            name="ck_movimientos_cabecera_tipo",
        ),
        CheckConstraint(
            "estado IN ('BORRADOR','CONFIRMADO','CANCELADO')",
            name="ck_movimientos_cabecera_estado",
        ),
        CheckConstraint(
            "(tipo_movimiento = 'TEAMS' AND origen_almacen_id IS NOT NULL AND destino_equipo_id IS NOT NULL) "
            "OR (tipo_movimiento = 'DEVOL' AND origen_equipo_id IS NOT NULL AND destino_almacen_id IS NOT NULL)",
            name="ck_movimientos_cabecera_extremos",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo_movimiento: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'BORRADOR'")
    )
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)
    origen_almacen_id: Mapped[int | None] = mapped_column(
        ForeignKey("secciones.almacen_id", ondelete="RESTRICT")
    )
    destino_almacen_id: Mapped[int | None] = mapped_column(
        ForeignKey("secciones.almacen_id", ondelete="RESTRICT")
    )
    origen_equipo_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT")
    )
    destino_equipo_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT")
    )
    observaciones: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    detalle: Mapped[list["MovimientoDetalle"]] = relationship(
        back_populates="cabecera", cascade="all, delete-orphan"
    )


class MovimientoDetalle(Base):
    __tablename__ = "movimientos_detalle"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_movimientos_detalle_cantidad"),
    )

    movimiento_id: Mapped[int] = mapped_column(
        ForeignKey("movimientos_cabecera.id", ondelete="RESTRICT"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    cabecera: Mapped[MovimientoCabecera] = relationship(back_populates="detalle")
