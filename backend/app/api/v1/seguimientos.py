"""Flujo CONSUMO de campo — entidad `seguimiento` (0014, renombrada en 0016).

Apertura, listado, detalle, "Agregar todo" y cierre.

INVARIANTE 5 (Zero Transactional Logic in Python): el backend jamás calcula
stock ni muta `seguimientos`/`seguimiento_items`/`inventario_equipos`. Toda
la aritmética corre en PostgreSQL vía `fn_crear_seguimiento`,
`fn_agregar_todo_seguimiento` y `fn_cerrar_seguimiento`
(services.transaccional), bajo FOR UPDATE y con auditoría inmutable
('SEGUIMIENTO_CREADO' / 'AGREGAR_TODO' / 'SEGUIMIENTO_CERRADO' /
'ACTA_CONSUMO_GENERADA').

Aislamiento por equipo (Constitution 3.1): el actor debe ser integrante del
equipo; el administrador recibe pase transversal (security.assert_equipo_access).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.seguimiento import (
    AgregarTodoOut,
    AgregarTodoRequest,
    CerrarSeguimientoRequest,
    SeguimientoCreate,
    SeguimientoListOut,
    SeguimientoOut,
)
from app.security import (
    ActorContext,
    assert_authenticated,
    assert_equipo_access,
    get_current_actor,
)
from app.services import seguimientos as seguimientos_svc
from app.services import transaccional

router = APIRouter(prefix="/equipos", tags=["seguimientos"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

_TIPO_AGREGAR_TODO = "AGREGAR_TODO"


async def _prechequear_equipo(
    session: AsyncSession, actor_ctx: ActorContext, equipo_id: int
) -> None:
    """404 si el equipo no existe/está inactivo ANTES del chequeo de
    aislamiento, preservando la semántica 404 > 403."""
    await transaccional.prechequear_equipo(session, equipo_id=equipo_id)
    await assert_equipo_access(actor_ctx, session, equipo_id)


@router.post(
    "/{equipo_id}/seguimientos", response_model=SeguimientoOut, status_code=201
)
async def crear_seguimiento(
    equipo_id: int,
    payload: SeguimientoCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> SeguimientoOut:
    """Apertura de seguimiento (ABIERTA) delegada a fn_crear_seguimiento:
    validación de materiales, cero duplicados, UN SOLO seguimiento abierto
    por equipo y evento 'SEGUIMIENTO_CREADO' íntegros en PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        seguimiento_id = await transaccional.crear_seguimiento(
            session,
            equipo_id=equipo_id,
            observaciones=payload.observaciones,
            items=[
                {"material_id": i.material_id, "cantidad_tomada": i.cantidad_tomada}
                for i in payload.items
            ],
            usuario=actor_ctx.actor_id,
        )
        return await seguimientos_svc.obtener_seguimiento(
            session, equipo_id, seguimiento_id
        )


