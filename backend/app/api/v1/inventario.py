from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.inventario import (
    SeccionOut,
    SeccionStockOut,
    SeccionTransferibleOut,
)
from app.schemas.operadores import (
    MoverMaterialOut,
    MoverMaterialRequest,
    SumarCantidadOut,
    SumarCantidadRequest,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import inventario, transaccional

router = APIRouter(prefix="/inventario", tags=["inventario"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]

_TIPO_SUMA_CANTIDAD = "SUMA_CANTIDAD"
_TIPO_MOVIMIENTO_INVENTARIO = "MOVIMIENTO_INVENTARIO"


async def _ejecutar_idempotente(
    session: AsyncSession,
    *,
    tipo: str,
    clave: str | None,
    operacion,
) -> tuple[dict, bool]:
    """Ejecuta `operacion` (que invoca UN Stored Procedure) en una única
    transacción y devuelve `(resultado, reenvio_idempotente)`.

    REQ-P2-INV-007: si la clave ya fue confirmada, se devuelve el resultado
    ORIGINAL sin duplicar efectos sobre stock ni auditoría. Dos caminos:
      * pre-chequeo de lectura (reenvío secuencial), y
      * carrera: el SP rechaza la clave repetida (IDEMPOTENT_REPLAY); la
        transacción fallida hace rollback y el resultado original se lee
        en una transacción nueva.
    La guarda y el almacén de `resultado` viven en PostgreSQL; aquí solo se
    lee. CERO aritmética de stock en Python."""

    async def _intento() -> tuple[dict, bool]:
        if clave is not None:
            previo = await transaccional.resultado_idempotente(
                session, tipo=tipo, clave=clave
            )
            if previo is not None:
                return previo, True
        return await operacion(), False

    try:
        async with session.begin():
            return await _intento()
    except BusinessRuleError as exc:
        if exc.code != transaccional.IDEMPOTENT_REPLAY or clave is None:
            raise
    async with session.begin():
        previo = await transaccional.resultado_idempotente(
            session, tipo=tipo, clave=clave
        )
    if previo is None:  # pragma: no cover - defensivo
        raise BusinessRuleError(
            "Operación idempotente sin resultado registrado", status_code=409
        )
    return previo, True


@router.get("/secciones", response_model=list[SeccionOut])
async def list_secciones(
    session: SessionDep, _actor: ActorDep
) -> list[SeccionOut]:
    return await inventario.listar_secciones(session)


@router.get(
    "/secciones/transferibles", response_model=list[SeccionTransferibleOut]
)
async def secciones_transferibles(
    session: SessionDep, _actor: ActorDep
) -> list[SeccionTransferibleOut]:
    """Secciones válidas como origen/destino de movimientos TEAMS/DEVOL:
    GENERAL activas + manejadores de ruteo FO (transferibles aunque
    inactivos). No altera el contrato de GET /secciones."""
    return [
        SeccionTransferibleOut(**s)
        for s in await inventario.listar_secciones_transferibles(session)
    ]


@router.get("/secciones/{almacen_id}", response_model=list[SeccionStockOut])
async def stock_seccion(
    almacen_id: int, session: SessionDep, _actor: ActorDep
) -> list[SeccionStockOut]:
    seccion = await inventario.obtener_seccion(session, almacen_id)
    if seccion is None:
        raise BusinessRuleError(
            "Sección no encontrada",
            coordinates=[{"almacen_id": almacen_id}],
            status_code=404,
        )
    return await inventario.stock_seccion(session, almacen_id)


@router.post("/sumar-cantidad", response_model=SumarCantidadOut)
async def sumar_cantidad(
    payload: SumarCantidadRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> SumarCantidadOut:
    """`+Cantidad`: suma directa al stock actual del material (Inventario
    General o módulos FO), SIN pasar por el flujo de transferencia.

    Delegado 100 % a `fn_sumar_cantidad`: la suma, la validación (cantidad
    > 0, material activo, registro existente) y el evento inmutable
    'SUMA_CANTIDAD' (distinto de AJUSTE_*) ocurren en PostgreSQL en una
    única transacción. Idempotente por `clave_idempotencia`."""
    assert_authenticated(actor_ctx)

    async def _operar() -> dict:
        nuevo = await transaccional.sumar_cantidad(
            session,
            destino=payload.destino,
            modulo=payload.modulo,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            usuario=actor_ctx.actor_id,
            clave_idempotencia=payload.clave_idempotencia,
        )
        return {"stock_nuevo": nuevo}

    resultado, reenvio = await _ejecutar_idempotente(
        session,
        tipo=_TIPO_SUMA_CANTIDAD,
        clave=payload.clave_idempotencia,
        operacion=_operar,
    )
    return SumarCantidadOut(
        destino=payload.destino,
        modulo=payload.modulo,
        material_id=payload.material_id,
        stock_nuevo=resultado["stock_nuevo"],
        reenvio_idempotente=reenvio,
    )


@router.post("/mover", response_model=MoverMaterialOut)
async def mover_material(
    payload: MoverMaterialRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MoverMaterialOut:
    """`Mover`: transferencia directa entre Inventario General y módulos FO
    (cantidad parcial), sin la lógica de TEAMS/DEVOL.

    Delegado 100 % a `fn_mover_material`: descuento del origen,
    acreditación del destino (fila creada solo con stock > 0) y evento
    inmutable 'MOVIMIENTO_INVENTARIO' atómicos en PostgreSQL. Rechaza
    destino = origen, cantidad <= 0 y cantidad > stock del origen sin
    modificar ningún inventario. Idempotente por `clave_idempotencia`."""
    assert_authenticated(actor_ctx)

    async def _operar() -> dict:
        return await transaccional.mover_material(
            session,
            origen=payload.origen,
            origen_modulo=payload.origen_modulo,
            destino=payload.destino,
            destino_modulo=payload.destino_modulo,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            usuario=actor_ctx.actor_id,
            clave_idempotencia=payload.clave_idempotencia,
        )

    resultado, reenvio = await _ejecutar_idempotente(
        session,
        tipo=_TIPO_MOVIMIENTO_INVENTARIO,
        clave=payload.clave_idempotencia,
        operacion=_operar,
    )
    return MoverMaterialOut(
        material_id=payload.material_id,
        origen=payload.origen,
        origen_modulo=payload.origen_modulo,
        destino=payload.destino,
        destino_modulo=payload.destino_modulo,
        stock_origen=resultado["stock_origen"],
        stock_destino=resultado["stock_destino"],
        reenvio_idempotente=reenvio,
    )
