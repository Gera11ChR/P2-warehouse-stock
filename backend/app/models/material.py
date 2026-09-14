from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
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
    jamás se reutiliza ni renumera, incluso tras eliminación lógica."""

    __tablename__ = "catalogo_materiales"
    __table_args__ = (
        CheckConstraint("stock_minimo IS NULL OR stock_minimo >= 0",
                        name="ck_catalogo_stock_minimo_non_negative"),
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
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    categoria: Mapped[Categoria | None] = relationship(back_populates="materiales")
