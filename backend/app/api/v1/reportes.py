"""Reportes oficiales — Acta de Entrega y Acta de Consumo (XLSX).

  * GET /reportes/entrega  -> actas de entrega (TEAMS confirmado, hito A).
  * GET /reportes/consumo  -> actas de consumo (cierre de seguimiento, hito B).

`formato`:
  * `json` (por defecto): listado de actas para la tabla de la UI.
  * `normal` | `extenso`: descarga XLSX inyectando los datos en la plantilla
    corporativa correspondiente (nunca se genera un Excel desde cero). El
    formato CSV legacy queda DESCARTADO.

Las actas son snapshots jsonb escritos por PostgreSQL en la transacción del
evento; el XLSX se genera bajo demanda desde ese snapshot.

Aislamiento (Constitution 3.1): el actor regular solo ve los equipos donde
es integrante; con `equipo_id` explícito se exige pertenencia (403). El
administrador ve todos los equipos.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.reporte import ActaListOut
from app.security import (
    ActorContext,
    assert_equipo_access,
    equipos_visibles,
    get_current_actor,
)
from app.services import plantilla_reporte
from app.services import reportes as reportes_svc

router = APIRouter(prefix="/reportes", tags=["reportes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

FormatoReporte = Literal["json", "normal", "extenso"]


async def _reporte(
    *,
    tipo: Literal["ENTREGA", "CONSUMO"],
    session: AsyncSession,
    actor_ctx: ActorContext,
    equipo_id: int | None,
    desde: date | None,
    hasta: date | None,
    acta_id: int | None,
    formato: FormatoReporte,
) -> ActaListOut | Response:
    solo_equipos: set[int] | None = None
    if not actor_ctx.es_admin:
        if equipo_id is not None:
            await assert_equipo_access(actor_ctx, session, equipo_id)
        else:
            solo_equipos = await equipos_visibles(actor_ctx, session)
            if not solo_equipos:
                # Sin equipos visibles: nada que reportar.
                solo_equipos = set()

    actas = await reportes_svc.consultar_actas(
        session,
        tipo=tipo,
        acta_id=acta_id,
        equipo_id=equipo_id,
        desde=desde,
        hasta=hasta,
        solo_equipos=solo_equipos,
    )
    if formato == "json":
        return ActaListOut(actas=actas)

    if not actas:
        raise BusinessRuleError(
            "No hay actas para los filtros indicados",
            coordinates=[{"tipo": tipo, "formato": formato}],
            status_code=404,
        )
    lineas = reportes_svc.lineas_para_xlsx(tipo, actas)
    fecha = reportes_svc.fecha_documento(actas)
    # openpyxl es síncrono/CPU-bound: fuera del event loop.
    contenido = await run_in_threadpool(
        plantilla_reporte.generar_acta,
        tipo=tipo,
        formato=formato,
        fecha=fecha,
        lineas=lineas,
    )
    nombre = plantilla_reporte.nombre_archivo_acta(tipo, formato, fecha)
    return Response(
        content=contenido,
        media_type=plantilla_reporte.MEDIA_TYPE_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/entrega", response_model=ActaListOut)
async def reporte_entrega(
    session: SessionDep,
    actor_ctx: ActorDep,
    equipo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    acta_id: int | None = None,
    formato: FormatoReporte = "json",
) -> ActaListOut | Response:
    """Acta(s) de Entrega (hito A): generadas por PostgreSQL al confirmar un
    movimiento TEAMS (estado CONFIRMADO). `formato=normal|extenso` descarga
    el XLSX sobre la plantilla corporativa; `acta_id` exporta un acta
    individual."""
    return await _reporte(
        tipo="ENTREGA",
        session=session,
        actor_ctx=actor_ctx,
        equipo_id=equipo_id,
        desde=desde,
        hasta=hasta,
        acta_id=acta_id,
        formato=formato,
    )


@router.get("/consumo", response_model=ActaListOut)
async def reporte_consumo(
    session: SessionDep,
    actor_ctx: ActorDep,
    equipo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    acta_id: int | None = None,
    formato: FormatoReporte = "json",
) -> ActaListOut | Response:
    """Acta(s) de Consumo (hito B): generadas por PostgreSQL al cerrar un
    seguimiento. `formato=normal|extenso` descarga el XLSX (título "ACTA DE
    CONSUMO", CANT. = cantidad consumida) sobre la plantilla corporativa."""
    return await _reporte(
        tipo="CONSUMO",
        session=session,
        actor_ctx=actor_ctx,
        equipo_id=equipo_id,
        desde=desde,
        hasta=hasta,
        acta_id=acta_id,
        formato=formato,
    )