@router.get("/{equipo_id}/seguimientos", response_model=SeguimientoListOut)
async def listar_seguimientos(
    equipo_id: int, session: SessionDep, actor_ctx: ActorDep
) -> SeguimientoListOut:
    """Historial de seguimientos del equipo (ABIERTA y CERRADA), más
    reciente primero. Aislamiento por integrante de equipo."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    seguimientos = await seguimientos_svc.listar_seguimientos_equipo(
        session, equipo_id
    )
    return SeguimientoListOut(seguimientos=seguimientos)


@router.get(
    "/{equipo_id}/seguimientos/{seguimiento_id}", response_model=SeguimientoOut
)
async def obtener_seguimiento(
    equipo_id: int,
    seguimiento_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> SeguimientoOut:
    """Seguimiento individual con verificación de pertenencia al equipo."""
    await _prechequear_equipo(session, actor_ctx, equipo_id)
    return await seguimientos_svc.obtener_seguimiento(
        session, equipo_id, seguimiento_id
    )


@router.post(
    "/{equipo_id}/seguimientos/{seguimiento_id}/agregar-todo",
    response_model=AgregarTodoOut,
)
async def agregar_todo(
    equipo_id: int,
    seguimiento_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    payload: AgregarTodoRequest | None = None,
) -> AgregarTodoOut:
    """"Agregar todo": carga al seguimiento ABIERTA todas las líneas con
    stock del inventario del equipo, delegada a fn_agregar_todo_seguimiento
    (atómica e idempotente: una doble invocación no duplica líneas).

    Un reenvío con la misma `clave_idempotencia` devuelve 200 con el
    resultado original (REQ-P2-INV-007) sin duplicar efectos."""
    assert_authenticated(actor_ctx)
    clave = payload.clave_idempotencia if payload else None

    async def _operar() -> AgregarTodoOut:
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        # Pre-chequeo de pertenencia al equipo (404 si no corresponde).
        await seguimientos_svc.obtener_seguimiento(
            session, equipo_id, seguimiento_id
        )
        if clave is not None:
            previo = await transaccional.resultado_idempotente(
                session,
                tipo=_TIPO_AGREGAR_TODO,
                clave=clave,
                actor=actor_ctx.actor_id,
            )
            if previo is not None:
                return await _eco_agregar_todo(previo)
        agregadas = await transaccional.agregar_todo_seguimiento(
            session,
            seguimiento_id=seguimiento_id,
            equipo_id=equipo_id,
            usuario=actor_ctx.actor_id,
            clave_idempotencia=clave,
        )
        return AgregarTodoOut(
            lineas_agregadas=agregadas,
            seguimiento=await seguimientos_svc.obtener_seguimiento(
                session, equipo_id, seguimiento_id
            ),
        )

    async def _eco_agregar_todo(previo: dict) -> AgregarTodoOut:
        return AgregarTodoOut(
            lineas_agregadas=previo.get("lineas_agregadas", 0),
            seguimiento=await seguimientos_svc.obtener_seguimiento(
                session, equipo_id, seguimiento_id
            ),
        )

    try:
        async with session.begin():
            return await _operar()
    except BusinessRuleError as exc:
        if exc.code != transaccional.IDEMPOTENT_REPLAY or clave is None:
            raise
    # Carrera: otra transacción confirmó la misma clave entre el pre-chequeo
    # y la guarda del SP. La transacción fallida ya hizo rollback; leemos el
    # resultado original en una transacción nueva.
    async with session.begin():
        previo = await transaccional.resultado_idempotente(
            session,
            tipo=_TIPO_AGREGAR_TODO,
            clave=clave,
            actor=actor_ctx.actor_id,
        )
        if previo is None:  # pragma: no cover - defensivo
            raise BusinessRuleError(
                "Operación idempotente sin resultado registrado",
                status_code=409,
            )
        return await _eco_agregar_todo(previo)


@router.post(
    "/{equipo_id}/seguimientos/{seguimiento_id}/cerrar",
    response_model=SeguimientoOut,
)
async def cerrar_seguimiento(
    equipo_id: int,
    seguimiento_id: int,
    payload: CerrarSeguimientoRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> SeguimientoOut:
    """Cierre con sobrantes delegado a fn_cerrar_seguimiento: valida cada
    sobrante (0 ≤ sobrante ≤ tomada), descuenta el consumido del inventario
    del equipo bajo FOR UPDATE, audita 'SEGUIMIENTO_CERRADO' por línea y
    registra el Acta de Consumo (hito B) en la MISMA transacción SQL.
    Las líneas omitidas se cierran con sobrante 0. Clasificación 404/409
    por pre-chequeo; la autoridad transaccional permanece en PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _prechequear_equipo(session, actor_ctx, equipo_id)
        # Pre-chequeo de pertenencia al equipo (404 si no corresponde).
        await seguimientos_svc.obtener_seguimiento(
            session, equipo_id, seguimiento_id
        )
        await transaccional.cerrar_seguimiento(
            session,
            seguimiento_id=seguimiento_id,
            sobrantes=[
                {
                    "material_id": s.material_id,
                    "cantidad_sobrante": s.cantidad_sobrante,
                }
                for s in payload.sobrantes
            ],
            usuario=actor_ctx.actor_id,
            observaciones_cierre=payload.observaciones_cierre,
        )
        return await seguimientos_svc.obtener_seguimiento(
            session, equipo_id, seguimiento_id
        )
