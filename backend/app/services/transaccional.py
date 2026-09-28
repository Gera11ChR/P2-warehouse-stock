"""Mapeador transaccional — NÚCLEO DE INVARIANTE 5.

Único módulo autorizado para invocar las Stored Functions del contrato.
Prohibiciones estructurales que este módulo garantiza:
  * CERO cálculo de stock en Python (no existe aritmética `stock ± x`).
  * CERO escritura directa sobre inventario_almacen / inventario_equipos
    (solo las funciones PostgreSQL mutan esas tablas).
"""

import json

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import (
    BusinessRuleError,
    MovimientoNotFoundError,
    MovimientoStateError,
)
from app.models import CatalogoMaterial, Despliegue, Equipo, MovimientoCabecera, Seccion

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
_SQL_CARGAR_STOCK_INICIAL_FIBRA = text(
    "SELECT fn_cargar_stock_inicial_fibra(:modulo, :material_id, :cantidad, :motivo)"
)
_SQL_AJUSTAR_STOCK_FIBRA = text(
    "SELECT fn_ajustar_stock_fibra(:modulo, :material_id, :nuevo_stock, :motivo)"
)
_SQL_AJUSTAR_STOCK_GENERAL = text(
    "SELECT fn_ajustar_stock_general(:material_id, :nuevo_stock, :motivo)"
)
_SQL_CREAR_DESPLIEGUE = text(
    "SELECT fn_crear_despliegue("
    ":equipo_id, :observaciones, CAST(:items AS JSONB), :usuario)"
)
_SQL_CERRAR_DESPLIEGUE = text(
    "SELECT fn_cerrar_despliegue("
    ":despliegue_id, CAST(:sobrantes AS JSONB), :usuario, :observaciones_cierre)"
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

    # ── Mapeos preexistentes (fn_procesar/cancelar/ajustes) ──────────────
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

    # fn_ajustar_stock_general: el material no tiene fila en la sección
    # GENERAL activa (ajuste de stock desde Inventario General, REQ-API-002).
    if "No se encontró inventario del material" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    # fn_ajustar_stock_general: ambigüedad de destino (más de una sección
    # GENERAL activa con el material) — conflicto de estado del dominio.
    if "no es posible determinar un destino único" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "no puede ser negativa" in mensaje or "no puede ser negativo" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "motivo" in mensaje.lower():
        return BusinessRuleError(mensaje, status_code=422)

    # ── Mapeos del flujo DESPLIEGUE (fn_crear/fn_cerrar_despliegue) ──────
    if "no se encuentra en estado ABIERTA" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "ya posee un despliegue abierto" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "Despliegue ID" in mensaje and "no encontrado" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "no existe o se encuentra inactivo" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "no existe o está inactivo" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "duplicado" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "no pertenece a este despliegue" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "Sobrante inválido" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "Stock insuficiente en el Equipo" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "debe contener al menos un material" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "debe ser un arreglo JSON" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "Cantidad tomada inválida" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

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


async def _prechequear_equipo(
    session: AsyncSession, *, equipo_id: int
) -> None:
    """Pre-chequeo del flujo DESPLIEGUE: el equipo debe existir y estar
    activo (clasificación temprana 404 antes de invocar la función)."""
    equipo = await session.get(Equipo, equipo_id)
    if equipo is None or not equipo.is_active:
        raise BusinessRuleError(
            "Equipo no encontrado",
            coordinates=[{"equipo_id": equipo_id}],
            status_code=404,
        )


async def prechequear_equipo(
    session: AsyncSession, *, equipo_id: int
) -> None:
    """Alias público del pre-chequeo de equipo para los routers del flujo
    DESPLIEGUE (evita accesos privados entre módulos)."""
    await _prechequear_equipo(session, equipo_id=equipo_id)


async def _prechequear_despliegue(
    session: AsyncSession, *, despliegue_id: int
) -> None:
    """Clasificación temprana 404/409 del cierre de despliegue: el
    despliegue debe existir (404) y estar ABIERTA (409 en otro caso). La
    validación autoritativa permanece en fn_cerrar_despliegue."""
    despliegue = await session.get(Despliegue, despliegue_id)
    if despliegue is None:
        raise BusinessRuleError(
            "Despliegue no encontrado",
            coordinates=[{"despliegue_id": despliegue_id}],
            status_code=404,
        )
    if despliegue.estado != "ABIERTA":
        raise BusinessRuleError(
            f"El despliegue ID {despliegue_id} no se encuentra en estado "
            "ABIERTA.",
            coordinates=[
                {"despliegue_id": despliegue_id, "estado": despliegue.estado}
            ],
            status_code=409,
        )


async def _ejecutar(
    session: AsyncSession, stmt, params: dict, *, scalar: bool = False
):
    """Ejecuta una Stored Function del contrato mapeando errores SQLSTATE:

      * P0001 (RAISE EXCEPTION) → _mapear_raise_exception (400/404/409/422).
      * 23503/23505 (FK/unicidad, SEC-012) → 409 conflicto de integridad.

    Con `scalar=True` devuelve el valor escalar de la función (p.ej. el id
    generado por fn_crear_despliegue)."""
    try:
        result = await session.execute(stmt, params)
        return result.scalar_one() if scalar else None
    except DBAPIError as exc:
        sqlstate = _sqlstate(exc)
        if sqlstate == "P0001":
            raise await _mapear_raise_exception(exc) from exc
        if sqlstate in ("23503", "23505"):
            raise BusinessRuleError(
                "Conflicto de integridad referencial o de unicidad en la "
                "base de datos (SEC-012)",
                status_code=409,
            ) from exc
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


async def cargar_stock_inicial_fibra(
    session: AsyncSession,
    *,
    modulo: str,
    material_id: int,
    cantidad: int,
    motivo: str | None,
) -> None:
    """fn_cargar_stock_inicial_fibra: alta única e idempotente de inventario
    FO (PAQUETE/EN_USO). Rechaza si la fila (modulo, material_id) ya existe
    y audita 'STOCK_INICIAL_FO' en PostgreSQL."""
    await _prechequear_material(session, material_id=material_id)
    await _ejecutar(
        session,
        _SQL_CARGAR_STOCK_INICIAL_FIBRA,
        {
            "modulo": modulo,
            "material_id": material_id,
            "cantidad": cantidad,
            "motivo": motivo,
        },
    )


async def ajustar_stock_fibra(
    session: AsyncSession,
    *,
    modulo: str,
    material_id: int,
    nuevo_stock: int,
    motivo: str,
) -> None:
    """fn_ajustar_stock_fibra: ajuste administrativo FO con motivo
    obligatorio. Diferencial, FOR UPDATE y auditoría
    ('AJUSTE_INVENTARIO_FO') calculados en PostgreSQL."""
    await _prechequear_material(session, material_id=material_id)
    await _ejecutar(
        session,
        _SQL_AJUSTAR_STOCK_FIBRA,
        {
            "modulo": modulo,
            "material_id": material_id,
            "nuevo_stock": nuevo_stock,
            "motivo": motivo,
        },
    )


async def ajustar_stock_general(
    session: AsyncSession,
    *,
    material_id: int,
    nuevo_stock: int,
    motivo: str,
) -> None:
    """fn_ajustar_stock_general: edición de stock desde Inventario General
    (REQ-API-002/003). Localiza en PostgreSQL la fila del material en la
    sección GENERAL activa y delega en fn_ajustar_stock_almacen: el
    diferencial y la auditoría viven íntegros en la base de datos."""
    await _prechequear_material(session, material_id=material_id)
    await _ejecutar(
        session,
        _SQL_AJUSTAR_STOCK_GENERAL,
        {
            "material_id": material_id,
            "nuevo_stock": nuevo_stock,
            "motivo": motivo,
        },
    )


async def crear_despliegue(
    session: AsyncSession,
    *,
    equipo_id: int,
    observaciones: str | None,
    items: list[dict],
    usuario: str,
) -> int:
    """fn_crear_despliegue: apertura de despliegue (ABIERTA) 100 % en
    PostgreSQL. `items` es una lista de {"material_id", "cantidad_tomada"}
    serializada a JSON. Devuelve el id generado por la función.

    CERO aritmética de stock en Python: validación de materiales, unicidad
    de despliegue abierto por equipo y auditoría ('DESPLIEGUE_CREADO') viven
    íntegros en la stored function."""
    await _prechequear_equipo(session, equipo_id=equipo_id)
    return await _ejecutar(
        session,
        _SQL_CREAR_DESPLIEGUE,
        {
            "equipo_id": equipo_id,
            "observaciones": observaciones,
            "items": json.dumps(items),
            "usuario": usuario,
        },
        scalar=True,
    )


async def cerrar_despliegue(
    session: AsyncSession,
    *,
    despliegue_id: int,
    sobrantes: list[dict],
    usuario: str,
    observaciones_cierre: str | None,
) -> None:
    """fn_cerrar_despliegue: cierre con sobrantes 100 % en PostgreSQL.
    `sobrantes` es una lista de {"material_id", "cantidad_sobrante"}
    serializada a JSON (vacía si no hay sobrantes: las líneas omitidas se
    cierran con sobrante 0). El descuento del inventario del equipo y la
    auditoría ('DESPLIEGUE_CERRADO' por línea) ocurren dentro de la
    función bajo FOR UPDATE."""
    await _prechequear_despliegue(session, despliegue_id=despliegue_id)
    await _ejecutar(
        session,
        _SQL_CERRAR_DESPLIEGUE,
        {
            "despliegue_id": despliegue_id,
            "sobrantes": json.dumps(sobrantes),
            "usuario": usuario,
            "observaciones_cierre": observaciones_cierre,
        },
    )
