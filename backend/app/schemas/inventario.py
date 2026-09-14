from pydantic import BaseModel, ConfigDict


class SeccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    almacen_id: int
    nombre: str
    tipo: str
    is_active: bool


class SeccionStockOut(BaseModel):
    """Fila de stock de una sección (JOIN catálogo, solo lectura)."""

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool


class CatalogoEquipoOut(BaseModel):
    """Fila de vw_inventario_equipo_completo: catálogo completo del equipo
    con stock 0 renderizado donde no existe registro físico (Sparse Model)."""

    equipo_id: int
    id_lista: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    stock_minimo: int | None
    stock_actual: int
    alerta_stock: bool
