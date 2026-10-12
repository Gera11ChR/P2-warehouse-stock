from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DetalleLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: int = Field(gt=0, description="Referencia a id_lista inmutable")
    cantidad: int = Field(gt=0)
    # TEAMS (0026): sección de ORIGEN de la línea (Inventario General o Fibra
    # Óptica). Opcional: si se omite, la línea hereda `origen_almacen_id` de
    # la cabecera (payload legado). Prohibido en DEVOL.
    origen_almacen_id: int | None = Field(default=None, gt=0)


class MovimientoBorradorCreate(BaseModel):
    """Borrador TEAMS/DEVOL. La validación de stock disponible NO ocurre aquí:
    se delega íntegramente a fn_procesar_movimiento en PostgreSQL.

    TEAMS multi-origen (0026): cada línea puede traer su `origen_almacen_id`;
    las que no lo traen heredan el de la cabecera. La cabecera queda con el
    origen común o NULL si el carrito es mixto (lo fija el servicio)."""

    model_config = ConfigDict(extra="forbid")

    tipo_movimiento: Literal["TEAMS", "DEVOL"]
    origen_almacen_id: int | None = None
    destino_almacen_id: int | None = None
    origen_equipo_id: int | None = None
    destino_equipo_id: int | None = None
    observaciones: str | None = Field(default=None, max_length=2000)
    detalle: list[DetalleLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_extremos(self) -> "MovimientoBorradorCreate":
        if self.tipo_movimiento == "TEAMS":
            if self.destino_equipo_id is None:
                raise ValueError("TEAMS requiere destino_equipo_id.")
            if self.origen_almacen_id is None and any(
                line.origen_almacen_id is None for line in self.detalle
            ):
                raise ValueError(
                    "TEAMS requiere origen_almacen_id (cabecera o por línea)."
                )
        else:
            if self.origen_equipo_id is None or self.destino_almacen_id is None:
                raise ValueError(
                    "DEVOL requiere origen_equipo_id y destino_almacen_id."
                )
            if any(line.origen_almacen_id is not None for line in self.detalle):
                raise ValueError(
                    "DEVOL no admite origen_almacen_id por línea."
                )
        return self

    @model_validator(mode="after")
    def _check_detalle_unico(self) -> "MovimientoBorradorCreate":
        ids = [line.material_id for line in self.detalle]
        if len(ids) != len(set(ids)):
            raise ValueError("Detalle con material_id duplicado.")
        return self


class MovimientoBorradorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observaciones: str | None = Field(default=None, max_length=2000)
    detalle: list[DetalleLine] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _check_detalle_unico(self) -> "MovimientoBorradorUpdate":
        if self.detalle is not None:
            ids = [line.material_id for line in self.detalle]
            if len(ids) != len(set(ids)):
                raise ValueError("Detalle con material_id duplicado.")
        return self


class ProcesarRequest(BaseModel):
    """Payload literal del contrato OpenSpec para procesar movimientos."""

    model_config = ConfigDict(extra="forbid")

    movimiento_id: int = Field(gt=0)


class DetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_id: int
    cantidad: int
    origen_almacen_id: int | None = None


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_movimiento: Literal["TEAMS", "DEVOL"]
    estado: Literal["BORRADOR", "CONFIRMADO", "CANCELADO"]
    usuario: str
    origen_almacen_id: int | None
    destino_almacen_id: int | None
    origen_equipo_id: int | None
    destino_equipo_id: int | None
    observaciones: str | None
    detalle: list[DetalleOut]


class ProcesadoOut(BaseModel):
    movimiento_id: int
    estado: Literal["CONFIRMADO"]


class MovimientoListOut(BaseModel):
    movimientos: list[MovimientoOut]
