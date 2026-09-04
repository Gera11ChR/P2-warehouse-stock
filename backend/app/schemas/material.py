from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_UNITS = (
    "PZ",
    "LT",
    "CARRETE (1 KM)",
    "METRO (M)",
    "CARRETE (5 KM)",
    "BOLSA (500 PZ)",
    "PAQUETE (100 PZ)",
    "ROLLO",
    "EQUIPO",
    "UNIDAD",
)

SKU_TYPES = ("GENERAL", "FIBRA")


def _validate_um(value: str | None) -> str | None:
    if value is not None and value not in SUPPORTED_UNITS:
        raise ValueError(f"um debe ser una unidad soportada: {SUPPORTED_UNITS}")
    return value


def _validate_tipo(value: str | None) -> str | None:
    if value is not None and value not in SKU_TYPES:
        raise ValueError(f"tipo debe ser uno de {SKU_TYPES}")
    return value


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(min_length=1, max_length=50)
    descripcion: str | None = None
    um: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    categoria: str | None = None
    tipo: str = "GENERAL"

    _check_um = field_validator("um")(_validate_um)
    _check_tipo = field_validator("tipo")(_validate_tipo)


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = None
    um: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    categoria: str | None = None
    tipo: str | None = None

    _check_um = field_validator("um")(_validate_um)
    _check_tipo = field_validator("tipo")(_validate_tipo)


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    descripcion: str | None
    um: str | None
    stock_minimo: int | None
    categoria: str | None
    tipo: str


class MaterialListOut(BaseModel):
    materiales: list[MaterialOut]
