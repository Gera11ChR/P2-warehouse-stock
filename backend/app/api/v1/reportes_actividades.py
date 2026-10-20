"""Reporte oficial de ACTIVIDADES (paquete 2026-10-actividades-reportes,
Etapa 2/3) — router FastAPI de `GET /reportes/actividades`.

Contrato (plan §3.4/§3.5, REQ-REP-002..005, 009..011, 016):
  * `formato=json` (por defecto): `ActividadListOut` (DTO congelado de la
    Etapa 1), ordenado de la más reciente a la más antigua.
  * `formato=xlsx`: libro de una hoja por folio sobre la plantilla
    corporativa «REPORTE DE ACTIVIDADES.xlsx», generado por
    `services.plantilla_reporte_actividades` en `run_in_threadpool`
    (CPU-bound fuera del event loop, REQ-REP-010).

Aislamiento (Constitution 3.1, REQ-REP-003, patrón de `/reportes/entrega`):
el administrador ve todas las Unidades; el actor regular con `equipo_id`
exige pertenencia (403) y sin él queda limitado a `equipos_visibles`
(conjunto vacío ⇒ cortocircuito sin consultar: 200 vacío en json, 404 en
xlsx). Un `actividad_id` ajeno se comporta como inexistente (vacío / 404)
sin revelar su existencia.

Precedencia (REQ-REP-004/011): validación de parámetros (422, incluidos
`extra="forbid"` y `desde > hasta`, ANTES de autorización y consulta) →
autorización (403) → consulta (200/404). Nunca 500 por reglas de negocio.

Límites del libro (plan D-1/D-11, REQ-REP-009/010): máximo
`MAX_HOJAS_XLSX` folios (422 `LIMITE_HOJAS_EXCEDIDO`) y `MAX_FILAS_XLSX`
filas inyectadas (422 `LIMITE_FILAS_EXCEDIDO`), evaluados con
`LIMIT MAX_HOJAS_XLSX + 1` sin cargar todas las filas.

Solo lectura (REQ-REP-016): cero escrituras, cero `session.begin()` de
escritura y cero eventos de auditoría; la única consulta es la lectura
tipada de `services.reportes_actividades`.
"""

from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import REPORTES_TZ
from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.actividad import ActividadListOut
from app.security import (
    ActorContext,
    assert_equipo_access,
    equipos_visibles,
    get_current_actor,
)
from app.services import plantilla_reporte
from app.services import plantilla_reporte_actividades
from app.services import reportes_actividades as reportes_svc

