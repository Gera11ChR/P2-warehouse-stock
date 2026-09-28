"""Reportes de despliegues (0014) — lectura aislada por equipo.

GET /reportes/despliegues devuelve el historial plano de despliegues (todos
los estados) con filtros `equipo_id`, `desde`, `hasta` y formato `json`
(por defecto) o `csv` (descarga con Content-Disposition attachment y
sanitización anti-inyección de fórmulas).

Aislamiento (Constitution 3.1): el actor regular solo ve los equipos donde
es integrante; con `equipo_id` explícito se exige pertenencia (403). El
administrador ve todos los equipos.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.reporte import ReporteDespliegueListOut
from app.security import (
    ActorContext,
    assert_equipo_access,
    equipos_visibles,
    get_current_actor,
)
from app.services import reportes as reportes_svc

router = APIRouter(prefix="/reportes", tags=["reportes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/despliegues", response_model=ReporteDespliegueListOut)
async def reporte_despliegues(
    session: SessionDep,
    actor_ctx: ActorDep,
    equipo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    formato: Annotated[
        Literal["json", "csv"], Query(alias="format")
    ] = "json",
) -> ReporteDespliegueListOut | Response:
    """Reporte de despliegues con exportación CSV opcional.

    `desde`/`hasta` son fechas ISO (AAAA-MM-DD) que filtran sobre
    `despliegues.fecha`. En modo `csv` la respuesta es un adjunto
    `reporte-despliegues-<hoy>.csv` con todas las celdas sanitizadas
    (OWASP CSV Injection)."""
    solo_equipos: set[int] | None = None
    if not actor_ctx.es_admin:
        if equipo_id is not None:
            await assert_equipo_access(actor_ctx, session, equipo_id)
        else:
            solo_equipos = await equipos_visibles(actor_ctx, session)
            if not solo_equipos:
                if formato == "csv":
                    return Response(
                        content=reportes_svc.generar_csv([]).encode("utf-8"),
                        media_type="text/csv; charset=utf-8",
                        headers={
                            "Content-Disposition": (
                                f'attachment; filename="reporte-despliegues-'
                                f'{date.today().isoformat()}.csv"'
                            )
                        },
                    )
                return ReporteDespliegueListOut(despliegues=[])

    rows = await reportes_svc.consultar_reportes_despliegues(
        session,
        equipo_id=equipo_id,
        desde=desde,
        hasta=hasta,
        solo_equipos=solo_equipos,
    )

    if formato == "csv":
        contenido = reportes_svc.generar_csv(rows).encode("utf-8")
        return Response(
            content=contenido,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="reporte-despliegues-'
                    f'{date.today().isoformat()}.csv"'
                )
            },
        )
    return ReporteDespliegueListOut(despliegues=rows)
