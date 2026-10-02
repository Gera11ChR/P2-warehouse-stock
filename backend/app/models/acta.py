from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActaReporte(Base):
    """Registro persistente de actas de reporte (0020) — APPEND-ONLY.

    Cada fila guarda un SNAPSHOT jsonb del estado EN EL MOMENTO DEL EVENTO;
    el XLSX (Fase 2) se genera bajo demanda a partir de ese snapshot y
    nunca desde el stock mutable actual (REQ-P2-REP-003/004):

      * tipo 'ENTREGA'  -> movimiento_id (TEAMS confirmado, trigger
        tg_acta_entrega dentro de la MISMA transacción SQL).
      * tipo 'CONSUMO'  -> seguimiento_id (cierre via fn_cerrar_seguimiento
        extendido en 0020).

    La cancelación posterior de un movimiento NO elimina su acta: el
    snapshot permanece como registro histórico inmutable del evento.
    """

    __tablename__ = "actas_reportes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    movimiento_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_cabecera.id", ondelete="RESTRICT")
    )
    seguimiento_id: Mapped[int | None] = mapped_column(
        ForeignKey("seguimientos.id", ondelete="RESTRICT")
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
