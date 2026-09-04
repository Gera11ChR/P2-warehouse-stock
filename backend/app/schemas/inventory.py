from pydantic import BaseModel, ConfigDict


class InventoryRowOut(BaseModel):
    codigo: str
    descripcion: str | None
    um: str | None
    categoria: str | None
    tipo: str
    stock_actual: int
    stock_minimo: int | None
    alerta_stock: bool
    almacen: str
    almacen_id: str


class InventoryListOut(BaseModel):
    items: list[InventoryRowOut]
