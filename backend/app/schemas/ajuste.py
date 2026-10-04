from pydantic import BaseModel, ConfigDict, Field


class CargaInicialRequest(BaseModel):
    """Alta de stock inicial delegada a fn_cargar_stock_inicial (idempotente:
    rechaza si ya existe registro en la sección)."""

    model_config = ConfigDict(extra="forbid")

    almacen_id: int = Field(gt=0)
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    cantidad: int = Field(ge=0)
    motivo: str | None = Field(default=None, max_length=500)


class AjusteStockAlmacenRequest(BaseModel):
    """Ajuste administrativo delegado a fn_ajustar_stock_almacen (recalcula
    diferencial y audita en SQL). Ergonomía `justificacion_opcional`
    (REQ-ERG-005): `motivo` es OPCIONAL — se acepta `null`, cadena vacía o
    campo omitido; el evento AJUSTE_INVENTARIO registra el motivo tal como
    llega (Constitution 2.4: ledger inmutable)."""

    model_config = ConfigDict(extra="forbid")

    almacen_id: int = Field(gt=0)
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    nuevo_stock: int = Field(ge=0)
    motivo: str | None = Field(default=None, max_length=500)


class AjusteOut(BaseModel):
    almacen_id: int
    material_id: int
