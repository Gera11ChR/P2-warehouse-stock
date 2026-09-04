from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamInventoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipo: str = Field(min_length=1, max_length=100)
    usuario: str = Field(min_length=1, max_length=100)
    codigo: str = Field(min_length=1, max_length=50)
    cantidad: int = Field(gt=0)


class TeamInventoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipo: str | None = Field(default=None, min_length=1, max_length=100)
    usuario: str | None = Field(default=None, min_length=1, max_length=100)
    cantidad: int | None = Field(default=None, gt=0)


class TeamInventoryOut(BaseModel):
    id: int
    equipo: str
    usuario: str
    codigo: str
    descripcion: str | None
    cantidad: int
    ultima_modificacion: datetime


class TeamInventoryListOut(BaseModel):
    items: list[TeamInventoryOut]
