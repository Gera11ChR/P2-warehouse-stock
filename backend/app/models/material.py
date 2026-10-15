from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    materiales: Mapped[list["CatalogoMaterial"]] = relationship(
        back_populates="categoria"
    )


class CatalogoMaterial(Base):
    """Catálogo maestro. `id_lista` es INMUTABLE: se genera una única vez y
    jamás se reutiliza ni renumera, incluso tras eliminación lógica.

    `valor_unitario` (RF-2/RF-3, migración 0027): atributo financiero de
    catálogo en MXN con hasta 3 decimales; nace en `1.000` (DEFAULT) y se
    edita solo por administradores (RBAC en el PATCH). Es atributo de
    catálogo — NO un saldo de inventario —, por lo que su edición sigue el
    patrón de campos de catálogo (UPDATE + trigger de auditoría
    `tg_auditar_modificacion_material`, RF-7)."""

    __tablename__ = "catalogo_materiales"
    __table_args__ = (
        CheckConstraint("stock_minimo IS NULL OR stock_minimo >= 0",
                        name="ck_catalogo_stock_minimo_non_negative"),
        CheckConstraint("valor_unitario >= 0",
                        name="ck_catalogo_valor_unitario_non_negative"),
        Index(
            "uq_catalogo_codigo_active",
            "codigo",
            unique=True,
            postgresql_where=text("codigo IS NOT NULL"),
        ),
    )

    id_lista: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    codigo: Mapped[str | None] = mapped_column(String(50))
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="RESTRICT")
    )
    u_m: Mapped[str | None] = mapped_column(String(50))
    stock_minimo: Mapped[int | None] = mapped_column(Integer)
    valor_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("1.000")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    categoria: Mapped[Categoria | None] = relationship(back_populates="materiales")


class Ums(Base):
    """Unidad de Medida (U.M.) maestra del catálogo (tabla `ums`, 0014).

    Fuente única del selector de U.M. para el alta/modificación de
    materiales y para la configuración local de equipos
    (`equipo_material_config.um_local_id`). La eliminación es lógica
    (is_active = FALSE) y queda auditada por el trigger
    `tg_auditar_um` (Constitution 6.2); no existen caminos de DELETE
    físico desde el backend."""

    __tablename__ = "ums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
