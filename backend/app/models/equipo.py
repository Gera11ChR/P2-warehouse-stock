from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Equipo(Base):
    __tablename__ = "equipos"

    equipo_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    integrantes: Mapped[list["EquipoIntegrante"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )


class EquipoIntegrante(Base):
    __tablename__ = "equipos_integrantes"
    __table_args__ = (
        UniqueConstraint("equipo_id", "usuario",
                         name="uq_equipos_integrantes_usuario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(
        ForeignKey("equipos.equipo_id", ondelete="RESTRICT"), nullable=False
    )
    usuario: Mapped[str] = mapped_column(String(100), nullable=False)

    equipo: Mapped[Equipo] = relationship(back_populates="integrantes")
