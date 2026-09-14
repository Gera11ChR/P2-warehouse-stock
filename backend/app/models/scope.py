from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActorAlmacenScope(Base):
    """RBAC resource-scoped (Constitution 3.2): alcance de escritura de un
    actor sobre secciones de inventario específicas."""

    __tablename__ = "actor_almacen_scopes"

    actor_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    almacen_id: Mapped[int] = mapped_column(
        ForeignKey("secciones.almacen_id", ondelete="RESTRICT"), primary_key=True
    )
