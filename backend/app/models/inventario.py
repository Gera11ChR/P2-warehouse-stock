from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Seccion(Base):
    """Maestro de secciones de inventario central (la entidad oficial del
    dominio; el término legacy `almacenes` queda erradicado)."""

    __tablename__ = "secciones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('GENERAL','FO_PAQUETE','FO_EN_USO')",
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
    fn_ajustar_stock_almacen). Prohibido session.add/delete o UPDATE directo."""

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
    stock_actual: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
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
    auditados (`fn_procesar_movimiento`). LECTURA ESTRICTA: las mutaciones
    ocurren únicamente dentro de las Stored Functions."""

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
    stock_actual: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
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
    """Inventario independiente de Fibra Óptica (REQ-DOMAIN-003/004/005/006).

    `PAQUETE` y `EN_USO` son raíces de inventario autónomas con el esquema
    estándar (ya NO secciones del Inventario General). Las filas son
    registros físicos reales creados por `fn_cargar_stock_inicial_fibra` y
    mutados SOLO por `fn_ajustar_stock_fibra`; la métrica de cada activo la
    gobierna el campo `u_m` del catálogo maestro (nunca columnas
    carretes/metros del legacy `fiber_variants`). LECTURA ESTRICTA desde el
    backend: prohibido session.add/delete o UPDATE directo sobre esta tabla."""

    __tablename__ = "inventario_fibra"
    __table_args__ = (
        CheckConstraint(
            "modulo IN ('PAQUETE','EN_USO')", name="ck_inventario_fibra_modulo"
        ),
        CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_fibra_non_negative"
        ),
        Index("ix_inventario_fibra_material", "material_id"),
    )

    modulo: Mapped[str] = mapped_column(String(20), primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    stock_actual: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
