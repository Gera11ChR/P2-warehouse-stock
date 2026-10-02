from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EquipoMaterialConfig(Base):
    """Configuración operativa LOCAL de un equipo por material (0014).

    Invariantes (arquitectura aprobada, Fase 2):
      * Tabla SEPARADA del inventario físico: `inventario_equipos` sigue
        siendo el registro autónomo de existencias poblado exclusivamente
        por movimientos TEAMS/DEVOL; aquí viven solo los parámetros
        operativos del equipo (stock mínimo local, categoría y U.M. de
        trabajo), SIN alterar el catálogo maestro ni el stock.
      * El catálogo y `u_m` maestros son inmutables desde esta entidad:
        `categoria_local_id` y `um_local_id` son sobrescrituras locales
        (FK RESTRICT a `categorias` y `ums`).
      * Toda mutación emite el evento inmutable `CONFIG_EQUIPO_MODIFICADA`
        vía el trigger `tg_auditar_equipo_material_config`
        (Constitution 6.2). Sin caminos de DELETE físico.
    """

    __tablename__ = "equipo_material_config"
    __table_args__ = (
        CheckConstraint(
            "stock_minimo_local IS NULL OR stock_minimo_local >= 0",
            name="ck_equipo_material_config_stock_minimo",
        ),
        Index("ix_equipo_material_config_material", "material_id"),
    )

    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), primary_key=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        primary_key=True,
    )
    stock_minimo_local: Mapped[int | None] = mapped_column(Integer)
    categoria_local_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="RESTRICT")
    )
    um_local_id: Mapped[int | None] = mapped_column(
        ForeignKey("ums.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Seguimiento(Base):
    """Cabecera del flujo CONSUMO de campo (0014, renombrada en 0016).

    Entidad antes denominada "despliegue"; renombre físico completo en la
    migración 0016 (tablas, columnas, secuencias, FKs, constraints,
    índices y funciones). Glosario: CONSUMO = dominio UI/reportes;
    seguimiento = entidad API/BD; entrega = acta TEAMS.

    Invariantes:
      * Ciclo de vida ABIERTA -> CERRADA gestionado EXCLUSIVAMENTE por las
        stored functions `fn_crear_seguimiento` / `fn_cerrar_seguimiento`;
        el backend solo las invoca (prohibido UPDATE directo de `estado`).
      * UN SOLO seguimiento ABIERTO por equipo: lo garantiza el índice
        único parcial `uq_seguimientos_equipo_abierta` (WHERE estado =
        'ABIERTA') y el bloqueo FOR UPDATE dentro de fn_crear_seguimiento.
      * Ledger append-only: las filas jamás se eliminan físicamente
        (FK RESTRICT desde seguimiento_items).
    """

    __tablename__ = "seguimientos"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ABIERTA','CERRADA')", name="ck_seguimientos_estado"
        ),
        Index("ix_seguimientos_equipo", "equipo_id"),
        Index("ix_seguimientos_fecha", "fecha"),
        Index(
            "uq_seguimientos_equipo_abierta",
            "equipo_id",
            unique=True,
            postgresql_where=text("estado = 'ABIERTA'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("CURRENT_DATE")
    )
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ABIERTA'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["SeguimientoItem"]] = relationship(
        back_populates="seguimiento",
        order_by="SeguimientoItem.material_id",
    )


class SeguimientoItem(Base):
    """Línea de material de un seguimiento — LEDGER APPEND-ONLY (0014/0016).

    Invariantes:
      * Las filas se crean ÚNICAMENTE en `fn_crear_seguimiento` o en
        `fn_agregar_todo_seguimiento` (idempotente) y jamás se eliminan ni
        se reescribe su `cantidad_tomada` (append-only).
      * `cantidad_sobrante` solo la escribe `fn_cerrar_seguimiento` (antes
        del cierre es NULL); la columna GENERADA `cantidad_consumida`
        (= tomada - sobrante) se materializa en PostgreSQL, nunca desde
        la aplicación.
      * Toda la aritmética de stock del seguimiento ocurre dentro de
        fn_cerrar_seguimiento bajo FOR UPDATE (cero condiciones de
        carrera); el backend jamás muta `inventario_equipos` para este
        flujo.
    """

    __tablename__ = "seguimiento_items"
    __table_args__ = (
        UniqueConstraint(
            "seguimiento_id", "material_id", name="uq_seguimiento_items_material"
        ),
        CheckConstraint("cantidad_tomada > 0", name="ck_seguimiento_items_tomada"),
        CheckConstraint(
            "cantidad_sobrante IS NULL OR "
            "(cantidad_sobrante >= 0 AND cantidad_sobrante <= cantidad_tomada)",
            name="ck_seguimiento_items_sobrante",
        ),
        Index("ix_seguimiento_items_material", "material_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seguimiento_id: Mapped[int] = mapped_column(
        ForeignKey("seguimientos.id", ondelete="RESTRICT"), nullable=False
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
        nullable=False,
    )
    cantidad_tomada: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_sobrante: Mapped[int | None] = mapped_column(Integer)
    cantidad_consumida: Mapped[int | None] = mapped_column(
        Integer,
        Computed("cantidad_tomada - cantidad_sobrante", persisted=True),
    )

    seguimiento: Mapped["Seguimiento"] = relationship(back_populates="items")
