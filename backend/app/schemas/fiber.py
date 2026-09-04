from pydantic import BaseModel, ConfigDict, Field


class FiberVariantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(min_length=1, max_length=50)
    variante: str = Field(min_length=1, max_length=100)
    metros_restantes: int = Field(ge=0)
    cantidad: int = Field(default=0, ge=0)
    almacen_id: str | None = None


class FiberVariantOut(BaseModel):
    id: int
    codigo: str
    descripcion: str | None
    variante: str
    metros_restantes: int
    stock_actual: int
    almacen: str | None


class FiberVariantListOut(BaseModel):
    items: list[FiberVariantOut]
