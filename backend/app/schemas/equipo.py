from pydantic import BaseModel, ConfigDict, Field


class EquipoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    integrantes: list[str] = Field(default_factory=list, max_length=50)


class EquipoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=500)
    integrantes: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipo_id: int
    nombre: str
    descripcion: str | None
    is_active: bool
    integrantes: list[str]
