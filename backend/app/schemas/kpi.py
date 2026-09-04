from pydantic import BaseModel


class KpisOut(BaseModel):
    total_materiales: int
    stock_total: int
    alertas_stock: int
    transferencias_hoy: int
