from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CancelarMovimientoRequest(BaseModel):
    """La reversión se delega a fn_cancelar_movimiento; el usuario autorizador
    proviene de CURRENT_USER en PostgreSQL (trazabilidad forense)."""

    model_config = ConfigDict(extra="forbid")

    motivo: str | None = Field(default=None, max_length=500)


class CanceladoOut(BaseModel):
    movimiento_id: int
    estado: Literal["CANCELADO"]