router = APIRouter(prefix="/reportes", tags=["reportes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


class FiltrosReporteActividades(BaseModel):
    """Parámetros de GET /reportes/actividades. extra="forbid": un
    parámetro no declarado (p. ej. acta_id) responde 422 extra_forbidden
    (REQ-REP-011, F-03)."""

    model_config = ConfigDict(extra="forbid")

    equipo_id: int | None = Field(default=None, gt=0)
    desde: date | None = None
    hasta: date | None = None
    actividad_id: int | None = Field(default=None, gt=0)
    formato: Literal["json", "xlsx"] = "json"


# Códigos del contrato (plan §3.5) documentados en OpenAPI para el
# consumidor (State-Agent): solo descripción, el comportamiento lo fijan
# los handlers. El 422 de validación lo documenta FastAPI por defecto.
_R_400 = {"description": "Identificador numérico fuera de rango INT4 (NUMERIC_OUT_OF_RANGE)"}
_R_403 = {"description": "Actor sin acceso a la Unidad (no integrante ni administrador)"}
_R_404 = {
    "description": "Sin actividades para los filtros indicados; la Unidad ajena al "
    "actor se comporta como inexistente"
}


@router.get(
    "/actividades",
    response_model=ActividadListOut,
    responses={400: _R_400, 403: _R_403, 404: _R_404},
)
async def reporte_actividades(
    filtros: Annotated[FiltrosReporteActividades, Query()],
    session: SessionDep,
    actor_ctx: ActorDep,
) -> ActividadListOut | Response:
    """Reporte de actividades confirmadas: `formato=json` devuelve el
    listado para la UI (200, más reciente primero); `formato=xlsx`
    descarga el libro de una hoja por folio sobre la plantilla
    corporativa, con tope de 100 folios (REQ-REP-009).

    Códigos del contrato (REQ-REP-011): 200 con resultados; 400
    NUMERIC_OUT_OF_RANGE (identificador positivo fuera de INT4); 403 actor
    sin acceso a la Unidad indicada; 404 sin actividades para los filtros
    o Unidad ajena al actor (indistinguible de inexistente); 422
    parámetros inválidos o no declarados, `RANGO_FECHAS_INVALIDO`,
    `LIMITE_HOJAS_EXCEDIDO` (más de 100 folios) o `LIMITE_FILAS_EXCEDIDO`
    (más de 10 000 filas inyectadas)."""
    # (a) Validación previa a autorización y consulta (REQ-REP-004): el
    # rango inválido responde 422 sin tocar datos de negocio.
    if filtros.desde and filtros.hasta and filtros.desde > filtros.hasta:
        raise BusinessRuleError(
            "El rango de fechas es inválido: desde no puede ser posterior a hasta.",
            code="RANGO_FECHAS_INVALIDO",
            status_code=422,
        )

    # (b) Aislamiento por Unidad (REQ-REP-003, patrón de /reportes/entrega).
    solo_equipos: set[int] | None = None
    if not actor_ctx.es_admin:
        if filtros.equipo_id is not None:
            await assert_equipo_access(actor_ctx, session, filtros.equipo_id)
        else:
            solo_equipos = await equipos_visibles(actor_ctx, session)
            if not solo_equipos:
                # Sin Unidades visibles: cortocircuito sin consultar.
                if filtros.formato == "json":
                    return ActividadListOut(items=[], total=0)
                raise BusinessRuleError(
                    "No hay actividades para los filtros indicados",
                    coordinates=[{"formato": "xlsx"}],
                    status_code=404,
                )

    # (c) json: listado para la UI, más reciente primero (REQ-REP-002).
    if filtros.formato == "json":
        actividades = await reportes_svc.consultar_actividades(
            session,
            zona=REPORTES_TZ,
            equipo_id=filtros.equipo_id,
            actividad_id=filtros.actividad_id,
            desde=filtros.desde,
            hasta=filtros.hasta,
            solo_equipos=solo_equipos,
        )
        return ActividadListOut(items=actividades, total=len(actividades))

    # (d) xlsx: una hoja por folio en orden de folio ascendente, con los
    # topes del libro evaluados antes de generar (REQ-REP-009/010).
    actividades = await reportes_svc.consultar_actividades(
        session,
        zona=REPORTES_TZ,
        equipo_id=filtros.equipo_id,
        actividad_id=filtros.actividad_id,
        desde=filtros.desde,
        hasta=filtros.hasta,
        solo_equipos=solo_equipos,
        limite=reportes_svc.MAX_HOJAS_XLSX + 1,
        orden_folio=True,
    )
    if not actividades:
        raise BusinessRuleError(
            "No hay actividades para los filtros indicados",
            coordinates=[{"formato": "xlsx"}],
            status_code=404,
        )
    if len(actividades) > reportes_svc.MAX_HOJAS_XLSX:
        raise BusinessRuleError(
            f"El libro excede el tope de {reportes_svc.MAX_HOJAS_XLSX} folios; "
            "acote los filtros (Unidad, fechas u operación) e intente de nuevo",
            code="LIMITE_HOJAS_EXCEDIDO",
            coordinates=[{"formato": "xlsx", "actividades": len(actividades)}],
            status_code=422,
        )
    filas = sum(len(a.materiales) + len(a.actividades) for a in actividades)
    if filas > reportes_svc.MAX_FILAS_XLSX:
        raise BusinessRuleError(
            f"El libro excede el límite de {reportes_svc.MAX_FILAS_XLSX} filas "
            "inyectadas (materiales + actividades); acote los filtros e "
            "intente de nuevo",
            code="LIMITE_FILAS_EXCEDIDO",
            coordinates=[{"formato": "xlsx", "filas": filas}],
            status_code=422,
        )
    # openpyxl es síncrono/CPU-bound: fuera del event loop (REQ-REP-010).
    zona = ZoneInfo(REPORTES_TZ)
    contenido = await run_in_threadpool(
        plantilla_reporte_actividades.generar_reporte_actividades,
        actividades=actividades,
        zona=zona,
    )
    nombre = plantilla_reporte_actividades.nombre_archivo_actividades(
        actividades=actividades, zona=zona
    )
    return Response(
        content=contenido,
        media_type=plantilla_reporte.MEDIA_TYPE_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
