from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class EquipoConfigLocalUpdate(BaseModel):
    """Configuración operativa LOCAL de un material en un equipo
    (`equipo_material_config`, migración 0014): stock mínimo, categoría y
    U.M. de trabajo propias del equipo, sin tocar catálogo maestro ni stock.

    Patch semántico por equipo/material: al menos un campo debe enviarse;
    los campos ausentes conservan su valor actual."""

    model_config = ConfigDict(extra="forbid")

    stock_minimo_local: int | None = Field(default=None, ge=0)
    categoria_local_id: int | None = Field(default=None, gt=0)
    um_local_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_al_menos_un_campo(self) -> "EquipoConfigLocalUpdate":
        if all(
            valor is None
            for valor in (
                self.stock_minimo_local,
                self.categoria_local_id,
                self.um_local_id,
            )
        ):
            raise ValueError(
                "Debe indicar al menos un campo a actualizar."
            )
        return self


class EquipoConfigLocalOut(BaseModel):
    """Respuesta del PATCH de configuración local (equipo_material_config):
    contrato OpenAPI explícito (Constitution 5.1)."""

    model_config = ConfigDict(from_attributes=True)

    equipo_id: int
    material_id: int
    stock_minimo_local: int | None
    categoria_local_id: int | None
    um_local_id: int | None
    updated_at: datetime


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipo_id: int
    nombre: str
    descripcion: str | None
    is_active: bool
    integrantes: list[str]
