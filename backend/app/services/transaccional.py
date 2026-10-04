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
from app.models import CatalogoMaterial, Equipo, MovimientoCabecera, Seccion, Seguimiento

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
_SQL_ELIMINAR_INVENTARIO_FIBRA = text(
    "SELECT fn_eliminar_inventario_fibra(:modulo, :material_id, :motivo)"
)
_SQL_AJUSTAR_STOCK_GENERAL = text(
    "SELECT fn_ajustar_stock_general(:material_id, :nuevo_stock, :motivo)"
)
_SQL_CREAR_SEGUIMIENTO = text(
    "SELECT fn_crear_seguimiento("
    ":equipo_id, :observaciones, CAST(:items AS JSONB), :usuario)"
)
_SQL_CERRAR_SEGUIMIENTO = text(
    "SELECT fn_cerrar_seguimiento("
    ":seguimiento_id, CAST(:sobrantes AS JSONB), :usuario, :observaciones_cierre)"
)
_SQL_AGREGAR_TODO_SEGUIMIENTO = text(
    "SELECT fn_agregar_todo_seguimiento("
    ":seguimiento_id, :equipo_id, :usuario, :clave_idempotencia)"
)
_SQL_SUMAR_CANTIDAD = text(
    "SELECT fn_sumar_cantidad("
    ":destino, :modulo, :material_id, :cantidad, :usuario, :clave_idempotencia)"
)
_SQL_MOVER_MATERIAL = text(
    "SELECT fn_mover_material("
    ":origen, :origen_modulo, :destino, :destino_modulo, "
    ":material_id, :cantidad, :usuario, :clave_idempotencia)"
)
# Lectura (solo SELECT) del resultado original de una operación idempotente
# (REQ-P2-INV-007, ligada al ACTOR desde la migración 0021). La guarda y la
# escritura de `resultado` viven en el SP.
_SQL_RESULTADO_IDEMPOTENTE = text(
    "SELECT resultado FROM operaciones_idempotencia "
    "WHERE tipo_operacion = :tipo AND clave = :clave AND actor = :actor"
)

# Código de error de dominio para el reenvío de una clave de idempotencia ya
# confirmada (el router lo traduce a una respuesta 200 con el resultado
# original; jamás se duplican efectos sobre stock ni auditoría).
IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"


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

    # ── Idempotencia (REQ-P2-INV-007): reenvío de una clave ya confirmada ─
    # La clave pertenece a OTRO actor (migración 0021): conflicto sin
    # divulgación del resultado original.
    if "ya fue utilizada por otro actor" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "ya fue ejecutada" in mensaje and "idempotencia" in mensaje:
        return BusinessRuleError(
            mensaje, code=IDEMPOTENT_REPLAY, status_code=409
        )

    # Desborde numérico (SQLSTATE 22003): cantidad/stock fuera de INT4.
    if "fuera de rango" in mensaje or "out of range" in mensaje.lower():
        return BusinessRuleError(mensaje, status_code=400)

    # ── Operadores rápidos (fn_sumar_cantidad / fn_mover_material) ───────
    if "debe ser mayor que cero" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "No existe una sección GENERAL activa" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    # ── Flujo CONSUMO (fn_crear/cerrar/agregar_todo_seguimiento) ─────────
    if "no se encuentra en estado ABIERTA" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "ya posee un seguimiento abierto" in mensaje:
        return BusinessRuleError(mensaje, status_code=409)

    if "Seguimiento ID" in mensaje and "no encontrado" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    # Pertenencia seguimiento<->equipo: 404 (misma semántica que el GET).
    if "no pertenece al equipo" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "no existe o se encuentra inactivo" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "no existe o está inactivo" in mensaje:
        return BusinessRuleError(mensaje, status_code=404)

    if "duplicado" in mensaje:
        return BusinessRuleError(mensaje, status_code=400)

    if "no pertenece a este seguimiento" in mensaje:
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


