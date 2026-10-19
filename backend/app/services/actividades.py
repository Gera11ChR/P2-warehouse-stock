"""Lecturas del flujo ACTIVIDADES por Unidad — SOLO LECTURA.

La escritura la ejecuta exclusivamente `fn_crear_actividad` vía
services.transaccional (tabla append-only con trigger de inmutabilidad).
Este módulo resuelve el seguimiento pendiente (cálculo íntegro en
PostgreSQL: `fn_actividad_pendiente`) y el historial de actividades de la
Unidad con el folio formateado como presentación pura (cero aritmética de
negocio en Python).
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BusinessRuleError
from app.models import ActividadReporte, Equipo
from app.schemas.actividad import (
    ActividadListOut,
    ActividadOut,
    ActividadPendienteOut,
    ActividadPendienteSeguimiento,
)

_SQL_PENDIENTE = text(
    "SELECT seguimiento_id, fecha_cierre, materiales "
    "FROM fn_actividad_pendiente(:equipo_id)"
)


def _formato_folio(folio_num: int) -> str:
    """Presentación `R` + número con relleno de ceros a 4 dígitos mínimo
    (sin truncar)."""
    return f"R{folio_num:04d}"


def _construir_out(actividad: ActividadReporte, equipo_nombre: str) -> ActividadOut:
    return ActividadOut(
        actividad_id=actividad.id,
        folio=_formato_folio(actividad.folio_num),
        folio_num=actividad.folio_num,
        seguimiento_id=actividad.seguimiento_id,
        equipo_id=actividad.equipo_id,
        equipo_nombre=equipo_nombre,
        fecha=actividad.created_at,
        usuario=actividad.usuario,
        vehiculo=actividad.vehiculo,
        clientes=actividad.clientes,
        direcciones=actividad.direcciones,
        actividades=actividad.actividades,
        comentarios=actividad.comentarios,
        materiales=actividad.materiales,
    )


async def obtener_actividad_pendiente(
    session: AsyncSession, equipo_id: int
) -> ActividadPendienteOut:
    """Seguimiento CERRADA más reciente de la Unidad sin actividad, con sus
    materiales consumidos y el valor unitario vigente (RF-2). `None` si no
    hay (RF-3)."""
    fila = (
        await session.execute(_SQL_PENDIENTE, {"equipo_id": equipo_id})
    ).mappings().first()
    if fila is None:
        return ActividadPendienteOut(seguimiento=None)
    return ActividadPendienteOut(
        seguimiento=ActividadPendienteSeguimiento(
            seguimiento_id=fila["seguimiento_id"],
            fecha_cierre=fila["fecha_cierre"],
            materiales=fila["materiales"],
        )
    )


async def listar_actividades(
    session: AsyncSession, equipo_id: int
) -> ActividadListOut:
    """Historial de actividades confirmadas de la Unidad, más reciente
    primero (RF-16)."""
    filas = (
        await session.execute(
            select(ActividadReporte, Equipo.nombre)
            .join(Equipo, Equipo.equipo_id == ActividadReporte.equipo_id)
            .where(ActividadReporte.equipo_id == equipo_id)
            .order_by(ActividadReporte.created_at.desc(), ActividadReporte.id.desc())
        )
    ).all()
    items = [_construir_out(actividad, nombre) for actividad, nombre in filas]
    return ActividadListOut(items=items, total=len(items))


async def obtener_actividad(
    session: AsyncSession, equipo_id: int, actividad_id: int
) -> ActividadOut:
    """Eco de la actividad recién confirmada (usado por el POST para devolver
    el folio y la fecha asignados por PostgreSQL)."""
    fila = (
        await session.execute(
            select(ActividadReporte, Equipo.nombre)
            .join(Equipo, Equipo.equipo_id == ActividadReporte.equipo_id)
            .where(
                ActividadReporte.id == actividad_id,
                ActividadReporte.equipo_id == equipo_id,
            )
        )
    ).one_or_none()
    if fila is None:  # pragma: no cover - defensivo tras la inserción propia
        raise BusinessRuleError(
            "Actividad no encontrada",
            coordinates=[{"equipo_id": equipo_id, "actividad_id": actividad_id}],
            status_code=404,
        )
    return _construir_out(fila[0], fila[1])
