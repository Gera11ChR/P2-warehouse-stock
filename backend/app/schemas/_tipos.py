"""Tipos decimales comunes del contrato API (plan §2.1, cambio
2026-10-fo-unificado-valor-unitario — RF-2/RF-6).

Cantidad decimal: no negativa con hasta 3 decimales y hasta 12 dígitos en
total (máximo `999 999 999.999`).

  * Entrada: `Field(max_digits=12, decimal_places=3)` rechaza sobre-precisión
    y desbordamiento con 422 (jamás redondea en silencio, E3/E4/E5).
  * Salida: número JSON (TypeScript `number`). `float()` es exacto para
    ≤15 dígitos significativos, suficiente para los valores de columna
    (12 dígitos) — plan §2.1.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer

CantidadDecimal = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=3, allow_inf_nan=False),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
CantidadMovimiento = Annotated[
    Decimal,
    Field(gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
