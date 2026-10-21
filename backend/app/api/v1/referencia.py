"""REFERENCIA de materiales por Unidad (0030, paquete
2026-10-referencia-materiales-unidades) — router FastAPI.

Configuración visual por Unidad (REQ-REF-001..011, plan §4.2): lectura
(GET), alta masiva todo-o-nada (POST), modificación de la Cantidad Semanal
(PATCH) y eliminación (DELETE) de líneas de la Referencia. Este router
solo transporta el payload validado por los DTOs (`extra="forbid"`),
autoriza y delega la lógica en `app/services/referencia.py`.

Orden de precedencia (REQ-REF-010, C-9/Q6):
  1. Validación (Pydantic y X-Actor) → 422; identificadores de ruta fuera
     de INT4 → 400 `NUMERIC_OUT_OF_RANGE` (handler global de main.py).
  2. Escrituras: `assert_authenticated` (administrador o con alguna
     sección asignada) → 403, igual que la configuración local de la
     Unidad; las lecturas solo exigen pertenencia.
  3. La Unidad existe y está activa (lectura y escritura) → 404 antes de
     evaluar pertenencia.
  4. `assert_equipo_access` → 403 con el cuerpo de autorización vigente.

Aislamiento (REQ-REF-011): no se escriben tablas fuera de
`referencia_materiales`; las mutaciones fijan `app.actor` para que el
trigger `tg_auditar_referencia_materiales` audite en la misma transacción
(Constitución §6.2). La transacción por petición es `session.begin()`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Equipo
from app.errors import BusinessRuleError
from app.schemas.referencia import (
    ReferenciaCreate,
    ReferenciaLineaOut,
    ReferenciaListOut,
    ReferenciaUpdate,
)
from app.security import (
    ActorContext,
    assert_authenticated,
    assert_equipo_access,
    get_current_actor,
)
from app.services import referencia as referencia_svc

router = APIRouter(prefix="/equipos", tags=["referencia"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]
EquipoIdDep = Annotated[int, Path(gt=0)]
MaterialIdDep = Annotated[int, Path(gt=0)]


def _unidad_no_encontrada(equipo_id: int) -> BusinessRuleError:
    """404 canónico de Unidad inexistente o inactiva (antes que 403)."""
    return BusinessRuleError(
        "Unidad no encontrada",
        coordinates=[{"equipo_id": equipo_id}],
        status_code=404,
    )


async def _exigir_unidad_activa(
    session: AsyncSession, equipo_id: int
) -> None:
    """La Unidad existe y está activa (lectura y escritura, REQ-REF-010)."""
    equipo = await session.get(Equipo, equipo_id)
    if equipo is None or not equipo.is_active:
        raise _unidad_no_encontrada(equipo_id)


@router.get(
    "/{equipo_id}/referencia", response_model=ReferenciaListOut
)
async def listar_referencia(
    equipo_id: EquipoIdDep, session: SessionDep, actor_ctx: ActorDep
) -> ReferenciaListOut:
    """Listar la Referencia de la Unidad (REQ-REF-005): solo lectura, sin
    `assert_authenticated` (basta pertenencia) y sin eventos de auditoría."""
    await _exigir_unidad_activa(session, equipo_id)
    await assert_equipo_access(actor_ctx, session, equipo_id)
    return await referencia_svc.listar_referencia(session, equipo_id)


@router.post(
    "/{equipo_id}/referencia",
    response_model=ReferenciaListOut,
    status_code=201,
)
async def crear_referencia(
    equipo_id: EquipoIdDep,
    payload: ReferenciaCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> ReferenciaListOut:
    """Alta masiva todo-o-nada (REQ-REF-006/007, C-8): 1..50 líneas en una
    transacción; el trigger audita `REFERENCIA_LINEA_CREADA` por línea."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _exigir_unidad_activa(session, equipo_id)
        await assert_equipo_access(actor_ctx, session, equipo_id)
        await session.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor_ctx.actor_id},
        )
        return await referencia_svc.crear_referencia(
            session, equipo_id, payload
        )


@router.patch(
    "/{equipo_id}/referencia/{material_id}",
    response_model=ReferenciaLineaOut,
)
async def modificar_referencia(
    equipo_id: EquipoIdDep,
    material_id: MaterialIdDep,
    payload: ReferenciaUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> ReferenciaLineaOut:
    """Modifica SOLO la Cantidad Semanal (REQ-REF-008, C-11/Q4); con la
    misma cantidad es un no-op sin escritura ni auditoría."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _exigir_unidad_activa(session, equipo_id)
        await assert_equipo_access(actor_ctx, session, equipo_id)
        await session.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor_ctx.actor_id},
        )
        return await referencia_svc.modificar_referencia(
            session, equipo_id, material_id, payload
        )


@router.delete(
    "/{equipo_id}/referencia/{material_id}", status_code=204
)
async def eliminar_referencia(
    equipo_id: EquipoIdDep,
    material_id: MaterialIdDep,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> None:
    """Elimina físicamente la línea (REQ-REF-009, C-3/D-9); el trigger
    conserva los valores previos en el ledger de auditoría."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _exigir_unidad_activa(session, equipo_id)
        await assert_equipo_access(actor_ctx, session, equipo_id)
        await session.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor_ctx.actor_id},
        )
        await referencia_svc.eliminar_referencia(
            session, equipo_id, material_id
        )