async def _set_actor(session: AsyncSession, actor: str) -> None:
    """Atribución del actor vía `set_config('app.actor', ...)` dentro de la
    MISMA transacción (Constitution 6.2): los SP y el trigger tg_acta_entrega
    usan current_setting('app.actor') y el evento ACTA_ENTREGA_GENERADA
    queda atribuido a quien CONFIRMA, no al creador del borrador."""
    await session.execute(
        text("SELECT set_config('app.actor', :actor, true)"), {"actor": actor}
    )


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
    """Pre-chequeo del flujo CONSUMO: el equipo debe existir y estar
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
    CONSUMO (evita accesos privados entre módulos)."""
    await _prechequear_equipo(session, equipo_id=equipo_id)


async def _prechequear_seguimiento(
    session: AsyncSession, *, seguimiento_id: int
) -> None:
    """Clasificación temprana 404/409 del cierre de seguimiento: el
    seguimiento debe existir (404) y estar ABIERTA (409 en otro caso). La
    validación autoritativa permanece en fn_cerrar_seguimiento."""
    seguimiento = await session.get(Seguimiento, seguimiento_id)
    if seguimiento is None:
        raise BusinessRuleError(
            "Seguimiento no encontrado",
            coordinates=[{"seguimiento_id": seguimiento_id}],
            status_code=404,
        )
    if seguimiento.estado != "ABIERTA":
        raise BusinessRuleError(
            f"El seguimiento ID {seguimiento_id} no se encuentra en estado "
            "ABIERTA.",
            coordinates=[
                {"seguimiento_id": seguimiento_id, "estado": seguimiento.estado}
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
    generado por fn_crear_seguimiento)."""
    try:
        result = await session.execute(stmt, params)
        return result.scalar_one() if scalar else None
    except DBAPIError as exc:
        sqlstate = _sqlstate(exc)
        if sqlstate == "P0001":
            raise await _mapear_raise_exception(exc) from exc
        if sqlstate == "22003":
            raise BusinessRuleError(
                "La cantidad o el stock resultante excede el rango soportado",
                status_code=400,
            ) from exc
        if sqlstate in ("23503", "23505"):
            raise BusinessRuleError(
                "Conflicto de integridad referencial o de unicidad en la "
                "base de datos (SEC-012)",
                status_code=409,
            ) from exc
        raise


async def procesar_movimiento(
    session: AsyncSession, *, movimiento_id: int, usuario: str
) -> None:
    """fn_procesar_movimiento: TEAMS/DEVOL atómico (BORRADOR -> CONFIRMADO).
    El commit lo gobierna el contexto transaccional del router. Si el
    movimiento es TEAMS, tg_acta_entrega registra el Acta de Entrega en la
    MISMA transacción, atribuida a `usuario` (quien confirma)."""
    await _prechequear_estado(
        session, movimiento_id=movimiento_id, estado_requerido="BORRADOR",
        operacion="procesar",
    )
    await _set_actor(session, usuario)
    await _ejecutar(
        session,
        _SQL_PROCESS_MOVEMENT,
        {"movimiento_id": movimiento_id},
    )


async def cancelar_movimiento(
    session: AsyncSession, *, movimiento_id: int, motivo: str | None, usuario: str
) -> None:
    """fn_cancelar_movimiento: reversión forense (CONFIRMADO -> CANCELADO).
    La auditoría del evento queda atribuida a `usuario` (quien cancela)."""
    await _prechequear_estado(
        session, movimiento_id=movimiento_id, estado_requerido="CONFIRMADO",
        operacion="cancelar",
    )
    await _set_actor(session, usuario)
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
    motivo: str | None,
) -> None:
    """fn_ajustar_stock_almacen: ajuste administrativo. Ergonomía
    `justificacion_opcional` (REQ-ERG-005): motivo opcional (null/vacío
    permitido; el evento AJUSTE_INVENTARIO registra el motivo tal como
    llega)."""
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


async def cargar_stock_inicial_ruteada(
    session: AsyncSession,
    *,
    almacen_id: int,
    material_id: int,
    cantidad: int,
    motivo: str | None,
) -> None:
    """Carga inicial ruteada por tipo de sección (REQ-CARGA-002/003).

    Resuelve `seccion.tipo` y despacha a la función del contrato correcta:

      * GENERAL      → `fn_cargar_stock_inicial` (inventario_almacen), con
                       el pre-chequeo de sección activa de `cargar_stock_inicial`.
      * FO_PAQUETE   → `fn_cargar_stock_inicial_fibra(modulo='PAQUETE')`
      * FO_EN_USO    → `fn_cargar_stock_inicial_fibra(modulo='EN_USO')`

    EXCEPCIÓN DEL `is_active`: las raíces FO son manijas de ruteo
    soft-inactivas (no albergan stock propio: su inventario vive en
    `inventario_fibra`), por lo que NO se les exige `is_active` — solo se
    valida su existencia (404). Para GENERAL la exigencia de sección activa
    permanece íntegra dentro de `cargar_stock_inicial`.

    CERO aritmética de stock en Python: toda la lógica (unicidad, auditoría
    'STOCK_INICIAL'/'STOCK_INICIAL_FO') vive en PostgreSQL; esta función
    solo enruta."""
    seccion = await session.get(Seccion, almacen_id)
    if seccion is None:
        raise BusinessRuleError(
            "Sección no encontrada",
            coordinates=[{"almacen_id": almacen_id}],
            status_code=404,
        )

    if seccion.tipo == "GENERAL":
        if not seccion.is_active:
            raise BusinessRuleError(
                "Sección no encontrada",
                coordinates=[{"almacen_id": almacen_id}],
                status_code=404,
            )
        await cargar_stock_inicial(
            session,
            almacen_id=almacen_id,
            material_id=material_id,
            cantidad=cantidad,
            motivo=motivo,
        )
        return

    if seccion.tipo in ("FO_PAQUETE", "FO_EN_USO"):
        modulo = "PAQUETE" if seccion.tipo == "FO_PAQUETE" else "EN_USO"
        await cargar_stock_inicial_fibra(
            session,
            modulo=modulo,
            material_id=material_id,
            cantidad=cantidad,
            motivo=motivo,
        )
        return

    raise BusinessRuleError(
        "La sección no es un destino válido para carga inicial",
        coordinates=[{"almacen_id": almacen_id, "tipo": seccion.tipo}],
        status_code=400,
    )


async def ajustar_stock_fibra(
    session: AsyncSession,
    *,
    modulo: str,
    material_id: int,
    nuevo_stock: int,
    motivo: str | None,
) -> None:
    """fn_ajustar_stock_fibra: ajuste administrativo FO. Ergonomía
    `justificacion_opcional` (REQ-ERG-004/005): motivo opcional (null/vacío
    permitido). Diferencial, FOR UPDATE y auditoría
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


async def mapear_error_delete_fibra(
    exc: DBAPIError, *, modulo: str, material_id: int
) -> Exception:
    """Mapea errores de base de datos del flujo DELETE FO a respuestas
    controladas — NUNCA un HTTP 500 (REQ-DEL-FIX-002/007, fo_report_1.md):

      * 23503 / 23001 (violación de FK): el material posee historial de
        movimientos/transferencias que impide la eliminación → 409 con
        mensaje de dominio claro. 23503 es la violación clásica de
        INSERT/UPDATE; 23001 (restrict_violation) es la que PostgreSQL
        reporta cuando un DELETE viola una FK ON DELETE RESTRICT desde
        dentro de una stored function (fo_report_1.md).
      * 42883 (función inexistente): la migración 0015
        (`fn_eliminar_inventario_fibra`) no fue aplicada en el entorno
        → 409 con mensaje operativo.
      * Cualquier otro error de BD → 409 controlado con el mensaje de
        PostgreSQL (fallback fail-closed, jamás 500)."""
    sqlstate = _sqlstate(exc)
    coordinates = [{"modulo": modulo, "material_id": material_id}]
    if sqlstate in ("23503", "23001"):
        return BusinessRuleError(
            "No se puede eliminar porque existen movimientos o "
            "transferencias asociadas",
            code="FO_DELETE_INTEGRITY_CONFLICT",
            coordinates=coordinates,
            status_code=409,
        )
    if sqlstate == "42883":
        return BusinessRuleError(
            "La eliminación de inventario FO no está disponible en este "
            "instalación (función de base de datos no aplicada); contacte "
            "al administrador del sistema",
            code="FO_DELETE_UNAVAILABLE",
            coordinates=coordinates,
            status_code=409,
        )
    return BusinessRuleError(
        f"Error de base de datos al eliminar inventario FO: {_mensaje_pg(exc)}",
        code="FO_DELETE_DB_ERROR",
        coordinates=coordinates,
        status_code=409,
    )


async def eliminar_inventario_fibra(
    session: AsyncSession,
    *,
    modulo: str,
    material_id: int,
    motivo: str | None,
    actor: str,
) -> None:
    """fn_eliminar_inventario_fibra: eliminación física de la fila
    (modulo, material_id) de `inventario_fibra` (REQ-DEL-001/002/003/004).

    Solo se elimina la fila del módulo indicado: `catalogo_materiales`, el
    inventario del otro módulo FO y el Inventario General permanecen
    intactos (aislamiento por módulo). El evento 'ELIMINACION_FO' con
    snapshot completo jsonb (modulo, material_id, stock_eliminado, motivo,
    usuario, fecha) lo inserta la función en PostgreSQL.

    Atribución del actor vía `set_config('app.actor', ...)` dentro de la
    MISMA transacción, espejo del patrón `_set_actor` de
    services/catalogo.py (Constitution 6.2).

    REQ-DEL-004: `motivo` solo es obligatorio si la fila tiene
    stock_actual > 0 — la validación autoritativa vive en PostgreSQL y su
    RAISE se traduce a 422 vía el mapeo "motivo" de _mapear_raise_exception;
    la fila inexistente se traduce a 404 vía el mapeo "No se encuentra
    registro de inventario". El pre-chequeo de material clasifica 404
    temprano cuando el material no existe o está inactivo en el catálogo.

    REQ-DEL-FIX-002 (fo_report_1.md): todo error de base de datos fuera de
    las validaciones P0001 se traduce a un 409 controlado vía
    `mapear_error_delete_fibra` — el flujo DELETE FO jamás propaga un 500.
    Se ejecuta el statement directamente (sin `_ejecutar`) para aplicar el
    mapeo de dominio específico de este flujo; el mapeo genérico SEC-012
    de `_ejecutar` permanece intacto para el resto de los flujos."""
    await _prechequear_material(session, material_id=material_id)
    await session.execute(
        text("SELECT set_config('app.actor', :actor, true)"), {"actor": actor}
    )
    try:
        await session.execute(
            _SQL_ELIMINAR_INVENTARIO_FIBRA,
            {
                "modulo": modulo,
                "material_id": material_id,
                "motivo": motivo,
            },
        )
    except DBAPIError as exc:
        if _sqlstate(exc) == "P0001":
            # Validaciones de dominio de fn_eliminar_inventario_fibra:
            # 404 fila inexistente / 422 motivo obligatorio (REQ-DEL-002/004).
            raise await _mapear_raise_exception(exc) from exc
        raise await mapear_error_delete_fibra(
            exc, modulo=modulo, material_id=material_id
        ) from exc


async def ajustar_stock_general(
    session: AsyncSession,
    *,
    material_id: int,
    nuevo_stock: int,
    motivo: str | None,
) -> None:
    """fn_ajustar_stock_general: edición de stock desde Inventario General
    (REQ-API-002/003). Localiza en PostgreSQL la fila del material en la
    sección GENERAL activa y delega en fn_ajustar_stock_almacen: el
    diferencial y la auditoría viven íntegros en la base de datos.
    Ergonomía `justificacion_opcional` (REQ-ERG-003): motivo opcional."""
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


async def crear_seguimiento(
    session: AsyncSession,
    *,
    equipo_id: int,
    observaciones: str | None,
    items: list[dict],
    usuario: str,
) -> int:
    """fn_crear_seguimiento: apertura de seguimiento (ABIERTA) 100 % en
    PostgreSQL. `items` es una lista de {"material_id", "cantidad_tomada"}
    serializada a JSON. Devuelve el id generado por la función.

    CERO aritmética de stock en Python: validación de materiales, unicidad
    de seguimiento abierto por equipo y auditoría ('SEGUIMIENTO_CREADO')
    viven íntegros en la stored function."""
    await _prechequear_equipo(session, equipo_id=equipo_id)
    return await _ejecutar(
        session,
        _SQL_CREAR_SEGUIMIENTO,
        {
            "equipo_id": equipo_id,
            "observaciones": observaciones,
            "items": json.dumps(items),
            "usuario": usuario,
        },
        scalar=True,
    )


async def cerrar_seguimiento(
    session: AsyncSession,
    *,
    seguimiento_id: int,
    sobrantes: list[dict],
    usuario: str,
    observaciones_cierre: str | None,
) -> None:
    """fn_cerrar_seguimiento: cierre con sobrantes 100 % en PostgreSQL.
    `sobrantes` es una lista de {"material_id", "cantidad_sobrante"}
    serializada a JSON (vacía si no hay sobrantes: las líneas omitidas se
    cierran con sobrante 0). El descuento del inventario del equipo, la
    auditoría ('SEGUIMIENTO_CERRADO' por línea) y el registro del Acta de
    Consumo (snapshot jsonb, 'ACTA_CONSUMO_GENERADA') ocurren dentro de la
    función bajo FOR UPDATE, en la misma transacción."""
    await _prechequear_seguimiento(session, seguimiento_id=seguimiento_id)
    await _ejecutar(
        session,
        _SQL_CERRAR_SEGUIMIENTO,
        {
            "seguimiento_id": seguimiento_id,
            "sobrantes": json.dumps(sobrantes),
            "usuario": usuario,
            "observaciones_cierre": observaciones_cierre,
        },
    )


async def resultado_idempotente(
    session: AsyncSession, *, tipo: str, clave: str, actor: str
) -> dict | None:
    """Resultado original de una operación idempotente ya confirmada POR EL
    MISMO ACTOR (SOLO LECTURA de `operaciones_idempotencia`; None si la
    clave no existe o pertenece a otro actor). Lo escribe el propio SP en
    su transacción."""
    result = await session.execute(
        _SQL_RESULTADO_IDEMPOTENTE,
        {"tipo": tipo, "clave": clave, "actor": actor},
    )
    fila = result.first()
    return None if fila is None else fila[0]


async def agregar_todo_seguimiento(
    session: AsyncSession,
    *,
    seguimiento_id: int,
    equipo_id: int,
    usuario: str,
    clave_idempotencia: str | None,
) -> int:
    """fn_agregar_todo_seguimiento: carga atómica e idempotente de TODAS las
    líneas con stock del inventario del equipo en el seguimiento ABIERTA.
    Devuelve las líneas agregadas (calculadas por la función)."""
    return await _ejecutar(
        session,
        _SQL_AGREGAR_TODO_SEGUIMIENTO,
        {
            "seguimiento_id": seguimiento_id,
            "equipo_id": equipo_id,
            "usuario": usuario,
            "clave_idempotencia": clave_idempotencia,
        },
        scalar=True,
    )


async def sumar_cantidad(
    session: AsyncSession,
    *,
    destino: str,
    modulo: str | None,
    material_id: int,
    cantidad: int,
    usuario: str,
    clave_idempotencia: str | None,
) -> int:
    """fn_sumar_cantidad (+Cantidad): suma directa al stock actual y evento
    inmutable 'SUMA_CANTIDAD' en una única transacción PostgreSQL. Devuelve
    el nuevo stock calculado por la función. CERO aritmética en Python."""
    return await _ejecutar(
        session,
        _SQL_SUMAR_CANTIDAD,
        {
            "destino": destino,
            "modulo": modulo,
            "material_id": material_id,
            "cantidad": cantidad,
            "usuario": usuario,
            "clave_idempotencia": clave_idempotencia,
        },
        scalar=True,
    )


async def mover_material(
    session: AsyncSession,
    *,
    origen: str,
    origen_modulo: str | None,
    destino: str,
    destino_modulo: str | None,
    material_id: int,
    cantidad: int,
    usuario: str,
    clave_idempotencia: str | None,
) -> dict:
    """fn_mover_material (Mover): descuento del origen, acreditación del
    destino y evento inmutable 'MOVIMIENTO_INVENTARIO' atómicos en
    PostgreSQL. Devuelve {"stock_origen", "stock_destino"} calculados por
    la función. CERO aritmética en Python."""
    return await _ejecutar(
        session,
        _SQL_MOVER_MATERIAL,
        {
            "origen": origen,
            "origen_modulo": origen_modulo,
            "destino": destino,
            "destino_modulo": destino_modulo,
            "material_id": material_id,
            "cantidad": cantidad,
            "usuario": usuario,
            "clave_idempotencia": clave_idempotencia,
        },
        scalar=True,
    )
