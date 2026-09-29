from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class CategoriaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=100)


class CategoriaUpdate(BaseModel):
    """Renombrado administrativo de categoría (solo administradores)."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=100)


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    is_active: bool


class UmsOut(BaseModel):
    """Unidad de Medida maestra (tabla `ums`, 0014): fuente única del
    selector de U.M. del catálogo y de la configuración local de equipos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    is_active: bool


class UmsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=50)


class UmsUpdate(BaseModel):
    """Renombrado administrativo de U.M. (solo administradores)."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=50)


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
    """Edición de material (alcance: Inventario General, REQ-UI-004).

    `id_lista` es INMUTABLE: no existe como campo de escritura.

    El stock NO se actualiza por ORM: si `stock_actual` viene en el payload,
    el servicio calcula el delta (Nuevo − Actual) y lo enruta a
    `fn_ajustar_stock_almacen` (vía `fn_ajustar_stock_general`) con
    `motivo` obligatorio y no vacío, de modo que PostgreSQL registre el
    ajuste como evento de Auditoría (Constitution 2.4: ledger inmutable;
    jamás UPDATE directo de stock). Este campo solo aplica al Inventario
    General, nunca a inventarios de Equipos ni de Fibra Óptica."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    codigo: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = None
    nueva_categoria: str | None = Field(default=None, max_length=100)
    u_m: str | None = None
    stock_minimo: int | None = Field(default=None, ge=0)
    stock_actual: int | None = Field(default=None, ge=0)
    motivo: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _check_categoria_dual(self) -> "MaterialUpdate":
        if self.categoria_id is not None and self.nueva_categoria:
            raise ValueError(
                "Use solo una rama del selector dual: categoria_id o nueva_categoria."
            )
        return self

    @model_validator(mode="after")
    def _check_stock_motivo(self) -> "MaterialUpdate":
        """REQ-API-003: si se envía `stock_actual`, el `motivo` es
        obligatorio y no vacío; el ajuste debe quedar trazado en el ledger."""
        if self.stock_actual is not None:
            if self.motivo is None or not self.motivo.strip():
                raise ValueError(
                    "motivo es obligatorio y no puede estar vacío cuando se "
                    "modifica stock_actual: todo ajuste de stock debe quedar "
                    "trazado en el ledger de Auditoría."
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
    """Listado del catálogo. `start_index` (REQ-API-006) es el índice ordinal
    de inicio para que el frontend renderice números de lista continuos
    1-indexed sin descargar el catálogo completo (Principio 4)."""

    start_index: int = 1
    materiales: list[MaterialOut]


class BusquedaGranelParams(BaseModel):
    """Parámetros de consulta del Buscador a granel (REQ-UI-007,
    REQ-API-006/007). El rango por número de lista se resuelve 100 % en
    backend con posicionamiento ordinal determinista
    (`ORDER BY descripcion ASC, id_lista ASC`, `OFFSET = X - 1`,
    `LIMIT = Y - X + 1`); la respuesta devuelve `start_index = X`.
    Prohibido descargar datasets completos al cliente."""

    model_config = ConfigDict(extra="forbid")

    desde_numero_lista: int | None = Field(default=None, ge=1)
    hasta_numero_lista: int | None = Field(default=None, ge=1)
    desde_descripcion: str | None = Field(default=None, max_length=255)
    hasta_descripcion: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check_rango_numero_lista(self) -> "BusquedaGranelParams":
        if (
            self.desde_numero_lista is not None
            and self.hasta_numero_lista is not None
            and self.hasta_numero_lista < self.desde_numero_lista
        ):
            raise ValueError(
                "hasta_numero_lista debe ser mayor o igual que "
                "desde_numero_lista."
            )
        return self
