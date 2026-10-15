"""DTOs de los operadores rápidos de inventario: `+Cantidad` y `Mover`.

Cambio 2026-10-fo-unificado-valor-unitario (RF-1/RF-6): los campos de
módulo (`modulo`/`origen_modulo`/`destino_modulo`) desaparecen del
contrato — el Inventario FO es único por material; enviarlos → 422
(`extra="forbid"`). Las cantidades pasan a decimales (hasta 3 decimales,
máximo `999 999 999.999`) sustituyendo la cota INT4.

Estos DTOs solo transportan parámetros: la suma, el descuento/acreditación
y la auditoría inmutable viven íntegros en PostgreSQL
(`fn_sumar_cantidad` / `fn_mover_material`). CERO aritmética de stock en
Python.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas._tipos import CantidadDecimal

InventarioTipo = Literal["GENERAL", "FO"]

# Cantidad de los operadores rápidos SIN cota de signo: la regla
# (cantidad > 0) es autoridad del SP y devuelve 400 (contrato vigente);
# Pydantic garantiza las cotas decimales (sobre-precisión/desborde → 422,
# plan §2.1).
CantidadOperador = Annotated[
    Decimal, Field(max_digits=12, decimal_places=3, allow_inf_nan=False)
]


class SumarCantidadRequest(BaseModel):
    """`+Cantidad`: adición directa al stock existente (sin flujo TEAMS)."""

    model_config = ConfigDict(extra="forbid")

    destino: InventarioTipo
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    # Sin `gt=0`: la regla (cantidad > 0) es autoridad del SP y devuelve 400
    # (contrato); Pydantic garantiza las cotas decimales (desbordes y
    # sobre-precisión -> 422 antes de llegar a PostgreSQL, M-3 sec-ops).
    cantidad: CantidadOperador
    clave_idempotencia: str | None = Field(
        default=None, min_length=1, max_length=100
    )


class SumarCantidadOut(BaseModel):
    destino: InventarioTipo
    material_id: int
    stock_nuevo: CantidadDecimal
    reenvio_idempotente: bool = False


class MoverMaterialRequest(BaseModel):
    """`Mover`: transferencia directa General <-> Inventario FO (cantidad
    parcial). Sin campos de módulo (RF-1)."""

    model_config = ConfigDict(extra="forbid")

    origen: InventarioTipo
    destino: InventarioTipo
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    # Sin `gt=0`: la regla (cantidad > 0) es autoridad del SP y devuelve 400
    # (contrato); Pydantic garantiza las cotas decimales (desbordes y
    # sobre-precisión -> 422 antes de llegar a PostgreSQL, M-3 sec-ops).
    cantidad: CantidadOperador
    clave_idempotencia: str | None = Field(
        default=None, min_length=1, max_length=100
    )


class MoverMaterialOut(BaseModel):
    material_id: int
    origen: InventarioTipo
    destino: InventarioTipo
    stock_origen: CantidadDecimal
    stock_destino: CantidadDecimal
    reenvio_idempotente: bool = False
