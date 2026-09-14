"""Mapeador transaccional — NÚCLEO DE INVARIANTE 5.

Único módulo autorizado para invocar las Stored Functions del contrato.
Prohibiciones estructurales que este módulo garantiza:
  * CERO cálculo de stock en Python (no existe aritmética `stock ± x`).
  * CERO escritura directa sobre inventario_almacen / inventario_equipos
    (solo las funciones PostgreSQL mutan esas tablas).
"""

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import (
    BusinessRuleError,
    MovimientoNotFoundError,
    MovimientoStateError,
)
from app.models import CatalogoMaterial, MovimientoCabecera, Seccion

_SQL_PROCESS_MOVEMENT = text("SELECT fn_procesar_movimiento(:movimiento_id)")
_SQL_CANCEL_MOVEMENT = text(
    "SELECT fn_cancelar_movimiento(:movimiento_id, :motivo)"
)
_SQL_CARGAR_STOCK_INICIAL = text(
    "SELECT fn_cargar_stock_inicial(:almacen_id, :material_id, :cantidad, :motivo)"
)
_SQL_AJUSTAR_STOCK_ALMACEN = text(
    "SELECT fn_ajustar_stock_almacen(:almacen_id, :material_id, :nuevo_stock, :motivo)"
)


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None)


def _mensaje_pg(exc: DBAPIError) -> str:
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    primary = getattr(diag, "message_primary", None)
    if primary:
        return primary
    return str(orig) if orig is not None else str(exc)


async def _mapear_raise_exception(exc: DBAPIError) -> Exception:
    """Convierte RAISE EXCEPTION (SQLSTATE P0001) en errores de dominio HTTP:
    400 stock insuficiente/cantidad negativa, 404 entidad inexistente,
    409 conflicto de estado, 422 regla de negocio genérica.

    La clasificación 404 vs 409 por estado se resuelve en el pre-chequeo de
    cada operación (lectura de cabecera antes de invocar la función); la
    validación autoritativa permanece en PostgreSQL."""
    mensaje = _mensaje_pg(exc)

    if "Stock insuficiente" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "no cuenta con stock suficiente" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "no existe o no se encuentra en estado" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "ya posee un registro de inventario activo" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "No se encuentra registro de inventario" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "no puede ser negativa" in mensaje or "no puede ser negativo" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "motivo" in mensaje.lower():
        return BusinessRuleError(mensaje, status_code=422)

    return BusinessRuleError(mensaje, status_code=422)


async def _prechequear_estado(
    session: AsyncSession, *, movimiento_id: int, estado_requerido: str, operacion: str
) -> None:
    """Clasificación temprana 404/409. No valida stock: la función SQL sigue
    siendo la única autoridad transaccional."""
    cabecera = await session.get(MovimientoCabecera, movimiento_id)
    if cabecera is None:
        raise MovimientoNotFoundError(movimiento_id)
    if cabecera.estado != estado_requerido:
        raise MovimientoStateError(
            movimiento_id, estado=cabecera.estado, operacion=operacion
        )


async def _prechequear_seccion(
    session: AsyncSession, *, almacen_id: int
) -> None:
    """AJU-04: evita violaciones de FK sin mapear (SQLSTATE 23503) cuando el
    almacén no existe; la clasificación correcta es 404."""
    seccion = await session.get(Seccion, almacen_id)
    if seccion is None or not seccion.is_active:
        raise BusinessRuleError(
            "Sección no encontrada",
            coordinates=[{"almacen_id": almacen_id}],
            status_code=404,
        )


async def _prechequear_material(
    session: AsyncSession, *, material_id: int
) -> None:
    """Ídem AJU-04 para material_id: evita FK 23503 y clasifica 404."""
    material = await session.get(CatalogoMaterial, material_id)
    if material is None or not material.is_active:
        raise BusinessRuleError(
            "Material no encontrado",
            coordinates=[{"material_id": material_id}],
            status_code=404,
        )


async def _ejecutar(
    session: AsyncSession, stmt, params: dict
) -> None:
    try:
        await session.execute(stmt, params)
    except DBAPIError as exc:
        if _sqlstate(exc) == "P0001":
            raise await _mapear_raise_exception(exc) from exc
        raise


async def procesar_movimiento(
    session: AsyncSession, *, movimiento_id: int
) -> None:
    """fn_procesar_movimiento: TEAMS/DEVOL atómico (BORRADOR -> CONFIRMADO).
    El commit lo gobierna el contexto transaccional del router."""
    await _prechequear_estado(
        session, movimiento_id=movimiento_id, estado_requerido="BORRADOR",
        operacion="procesar",
    )
    await _ejecutar(
        session,
        _SQL_PROCESS_MOVEMENT,
        {"movimiento_id": movimiento_id},
    )


async def cancelar_movimiento(
    session: AsyncSession, *, movimiento_id: int, motivo: str | None
) -> None:
    """fn_cancelar_movimiento: reversión forense (CONFIRMADO -> CANCELADO)."""
    await _prechequear_estado(
        session, movimiento_id=movimiento_id, estado_requerido="CONFIRMADO",
        operacion="cancelar",
    )
    await _ejecutar(
        session,
        _SQL_CANCEL_MOVEMENT,
        {"movimiento_id": movimiento_id, "motivo": motivo},
    )


async def cargar_stock_inicial(
    session: AsyncSession,
    *,
    almacen_id: int,
    material_id: int,
    cantidad: int,
    motivo: str | None,
) -> None:
    """fn_cargar_stock_inicial: alta única e idempotente de inventario."""
    await _prechequear_seccion(session, almacen_id=almacen_id)
    await _prechequear_material(session, material_id=material_id)
    await _ejecutar(
        session,
        _SQL_CARGAR_STOCK_INICIAL,
        {
            "almacen_id": almacen_id,
            "material_id": material_id,
            "cantidad": cantidad,
            "motivo": motivo,
        },
    )


async def ajustar_stock_almacen(
    session: AsyncSession,
    *,
    almacen_id: int,
    material_id: int,
    nuevo_stock: int,
    motivo: str,
) -> None:
    """fn_ajustar_stock_almacen: ajuste administrativo con motivo obligatorio."""
    await _prechequear_seccion(session, almacen_id=almacen_id)
    await _prechequear_material(session, material_id=material_id)
    await _ejecutar(
        session,
        _SQL_AJUSTAR_STOCK_ALMACEN,
        {
            "almacen_id": almacen_id,
            "material_id": material_id,
            "nuevo_stock": nuevo_stock,
            "motivo": motivo,
        },
    )
