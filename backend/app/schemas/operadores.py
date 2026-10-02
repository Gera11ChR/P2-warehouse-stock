"""DTOs de los operadores rápidos de inventario: `+Cantidad` y `Mover`.

Cambio 2026-10-01-reportes-consumo-management (REQ-P2-INV-001..007).
Estos DTOs solo transportan parámetros: la suma, el descuento/acreditación
y la auditoría inmutable viven íntegros en PostgreSQL
(`fn_sumar_cantidad` / `fn_mover_material`). CERO aritmética de stock en
Python.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InventarioTipo = Literal["GENERAL", "FO"]
ModuloFo = Literal["PAQUETE", "EN_USO"]


class SumarCantidadRequest(BaseModel):
    """`+Cantidad`: adición directa al stock existente (sin flujo TEAMS)."""

    model_config = ConfigDict(extra="forbid")

    destino: InventarioTipo
    modulo: ModuloFo | None = Field(
        default=None, description="Obligatorio cuando destino = FO"
    )
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    # Sin `gt=0`: la regla (cantidad > 0) es autoridad del SP y devuelve 400
    # (contrato); Pydantic solo garantiza el tipo entero.
    cantidad: int
    clave_idempotencia: str | None = Field(
        default=None, min_length=1, max_length=100
    )

    @model_validator(mode="after")
    def _check_modulo(self) -> "SumarCantidadRequest":
        if self.destino == "FO" and self.modulo is None:
            raise ValueError("modulo es obligatorio cuando destino = FO.")
        if self.destino == "GENERAL" and self.modulo is not None:
            raise ValueError("modulo solo aplica cuando destino = FO.")
        return self


class SumarCantidadOut(BaseModel):
    destino: InventarioTipo
    modulo: ModuloFo | None
    material_id: int
    stock_nuevo: int
    reenvio_idempotente: bool = False


class MoverMaterialRequest(BaseModel):
    """`Mover`: transferencia directa General <-> FO (cantidad parcial)."""

    model_config = ConfigDict(extra="forbid")

    origen: InventarioTipo
    origen_modulo: ModuloFo | None = None
    destino: InventarioTipo
    destino_modulo: ModuloFo | None = None
    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    # Sin `gt=0`: la regla (cantidad > 0) es autoridad del SP y devuelve 400
    # (contrato); Pydantic solo garantiza el tipo entero.
    cantidad: int
    clave_idempotencia: str | None = Field(
        default=None, min_length=1, max_length=100
    )

    @model_validator(mode="after")
    def _check_modulos(self) -> "MoverMaterialRequest":
        if self.origen == "FO" and self.origen_modulo is None:
            raise ValueError("origen_modulo es obligatorio cuando origen = FO.")
        if self.origen == "GENERAL" and self.origen_modulo is not None:
            raise ValueError("origen_modulo solo aplica cuando origen = FO.")
        if self.destino == "FO" and self.destino_modulo is None:
            raise ValueError("destino_modulo es obligatorio cuando destino = FO.")
        if self.destino == "GENERAL" and self.destino_modulo is not None:
            raise ValueError("destino_modulo solo aplica cuando destino = FO.")
        return self


class MoverMaterialOut(BaseModel):
    material_id: int
    origen: InventarioTipo
    origen_modulo: ModuloFo | None
    destino: InventarioTipo
    destino_modulo: ModuloFo | None
    stock_origen: int
    stock_destino: int
    reenvio_idempotente: bool = False
