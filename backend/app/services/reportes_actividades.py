"""Consulta del reporte de ACTIVIDADES — SOLO LECTURA (T4, paquete
2026-10-actividades-reportes, Etapa 2/3; plan §2).

REGLAS:
  * REQ-REP-002: devuelve las actividades confirmadas que cumplen los
    filtros (`equipo_id`, `actividad_id`, `desde`, `hasta`, `solo_equipos`),
    combinables con semántica AND, ordenadas de la más reciente a la más
    antigua (`created_at DESC, id DESC`); con `orden_folio` el orden pasa a
    `folio_num ASC` (libro XLSX, REQ-REP-009).
  * REQ-REP-003: el aislamiento por Unidad llega como el conjunto
    `solo_equipos` calculado por el router (patrón de `/reportes/entrega`);
    un conjunto vacío produce cero filas.
  * REQ-REP-004: `desde`/`hasta` son días calendario completos de la ZONA
    DE NEGOCIO, que viaja como parámetro enlazado (nunca concatenada) a
    `timezone(zona, CAST(… AS timestamp))`; el `+ interval '1 day'` se
    calcula SIEMPRE en SQL, nunca con `timedelta` en Python (desbordaría
    con `hasta=9999-12-31` y daría HTTP 500 — F-04, verificado en T1).
  * REQ-REP-005: `actividad_id` filtra por identificador (AND con el
    resto de filtros).
  * REQ-REP-016: SOLO LECTURA: cero escrituras, cero eventos de auditoría
    y cero aritmética de negocio en Python (el mapeo reutiliza
    `_construir_out` de `services.actividades`, plan D-9).
  * La consulta se construye con SQLAlchemy ORM TIPADO (nunca `text()` sin
    tipos): solo con comparaciones tipadas PostgreSQL rechaza un
    identificador fuera de INT4 con SQLSTATE 22003 → 400 NUMERIC_OUT_OF_RANGE
    (plan §2/F-04, verificado en T1).
"""

from datetime import date

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActividadReporte, Equipo
from app.schemas.actividad import ActividadOut
from app.services.actividades import _construir_out

# ── Cotas del libro XLSX (plan D-1/D-11, REQ-REP-009/010) ─────────────────
# Las aplica el router de reportes en T5 (más de MAX_HOJAS_XLSX folios ⇒ 422
# LIMITE_HOJAS_EXCEDIDO; más de MAX_FILAS_XLSX filas inyectadas ⇒ 422
# LIMITE_FILAS_EXCEDIDO). Aquí solo se declaran: una única fuente de verdad.
MAX_HOJAS_XLSX = 100
MAX_FILAS_XLSX = 10_000


def _construir_stmt(
    *,
    zona: str,
    equipo_id: int | None = None,
    actividad_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    solo_equipos: set[int] | None = None,
    limite: int | None = None,
    orden_folio: bool = False,
) -> Select[ActividadReporte, str]:
    """SELECT tipado de `actividades_reportes` JOIN `equipos` con los
    filtros AND opcionales del plan §2 (sin ejecutar)."""
    stmt: Select[ActividadReporte, str] = (
        select(ActividadReporte, Equipo.nombre).join(
            Equipo, Equipo.equipo_id == ActividadReporte.equipo_id
        )
    )
    if equipo_id is not None:
        stmt = stmt.where(ActividadReporte.equipo_id == equipo_id)
    if actividad_id is not None:
        stmt = stmt.where(ActividadReporte.id == actividad_id)
    if solo_equipos is not None:
        # Conjunto vacío ⇒ 0 filas (el router, además, no consulta en ese
        # caso); verificado en T1 — REQ-REP-003.
        stmt = stmt.where(ActividadReporte.equipo_id.in_(solo_equipos))
    if desde is not None:
        stmt = stmt.where(
            ActividadReporte.created_at
            >= sa.func.timezone(zona, sa.cast(desde, sa.TIMESTAMP(timezone=False)))
        )
    if hasta is not None:
        stmt = stmt.where(
            ActividadReporte.created_at
            < sa.func.timezone(
                zona,
                sa.cast(hasta, sa.TIMESTAMP(timezone=False))
                + sa.cast(sa.text("interval '1 day'"), sa.Interval()),
            )
        )
    if orden_folio:
        stmt = stmt.order_by(ActividadReporte.folio_num.asc())
    else:
        stmt = stmt.order_by(
            ActividadReporte.created_at.desc(), ActividadReporte.id.desc()
        )
    if limite is not None:
        stmt = stmt.limit(limite)
    return stmt


async def consultar_actividades(
    session: AsyncSession,
    *,
    zona: str,
    equipo_id: int | None = None,
    actividad_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    solo_equipos: set[int] | None = None,
    limite: int | None = None,
    orden_folio: bool = False,
) -> list[ActividadOut]:
    """Consulta de solo lectura para `GET /reportes/actividades` (REQ-REP-002/
    003/004/005/016): filtros AND opcionales, `desde`/`hasta` como días
    completos en la zona de negocio (parámetro enlazado), orden por folio
    ascendente o por fecha descendente, y `limite` opcional.

    El mapeo a DTO reutiliza `_construir_out` (plan D-9): cero aritmética
    de negocio y cero escrituras en Python.
    """
    stmt = _construir_stmt(
        zona=zona,
        equipo_id=equipo_id,
        actividad_id=actividad_id,
        desde=desde,
        hasta=hasta,
        solo_equipos=solo_equipos,
        limite=limite,
        orden_folio=orden_folio,
    )
    filas = (await session.execute(stmt)).all()
    return [_construir_out(actividad, nombre) for actividad, nombre in filas]
