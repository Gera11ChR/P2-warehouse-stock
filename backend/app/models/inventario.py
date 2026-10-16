from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Seccion(Base):
    """Maestro de secciones de inventario central (la entidad oficial del
    dominio; el término legacy `almacenes` queda erradicado).

    Solo existen dos tipos: `GENERAL` y `FO` (sección única de ruteo
    "Inventario FO")."""

    __tablename__ = "secciones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('GENERAL','FO')",
            name="ck_secciones_tipo",
        ),
    )

    almacen_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'GENERAL'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    inventario: Mapped[list["InventarioAlmacen"]] = relationship(
        back_populates="seccion"
    )


class InventarioAlmacen(Base):
    """Stock por sección. LECTURA ESTRICTA desde el backend: toda mutación se
    ejecuta exclusivamente a través de las Stored Functions del contrato
    (fn_procesar_movimiento, fn_cancelar_movimiento, fn_cargar_stock_inicial,
    fn_ajustar_stock_almacen). Prohibido session.add/delete o UPDATE directo.

    Migración 0027 (RF-6): `stock_actual` pasa a NUMERIC(12,3) — cantidades
    con hasta 3 decimales; el CHECK `>= 0` se conserva."""

    __tablename__ = "inventario_almacen"
    __table_args__ = (
        CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_almacen_non_negative"
        ),
        Index("ix_inventario_almacen_material", "material_id"),
    )

    almacen_id: Mapped[int] = mapped_column(
        ForeignKey("secciones.almacen_id", ondelete="RESTRICT"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    seccion: Mapped[Seccion] = relationship(back_populates="inventario")


class InventarioEquipo(Base):
    """Inventario autónomo del equipo (REQ-DOMAIN-001/002).

    El Modelo Sparse y la vista `vw_inventario_equipo_completo` quedaron
    deprecados: `inventario_equipos` es la fuente física autónoma del stock
    de cada equipo, inicializada VACÍA al crear el equipo (cero herencia del
    catálogo global) y poblada EXCLUSIVAMENTE por movimientos TEAMS/DEVOL
    auditados (`fn_procesar_movimiento`). Extensión 0014: `fn_cerrar_seguimiento`
    descuenta el consumido del seguimiento en la MISMA transacción atómica.
    LECTURA ESTRICTA: las mutaciones ocurren únicamente dentro de las Stored
    Functions (`fn_procesar_movimiento`, `fn_cancelar_movimiento`,
    `fn_cerrar_seguimiento`). Migración 0027 (RF-6): `stock_actual`
    NUMERIC(12,3); CHECK `>= 0` conservado."""

    __tablename__ = "inventario_equipos"
    __table_args__ = (
        CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_equipos_non_negative"
        ),
        Index("ix_inventario_equipos_material", "material_id"),
    )

    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    # Puntero lógico al movimiento de origen (trazabilidad REQ-DOMAIN-002).
    # Sin FK declarativa a movimientos_cabecera: el ledger de movimientos es
    # append-only (jamás se borran físicamente), por lo que el puntero aporta
    # la misma trazabilidad sin acoplar el inventario al ciclo de vida del
    # movimiento. Las filas preexistentes quedan en NULL (sin atribución
    # fabricada: el stock acumulado puede provenir de varios movimientos).
    ultimo_movimiento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class InventarioFibra(Base):
    """Inventario FO unificado (RF-1).

    UNA sola fila por material (PK `material_id`), sin subapartados. La fila se crea con
    `fn_cargar_stock_inicial_fibra` y se muta SOLO con
    `fn_ajustar_stock_fibra`; la métrica la gobierna `u_m` del catálogo
    maestro. LECTURA ESTRICTA desde el backend: prohibido session.add/delete
    o UPDATE directo sobre esta tabla."""

    __tablename__ = "inventario_fibra"
    __table_args__ = (
        CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_fibra_non_negative"
        ),
    )

    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
