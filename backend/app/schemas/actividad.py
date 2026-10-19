"""DTOs del flujo ACTIVIDADES por Unidad (0029, paquete
2026-10-actividades-unidad, plan §3.2).

Contrato Backend-First congelable en T7: los nombres, tipos y límites de
estos DTOs son la fuente del snapshot OpenAPI. `ActividadCreate` es
`extra="forbid"` y NO acepta folio, fecha, materiales, valor unitario ni
usuario (los decide PostgreSQL; REQ-ACT-008/009/010).
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

LARGO_VEHICULO = 100
LARGO_CLIENTES = 500
LARGO_DIRECCIONES = 500
LARGO_COMENTARIOS = 2000
LARGO_ACTIVIDAD = 500
MAX_ACTIVIDADES = 30


def _validar_controles(valor: str, *, permitir_salto: bool) -> None:
    """Rechaza caracteres de control C0 (salvo `\\n` cuando se permite),
    DEL (0x7F) y C1 (0x80-0x9F) — REQ-ACT-013."""
    for ch in valor:
        orden = ord(ch)
        if orden < 0x20 and not (permitir_salto and ch == "\n"):
            raise ValueError("contiene caracteres de control no permitidos")
        if 0x7F <= orden <= 0x9F:
            raise ValueError("contiene caracteres de control no permitidos")
    try:
        # Sustitutos Unicode sueltos (U+D800..U+DFFF) no son codificables en
        # UTF-8: el driver los rechazaría con 500 (REQ-ACT-013/019).
        valor.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("contiene caracteres Unicode no válidos") from exc


class ActividadMaterialOut(BaseModel):
    """Material consumido dentro del snapshot (jsonb): valores como números
    JSON. Solo lectura."""

    model_config = ConfigDict(extra="forbid")

    material_id: int
    codigo: str | None
    descripcion: str
    u_m: str | None
    cantidad_consumida: float
    valor_unitario: float


class ActividadPendienteSeguimiento(BaseModel):
    """Seguimiento CERRADA más reciente sin actividad (fn_actividad_pendiente):
    sus materiales y el valor unitario VIGENTE al momento de la consulta."""

    model_config = ConfigDict(extra="forbid")

    seguimiento_id: int
    fecha_cierre: datetime
    materiales: list[ActividadMaterialOut]


class ActividadPendienteOut(BaseModel):
    """GET /pendiente: `seguimiento: null` si la Unidad no tiene seguimiento
    pendiente de actividad (RF-3)."""

    seguimiento: ActividadPendienteSeguimiento | None


class ActividadCreate(BaseModel):
    """Confirmación de actividad. El frontend descarta las celdas vacías; el
    backend además las rechaza (defensa en profundidad, RF-6)."""

    model_config = ConfigDict(extra="forbid")

    seguimiento_id: int = Field(gt=0, le=2147483647)
    vehiculo: str = Field(strict=True, min_length=1, max_length=LARGO_VEHICULO)
    clientes: str = Field(strict=True, min_length=1, max_length=LARGO_CLIENTES)
    direcciones: str = Field(strict=True, min_length=1, max_length=LARGO_DIRECCIONES)
    actividades: list[
        Annotated[str, Field(strict=True, min_length=1, max_length=LARGO_ACTIVIDAD)]
    ] = Field(min_length=1, max_length=MAX_ACTIVIDADES)
    comentarios: str | None = Field(
        default=None, strict=True, max_length=LARGO_COMENTARIOS
    )

    @field_validator("vehiculo", "clientes", "direcciones")
    @classmethod
    def _texto_obligatorio_sin_controles(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el campo es obligatorio (texto no vacío)")
        _validar_controles(valor, permitir_salto=False)
        return valor

    @field_validator("actividades")
    @classmethod
    def _celdas_validas(cls, valores: list[str]) -> list[str]:
        limpias = [celda.strip() for celda in valores]
        if any(not celda for celda in limpias):
            raise ValueError("cada actividad debe ser un texto de 1 a 500 caracteres")
        if any(len(celda) > LARGO_ACTIVIDAD for celda in limpias):
            raise ValueError("cada actividad debe ser un texto de 1 a 500 caracteres")
        for celda in limpias:
            _validar_controles(celda, permitir_salto=False)
        return limpias

    @field_validator("comentarios")
    @classmethod
    def _comentarios_validos(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        _validar_controles(valor, permitir_salto=True)
        return valor


class ActividadOut(BaseModel):
    """Eco de lectura de una actividad confirmada. `folio` es presentación
    pura (`R` + folio_num con 4 dígitos mínimo), nunca entrada del cliente."""

    model_config = ConfigDict(extra="forbid")

    actividad_id: int
    folio: str
    folio_num: int
    seguimiento_id: int
    equipo_id: int
    equipo_nombre: str
    fecha: datetime
    usuario: str
    vehiculo: str
    clientes: str
    direcciones: str
    actividades: list[str]
    comentarios: str | None
    materiales: list[ActividadMaterialOut]


class ActividadListOut(BaseModel):
    """GET por Unidad: más reciente primero (RF-16)."""

    items: list[ActividadOut]
    total: int
