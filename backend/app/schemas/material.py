from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


def _validate_um(value: str | None) -> str | None:
    if value is not None and value not in SUPPORTED_UNITS:
        raise ValueError(f"u_m debe ser una unidad soportada: {SUPPORTED_UNITS}")
    return value


class CategoriaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=100)


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    is_active: bool


class MaterialCreate(BaseModel):
    """Alta de material. Selector dual de categorías: `categoria_id` (rama A)
    o `nueva_categoria` (rama B, texto libre). El campo legacy `tipo` no existe.
    `id_lista` es autogenerado por PostgreSQL: no se acepta en el payload."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = None
    nueva_categoria: str | None = Field(default=None, max_length=100)
    u_m: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    stock_inicial: int | None = Field(default=None, ge=0)
    seccion_id: int | None = None

    _check_um = field_validator("u_m")(_validate_um)

    @model_validator(mode="after")
    def _check_categoria_dual(self) -> "MaterialCreate":
        if self.categoria_id is not None and self.nueva_categoria:
            raise ValueError(
                "Use solo una rama del selector dual: categoria_id o nueva_categoria."
            )
        return self

    @model_validator(mode="after")
    def _check_stock_inicial(self) -> "MaterialCreate":
        if self.stock_inicial is not None and self.stock_inicial > 0:
            if self.seccion_id is None:
                raise ValueError(
                    "seccion_id es obligatorio cuando se declara stock_inicial."
                )
        return self


class MaterialUpdate(BaseModel):
    """Edición de material. `id_lista` es INMUTABLE: no existe como campo de
    escritura. El stock nunca se modifica por esta vía (solo catálogo)."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = None
    nueva_categoria: str | None = Field(default=None, max_length=100)
    u_m: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    _check_um = field_validator("u_m")(_validate_um)

    @model_validator(mode="after")
    def _check_categoria_dual(self) -> "MaterialUpdate":
        if self.categoria_id is not None and self.nueva_categoria:
            raise ValueError(
                "Use solo una rama del selector dual: categoria_id o nueva_categoria."
            )
        return self


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_lista: int
    codigo: str | None
    descripcion: str
    categoria_id: int | None
    categoria: str | None
    u_m: str | None
    stock_minimo: int | None
    is_active: bool


class MaterialListOut(BaseModel):
    materiales: list[MaterialOut]
