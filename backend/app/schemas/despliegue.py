"""DTOs del flujo DESPLIEGUE de campo (migración 0014).

Toda la aritmética de stock del despliegue vive en PostgreSQL
(`fn_crear_despliegue` / `fn_cerrar_despliegue`); estos DTOs solo transportan
la lista de materiales, los sobrantes del cierre y los ecos de lectura.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DespliegueItemIn(BaseModel):
    """Línea de apertura: material y cantidad tomada del inventario del
    equipo (validación autoritativa en fn_crear_despliegue)."""

    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    cantidad_tomada: int = Field(gt=0)


class DespliegueCreate(BaseModel):
    """Apertura de despliegue (estado ABIERTA)."""

    model_config = ConfigDict(extra="forbid")

    observaciones: str | None = Field(default=None, max_length=2000)
    items: list[DespliegueItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_items_unicos(self) -> "DespliegueCreate":
        ids = [item.material_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("items con material_id duplicado.")
        return self


class SobranteLine(BaseModel):
    """Línea de sobrante del cierre (material devuelto al inventario)."""

    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0)
    cantidad_sobrante: int = Field(ge=0)


class CerrarDespliegueRequest(BaseModel):
    """Cierre de despliegue. Las líneas omitidas se cierran con sobrante 0."""

    model_config = ConfigDict(extra="forbid")

    sobrantes: list[SobranteLine] = Field(default_factory=list)
    observaciones_cierre: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check_sobrantes_unicos(self) -> "CerrarDespliegueRequest":
        ids = [line.material_id for line in self.sobrantes]
        if len(ids) != len(set(ids)):
            raise ValueError("sobrantes con material_id duplicado.")
        return self


class DespliegueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    cantidad_tomada: int
    cantidad_sobrante: int | None
    cantidad_consumida: int | None


class DespliegueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    fecha: date
    observaciones: str | None
    usuario: str
    estado: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    items: list[DespliegueItemOut]


class DespliegueListOut(BaseModel):
    despliegues: list[DespliegueOut]
