"""Pruebas SQL secuenciales de la Fase 1 (T1.7) — cambio
2026-10-01-reportes-consumo-management.

Cobertura (100 % SQL, psycopg sobre p2_test, PostgreSQL 18.6):
  * T1.2 — renombre físico completo DESPLIEGUE -> seguimiento/CONSUMO
    (catálogo sin objetos legacy; funciones con nomenclatura nueva).
  * Inmutabilidad de `auditoria_eventos` (cero triggers/reglas de
    escritura; ledger append-only por esquema).
  * fn_sumar_cantidad: feliz GENERAL/FO, validaciones (0, negativo,
    destino inválido, material inactivo, sin fila), idempotencia por
    clave y atomicidad con rollback inducido.
  * fn_mover_material: feliz en las 3 direcciones, semántica dispersa
    (fila origen conservada en 0; fila destino creada solo con stock > 0),
    casos borde (destino=origen, cantidad 0/negativa, stock insuficiente,
    origen sin fila), idempotencia.
  * fn_agregar_todo_seguimiento: carga completa, idempotencia (doble
    invocación no duplica), validaciones (404/409, pertenencia).
  * fn_cerrar_seguimiento extendido: Acta de Consumo con snapshot jsonb y
    consumido registrado y descontado directamente en SQL; rollback total ante
    consumo inválido o línea faltante.
  * Acta de Entrega: trigger tg_acta_entrega en la MISMA transacción de la
    confirmación TEAMS (CONFIRMADO, estado real del esquema), sin acta
    para DEVOL, sin duplicado ante UPDATE no-op, snapshot conservado tras
    cancelación.
  * Concurrencia FOR UPDATE: sumas concurrentes, movimientos opuestos y
    suma+mover serializan sin deadlocks y con resultado determinista.

Las pruebas corren SECUENCIALMENTE (pytest sin xdist); el paralelismo
interno de los tests de concurrencia es el requerido por la tarea.
"""

import json
import os
import threading

import psycopg
import pytest
from psycopg.errors import RaiseException

# URL nativa psycopg a p2_test (misma BD que la suite de la app; el
# bootstrap de sql_tests/conftest.py aplica `alembic upgrade head`).
PSYCOPG_TEST_URL = os.environ["P2_TEST_DATABASE_URL"].replace(
    "postgresql+psycopg://", "postgresql://"
)

P0001 = "P0001"


# ================================================================
# Helpers
# ================================================================


def _uno(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def _ejecuta(conn, query, params=()):
    """Sentencia sin filas de resultado (INSERT/UPDATE sin RETURNING)."""
    with conn.cursor() as cur:
        cur.execute(query, params)


def _valor(conn, query, params=()):
    return _uno(conn, query, params)[0]


def _todos(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def _falla(conn, query, params=()):
    """Ejecuta y espera un RAISE EXCEPTION (SQLSTATE P0001)."""
    with pytest.raises(RaiseException) as excinfo:
        with conn.cursor() as cur:
            cur.execute(query, params)
    assert excinfo.value.sqlstate == P0001
    return str(excinfo.value)


def crear_categoria(conn, nombre="Categoria QA"):
    return _valor(
        conn,
        "INSERT INTO categorias (nombre) VALUES (%s) RETURNING id",
        (nombre,),
    )


def crear_material(conn, descripcion="Material QA", u_m="PZ", categoria_id=None):
    return _valor(
        conn,
        "INSERT INTO catalogo_materiales (descripcion, u_m, categoria_id) "
        "VALUES (%s, %s, %s) RETURNING id_lista",
        (descripcion, u_m, categoria_id),
    )


def crear_equipo(conn, nombre="Equipo QA"):
    return _valor(
        conn, "INSERT INTO equipos (nombre) VALUES (%s) RETURNING equipo_id", (nombre,)
    )


def carga_inicial_general(conn, material_id, cantidad):
    _uno(
        conn,
        "SELECT fn_cargar_stock_inicial(1, %s, %s, %s)",
        (material_id, cantidad, "carga QA"),
    )


def carga_inicial_fibra(conn, modulo, material_id, cantidad):
    _uno(
        conn,
        "SELECT fn_cargar_stock_inicial_fibra(%s, %s, %s, %s)",
        (modulo, material_id, cantidad, "carga FO QA"),
    )


def stock_general(conn, material_id):
    return _valor(
        conn,
        "SELECT stock_actual FROM inventario_almacen "
        "WHERE almacen_id = 1 AND material_id = %s",
        (material_id,),
    )


def stock_fibra(conn, modulo, material_id):
    fila = _uno(
        conn,
        "SELECT stock_actual FROM inventario_fibra "
        "WHERE modulo = %s AND material_id = %s",
        (modulo, material_id),
    )
    return None if fila is None else fila[0]


def stock_equipo(conn, equipo_id, material_id):
    fila = _uno(
        conn,
        "SELECT stock_actual FROM inventario_equipos "
        "WHERE equipo_id = %s AND material_id = %s",
        (equipo_id, material_id),
    )
    return None if fila is None else fila[0]


def eventos(conn, tipo_accion):
    return _valor(
        conn,
        "SELECT count(*) FROM auditoria_eventos WHERE tipo_accion = %s",
        (tipo_accion,),
    )


def stockear_equipo_teams(conn, material_id, cantidad, nombre="Equipo QA"):
    """Equipo con stock real vía TEAMS procesado (dispara el Acta de
    Entrega por diseño, T1.6)."""
    carga_inicial_general(conn, material_id, cantidad)
    equipo_id = crear_equipo(conn, nombre)
    movimiento_id = _valor(
        conn,
        "INSERT INTO movimientos_cabecera "
        "(tipo_movimiento, usuario, origen_almacen_id, destino_equipo_id) "
        "VALUES ('TEAMS', 'qa', 1, %s) RETURNING id",
        (equipo_id,),
    )
    _ejecuta(
        conn,
        "INSERT INTO movimientos_detalle (movimiento_id, material_id, cantidad) "
        "VALUES (%s, %s, %s)",
        (movimiento_id, material_id, cantidad),
    )
    _uno(conn, "SELECT fn_procesar_movimiento(%s)", (movimiento_id,))
    return equipo_id, movimiento_id


def crear_seguimiento(conn, equipo_id, items, observaciones="obs QA"):
    return _valor(
        conn,
        "SELECT fn_crear_seguimiento(%s, %s, %s::jsonb, %s)",
        (equipo_id, observaciones, json.dumps(items), "qa"),
    )


def _hilo(sql, params, resultado, idx, barrera):
    def run():
        try:
            barrera.wait(timeout=30)
            with psycopg.connect(PSYCOPG_TEST_URL, autocommit=True) as c:
                with c.cursor() as cur:
                    cur.execute(sql, params)
            resultado[idx] = "ok"
        except Exception as exc:  # pragma: no cover - solo diagnóstico
            resultado[idx] = f"ERROR: {exc}"

    return run


# ================================================================
# T1.2 — Renombre físico y ledger inmutable
# ================================================================


def test_renombre_fisico_sin_objetos_legacy(conn):
    """REQ-P2-CON-001: cero objetos de catálogo con nomenclatura DESPLIEGUE
    (tablas, secuencias, índices, constraints); nuevos objetos presentes."""
    for nuevo in (
        "seguimientos",
        "seguimiento_items",
        "seguimientos_id_seq",
        "seguimiento_items_id_seq",
        "actas_reportes",
        "operaciones_idempotencia",
        "uq_seguimientos_equipo_abierta",
    ):
        assert _valor(conn, "SELECT to_regclass('public.' || %s)", (nuevo,)) is not None

    for legacy in ("despliegues", "despliegue_items", "despliegues_id_seq"):
        assert _valor(conn, "SELECT to_regclass('public.' || %s)", (legacy,)) is None

    assert _valor(
        conn,
        "SELECT count(*) FROM information_schema.table_constraints "
        "WHERE table_schema = 'public' AND constraint_name ILIKE '%%despliegue%%'",
    ) == 0
    assert _valor(
        conn,
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname ILIKE '%%despliegue%%'",
    ) == 0

    # Funciones: nuevas presentes, legacy ausentes.
    assert _valor(conn, "SELECT to_regproc('fn_crear_seguimiento')") is not None
    assert _valor(conn, "SELECT to_regproc('fn_cerrar_seguimiento')") is not None
    assert _valor(conn, "SELECT to_regproc('fn_crear_despliegue')") is None
    assert _valor(conn, "SELECT to_regproc('fn_cerrar_despliegue')") is None

    # Nomenclatura nueva dentro de los cuerpos (sin alias legacy).
    prosrc = _valor(conn, "SELECT prosrc FROM pg_proc WHERE proname = 'fn_crear_seguimiento'")
    assert "SEGUIMIENTO_CREADO" in prosrc
    assert "DESPLIEGUE_CREADO" not in prosrc


def test_auditoria_eventos_sin_vias_de_escritura(conn):
    """Ledger inmutable (endurecido en 0022): el ÚNICO trigger sobre
    auditoria_eventos es el guard que bloquea UPDATE/DELETE; el INSERT
    sigue funcionando y las filas persisten tal cual."""
    guard = _todos(
        conn,
        "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = 'auditoria_eventos' AND NOT t.tgisinternal",
    )
    assert guard == [("tg_ledger_auditoria_inmutable",)]
    assert _valor(
        conn,
        "SELECT count(*) FROM pg_rules "
        "WHERE schemaname = 'public' AND tablename = 'auditoria_eventos'",
    ) == 0
    _ejecuta(
        conn,
        "INSERT INTO auditoria_eventos (usuario, tipo_accion, resultado, detalles) "
        "VALUES ('legacy', 'DESPLIEGUE_CREADO', 'EXITO', '{}'::jsonb)",
    )
    fila = _uno(
        conn,
        "SELECT tipo_accion, resultado FROM auditoria_eventos WHERE usuario = 'legacy'",
    )
    assert fila == ("DESPLIEGUE_CREADO", "EXITO")

    # El guard bloquea UPDATE y DELETE de filas del ledger.
    assert "UPDATE y DELETE están prohibidos" in _falla(
        conn,
        "UPDATE auditoria_eventos SET resultado = 'X' WHERE usuario = 'legacy'",
    )
    assert "UPDATE y DELETE están prohibidos" in _falla(
        conn,
        "DELETE FROM auditoria_eventos WHERE usuario = 'legacy'",
    )


def test_actas_reportes_inmutables(conn):
    """La tabla de actas (nueva en este cambio) también queda protegida:
    solo el guard, cero reglas, INSERT permitido y UPDATE/DELETE bloqueados."""
    guard = _todos(
        conn,
        "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = 'actas_reportes' AND NOT t.tgisinternal",
    )
    assert guard == [("tg_ledger_actas_inmutable",)]
    assert _valor(
        conn,
        "SELECT count(*) FROM pg_rules "
        "WHERE schemaname = 'public' AND tablename = 'actas_reportes'",
    ) == 0
    # Acta REAL registrada por el trigger tg_acta_entrega al confirmar un
    # TEAMS (así se respetan las FKs y el CHECK ck_actas_extremos).
    material = crear_material(conn, descripcion="Acta inmutabilidad")
    stockear_equipo_teams(conn, material, 10)
    acta_id = _valor(conn, "SELECT id FROM actas_reportes WHERE tipo = 'ENTREGA'")
    assert "UPDATE y DELETE están prohibidos" in _falla(
        conn,
        "UPDATE actas_reportes SET tipo = 'CONSUMO' WHERE id = %s",
        (acta_id,),
    )
    assert "UPDATE y DELETE están prohibidos" in _falla(
        conn,
        "DELETE FROM actas_reportes WHERE id = %s",
        (acta_id,),
    )


# ================================================================
# T1.3 — fn_sumar_cantidad
# ================================================================


def test_sumar_cantidad_general(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    nuevo = _valor(
        conn,
        "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', NULL)",
        (material_id,),
    )
    assert nuevo == 15
    assert stock_general(conn, material_id) == 15
    assert eventos(conn, "SUMA_CANTIDAD") == 1
    detalles = _valor(
        conn,
        "SELECT detalles FROM auditoria_eventos WHERE tipo_accion = 'SUMA_CANTIDAD'",
    )
    assert detalles["stock_anterior"] == 10
    assert detalles["stock_nuevo"] == 15
    assert detalles["diferencial"] == 5


def test_sumar_cantidad_fibra(conn):
    material_id = crear_material(conn)
    carga_inicial_fibra(conn, "EN_USO", material_id, 10)

    nuevo = _valor(
        conn,
        "SELECT fn_sumar_cantidad('FO', 'EN_USO', %s, 7, 'qa', NULL)",
        (material_id,),
    )
    assert nuevo == 17
    assert stock_fibra(conn, "EN_USO", material_id) == 17
    assert eventos(conn, "SUMA_CANTIDAD") == 1


def test_sumar_cantidad_validaciones(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    for cantidad in (0, -3):
        msg = _falla(
            conn,
            "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, %s, 'qa', NULL)",
            (material_id, cantidad),
        )
        assert "mayor que cero" in msg

    msg = _falla(
        conn,
        "SELECT fn_sumar_cantidad('ALMACEN', NULL, %s, 5, 'qa', NULL)",
        (material_id,),
    )
    assert "GENERAL o FO" in msg

    _ejecuta(conn, "UPDATE catalogo_materiales SET is_active = FALSE WHERE id_lista = %s", (material_id,))
    msg = _falla(
        conn,
        "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', NULL)",
        (material_id,),
    )
    assert "inactivo" in msg

    otro = crear_material(conn, descripcion="Sin inventario")
    msg = _falla(
        conn,
        "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', NULL)",
        (otro,),
    )
    assert "No se encuentra registro de inventario" in msg

    # Cero efectos colaterales: stock intacto y ledger limpio.
    assert stock_general(conn, material_id) == 10
    assert eventos(conn, "SUMA_CANTIDAD") == 0


def test_sumar_cantidad_idempotencia(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    _uno(
        conn,
        "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', 'clave-suma-1')",
        (material_id,),
    )
    msg = _falla(
        conn,
        "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', 'clave-suma-1')",
        (material_id,),
    )
    assert "ya fue ejecutada" in msg

    assert stock_general(conn, material_id) == 15  # sumada UNA sola vez
    assert eventos(conn, "SUMA_CANTIDAD") == 1
    assert _valor(
        conn,
        "SELECT count(*) FROM operaciones_idempotencia "
        "WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = 'clave-suma-1'",
    ) == 1
    resultado = _valor(
        conn,
        "SELECT resultado FROM operaciones_idempotencia "
        "WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = 'clave-suma-1'",
    )
    assert resultado["stock_nuevo"] == 15


def test_sumar_cantidad_atomicidad_rollback(conn):
    """Atomicidad: dentro de UNA transacción, un fallo posterior revierte
    la suma ya aplicada, la auditoría y la clave de idempotencia."""
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    with psycopg.connect(PSYCOPG_TEST_URL, autocommit=False) as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', 'clave-rollback')",
                (material_id,),
            )
            with pytest.raises(RaiseException):
                cur.execute(
                    "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', "
                    "%s, 999, 'qa', NULL)",
                    (material_id,),
                )
        c.rollback()

    assert stock_general(conn, material_id) == 10
    assert eventos(conn, "SUMA_CANTIDAD") == 0
    assert _valor(
        conn,
        "SELECT count(*) FROM operaciones_idempotencia WHERE clave = 'clave-rollback'",
    ) == 0


# ================================================================
# T1.4 — fn_mover_material
# ================================================================


def test_mover_general_a_fo(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    resultado = _valor(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 4, 'qa', NULL)",
        (material_id,),
    )
    assert resultado["stock_origen"] == 6
    assert resultado["stock_destino"] == 4
    assert stock_general(conn, material_id) == 6
    assert stock_fibra(conn, "PAQUETE", material_id) == 4  # fila creada con stock > 0
    assert eventos(conn, "MOVIMIENTO_INVENTARIO") == 1
    detalles = _valor(
        conn,
        "SELECT detalles FROM auditoria_eventos WHERE tipo_accion = 'MOVIMIENTO_INVENTARIO'",
    )
    assert detalles["origen"]["tipo"] == "GENERAL"
    assert detalles["destino"]["tipo"] == "FO"
    assert detalles["stock_origen_anterior"] == 10
    assert detalles["stock_origen_despues"] == 6
    assert detalles["stock_destino_anterior"] == 0
    assert detalles["stock_destino_despues"] == 4


def test_mover_fo_a_general(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 6)
    carga_inicial_fibra(conn, "PAQUETE", material_id, 4)

    _uno(
        conn,
        "SELECT fn_mover_material('FO', 'PAQUETE', 'GENERAL', NULL, %s, 2, 'qa', NULL)",
        (material_id,),
    )
    assert stock_general(conn, material_id) == 8
    assert stock_fibra(conn, "PAQUETE", material_id) == 2


def test_mover_entre_modulos_fo(conn):
    material_id = crear_material(conn)
    carga_inicial_fibra(conn, "PAQUETE", material_id, 10)

    _uno(
        conn,
        "SELECT fn_mover_material('FO', 'PAQUETE', 'FO', 'EN_USO', %s, 4, 'qa', NULL)",
        (material_id,),
    )
    assert stock_fibra(conn, "PAQUETE", material_id) == 6
    assert stock_fibra(conn, "EN_USO", material_id) == 4


def test_mover_semantica_dispersa_fila_origen_conservada(conn):
    """Decisión documentada (T1.4): la fila origen que llega a 0 SE
    CONSERVA (no se elimina); la de destino se crea solo con stock > 0."""
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    _uno(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'EN_USO', %s, 10, 'qa', NULL)",
        (material_id,),
    )
    fila_origen = _uno(
        conn,
        "SELECT stock_actual FROM inventario_almacen "
        "WHERE almacen_id = 1 AND material_id = %s",
        (material_id,),
    )
    assert fila_origen == (0,)  # fila CONSERVADA con stock 0
    assert stock_fibra(conn, "EN_USO", material_id) == 10
    # Un nuevo +Cantidad sobre la fila conservada funciona sin carga inicial.
    _uno(conn, "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 3, 'qa', NULL)", (material_id,))
    assert stock_general(conn, material_id) == 3


def test_mover_casos_borde(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)
    carga_inicial_fibra(conn, "PAQUETE", material_id, 10)

    # destino = origen
    msg = _falla(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'GENERAL', NULL, %s, 2, 'qa', NULL)",
        (material_id,),
    )
    assert "no puede ser igual al origen" in msg
    msg = _falla(
        conn,
        "SELECT fn_mover_material('FO', 'PAQUETE', 'FO', 'PAQUETE', %s, 2, 'qa', NULL)",
        (material_id,),
    )
    assert "no puede ser igual al origen" in msg

    # cantidad <= 0
    for cantidad in (0, -5):
        msg = _falla(
            conn,
            "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, %s, 'qa', NULL)",
            (material_id, cantidad),
        )
        assert "mayor que cero" in msg

    # cantidad > stock origen
    msg = _falla(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 11, 'qa', NULL)",
        (material_id,),
    )
    assert "Stock insuficiente" in msg

    # origen sin fila de inventario
    otro = crear_material(conn, descripcion="Sin fila origen")
    msg = _falla(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 1, 'qa', NULL)",
        (otro,),
    )
    assert "No se encuentra registro de inventario" in msg

    # Ningún extremo modificado; ledger limpio (REQ-P2-INV-004).
    assert stock_general(conn, material_id) == 10
    assert stock_fibra(conn, "PAQUETE", material_id) == 10
    assert eventos(conn, "MOVIMIENTO_INVENTARIO") == 0


def test_mover_idempotencia(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    _uno(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 3, 'qa', 'clave-mover-1')",
        (material_id,),
    )
    msg = _falla(
        conn,
        "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 3, 'qa', 'clave-mover-1')",
        (material_id,),
    )
    assert "ya fue ejecutada" in msg

    assert stock_general(conn, material_id) == 7  # descontado UNA sola vez
    assert stock_fibra(conn, "PAQUETE", material_id) == 3
    assert eventos(conn, "MOVIMIENTO_INVENTARIO") == 1
    assert _valor(
        conn,
        "SELECT count(*) FROM operaciones_idempotencia "
        "WHERE tipo_operacion = 'MOVIMIENTO_INVENTARIO' AND clave = 'clave-mover-1'",
    ) == 1


# ================================================================
# T1.5 — fn_agregar_todo_seguimiento
# ================================================================


def test_agregar_todo_carga_total_idempotente(conn):
    material_a = crear_material(conn, descripcion="Material A")
    material_b = crear_material(conn, descripcion="Material B")
    equipo_id, _ = stockear_equipo_teams(conn, material_a, 50)
    carga_inicial_general(conn, material_b, 30)
    b_id = _valor(
        conn,
        "INSERT INTO movimientos_cabecera "
        "(tipo_movimiento, usuario, origen_almacen_id, destino_equipo_id) "
        "VALUES ('TEAMS', 'qa', 1, %s) RETURNING id",
        (equipo_id,),
    )
    _ejecuta(
        conn,
        "INSERT INTO movimientos_detalle (movimiento_id, material_id, cantidad) "
        "VALUES (%s, %s, %s)",
        (b_id, material_b, 30),
    )
    _uno(conn, "SELECT fn_procesar_movimiento(%s)", (b_id,))

    # El seguimiento ya trae el material A; "Agregar todo" debe añadir solo B.
    seguimiento_id = crear_seguimiento(
        conn, equipo_id, [{"material_id": material_a, "cantidad_tomada": 20}]
    )

    agregadas = _valor(
        conn,
        "SELECT fn_agregar_todo_seguimiento(%s, %s, 'qa', NULL)",
        (seguimiento_id, equipo_id),
    )
    assert agregadas == 1
    filas = _todos(
        conn,
        "SELECT material_id, cantidad_tomada FROM seguimiento_items "
        "WHERE seguimiento_id = %s ORDER BY material_id",
        (seguimiento_id,),
    )
    assert filas == [(material_a, 20), (material_b, 30)]
    assert eventos(conn, "AGREGAR_TODO") == 1

    # Doble invocación: no duplica líneas ni eventos (REQ-P2-CON-004).
    agregadas = _valor(
        conn,
        "SELECT fn_agregar_todo_seguimiento(%s, %s, 'qa', NULL)",
        (seguimiento_id, equipo_id),
    )
    assert agregadas == 0
    filas = _todos(
        conn,
        "SELECT count(*) FROM seguimiento_items WHERE seguimiento_id = %s",
        (seguimiento_id,),
    )
    assert filas == [(2,)]
    assert eventos(conn, "AGREGAR_TODO") == 1


def test_agregar_todo_validaciones(conn):
    material_a = crear_material(conn)
    equipo_id, _ = stockear_equipo_teams(conn, material_a, 50)
    otro_equipo = crear_equipo(conn, "Otro equipo")
    seguimiento_id = crear_seguimiento(
        conn, equipo_id, [{"material_id": material_a, "cantidad_tomada": 5}]
    )

    msg = _falla(
        conn,
        "SELECT fn_agregar_todo_seguimiento(999999, %s, 'qa', NULL)",
        (equipo_id,),
    )
    assert "no encontrado" in msg

    msg = _falla(
        conn,
        "SELECT fn_agregar_todo_seguimiento(%s, %s, 'qa', NULL)",
        (seguimiento_id, otro_equipo),
    )
    assert "no pertenece a la unidad" in msg

    _uno(
        conn,
        "SELECT fn_cerrar_seguimiento(%s, %s::jsonb, 'qa', NULL)",
        (seguimiento_id, json.dumps([{"material_id": material_a, "cantidad_consumida": 1}])),
    )
    msg = _falla(
        conn,
        "SELECT fn_agregar_todo_seguimiento(%s, %s, 'qa', NULL)",
        (seguimiento_id, equipo_id),
    )
    assert "no se encuentra en estado ABIERTA" in msg
    assert eventos(conn, "AGREGAR_TODO") == 0


# ================================================================
# T1.6 — Cierre con Acta de Consumo y Acta de Entrega
# ================================================================


def test_cerrar_seguimiento_acta_consumo(conn):
    """REQ-P2-CON-005 / REQ-P2-REP-004: el consumido se descuenta directamente
    en SQL; snapshot jsonb y evento ACTA_CONSUMO_GENERADA."""
    material_a = crear_material(conn, descripcion="Material Consumo")
    equipo_id, _ = stockear_equipo_teams(conn, material_a, 50)
    seguimiento_id = crear_seguimiento(
        conn,
        equipo_id,
        [{"material_id": material_a, "cantidad_tomada": 20}],
        observaciones="Seguimiento de consumo QA",
    )

    _uno(
        conn,
        "SELECT fn_cerrar_seguimiento(%s, %s::jsonb, 'qa', 'Cierre QA')",
        (
            seguimiento_id,
            json.dumps([{"material_id": material_a, "cantidad_consumida": 15}]),
        ),
    )

    # Stock de la unidad descontado por el CONSUMIDO (50 - 15 = 35).
    assert stock_equipo(conn, equipo_id, material_a) == 35
    estado = _valor(
        conn, "SELECT estado FROM seguimientos WHERE id = %s", (seguimiento_id,)
    )
    assert estado == "CERRADA"

    # Acta de Consumo con snapshot completo.
    acta = _uno(
        conn,
        "SELECT snapshot FROM actas_reportes WHERE tipo = 'CONSUMO' AND seguimiento_id = %s",
        (seguimiento_id,),
    )
    assert acta is not None
    snapshot = acta[0]
    assert snapshot["acta_tipo"] == "CONSUMO"
    assert snapshot["equipo_nombre"] == "Equipo QA"
    assert snapshot["observaciones_cierre"] == "Cierre QA"
    item = snapshot["items"][0]
    assert item["cantidad_tomada"] == 20
    assert "cantidad_sobrante" not in item
    assert item["cantidad_consumida"] == 15  # registrada por la función

    assert eventos(conn, "SEGUIMIENTO_CERRADO") == 1
    assert eventos(conn, "ACTA_CONSUMO_GENERADA") == 1


def test_cerrar_seguimiento_rollback_consumo_invalido(conn):
    """Atomicidad: un consumo inválido revierte TODA la transacción de
    cierre (estado, stock, acta y auditoría)."""
    material_a = crear_material(conn)
    equipo_id, _ = stockear_equipo_teams(conn, material_a, 50)
    seguimiento_id = crear_seguimiento(
        conn, equipo_id, [{"material_id": material_a, "cantidad_tomada": 20}]
    )
    eventos_antes = _valor(
        conn, "SELECT count(*) FROM auditoria_eventos"
    )
    actas_antes = _valor(conn, "SELECT count(*) FROM actas_reportes")

    msg = _falla(
        conn,
        "SELECT fn_cerrar_seguimiento(%s, %s::jsonb, 'qa', NULL)",
        (
            seguimiento_id,
            json.dumps([{"material_id": material_a, "cantidad_consumida": 25}]),
        ),
    )
    assert "Consumo inválido" in msg

    estado = _valor(
        conn, "SELECT estado FROM seguimientos WHERE id = %s", (seguimiento_id,)
    )
    assert estado == "ABIERTA"
    assert stock_equipo(conn, equipo_id, material_a) == 50
    assert _valor(conn, "SELECT count(*) FROM auditoria_eventos") == eventos_antes
    assert _valor(conn, "SELECT count(*) FROM actas_reportes") == actas_antes


def test_acta_entrega_en_misma_transaccion_de_confirmacion(conn):
    """REQ-P2-REP-003: el registro del Acta de Entrega ocurre dentro de la
    transacción SQL de la confirmación TEAMS (transición BORRADOR ->
    CONFIRMADO, nombre REAL del esquema) con snapshot jsonb."""
    material_a = crear_material(conn, descripcion="Material Entrega")
    equipo_id, movimiento_id = stockear_equipo_teams(conn, material_a, 50)

    estado = _valor(
        conn, "SELECT estado FROM movimientos_cabecera WHERE id = %s", (movimiento_id,)
    )
    assert estado == "CONFIRMADO"

    acta = _uno(
        conn,
        "SELECT snapshot FROM actas_reportes WHERE tipo = 'ENTREGA' AND movimiento_id = %s",
        (movimiento_id,),
    )
    assert acta is not None
    snapshot = acta[0]
    assert snapshot["acta_tipo"] == "ENTREGA"
    assert snapshot["movimiento_id"] == movimiento_id
    assert snapshot["usuario"] == "qa"
    assert snapshot["origen"]["nombre"] == "Inventario General"
    assert snapshot["destino_equipo"]["equipo_id"] == equipo_id
    assert snapshot["items"][0]["cantidad"] == 50
    assert snapshot["items"][0]["descripcion"] == "Material Entrega"

    assert eventos(conn, "ACTA_ENTREGA_GENERADA") == 1


def test_acta_entrega_no_aplica_a_devuel(conn):
    material_a = crear_material(conn)
    equipo_id, _ = stockear_equipo_teams(conn, material_a, 50)
    movimiento_id = _valor(
        conn,
        "INSERT INTO movimientos_cabecera "
        "(tipo_movimiento, usuario, origen_equipo_id, destino_almacen_id) "
        "VALUES ('DEVOL', 'qa', %s, 1) RETURNING id",
        (equipo_id,),
    )
    _ejecuta(
        conn,
        "INSERT INTO movimientos_detalle (movimiento_id, material_id, cantidad) "
        "VALUES (%s, %s, %s)",
        (movimiento_id, material_a, 10),
    )
    _uno(conn, "SELECT fn_procesar_movimiento(%s)", (movimiento_id,))

    assert _valor(
        conn,
        "SELECT count(*) FROM actas_reportes WHERE tipo = 'ENTREGA' AND movimiento_id = %s",
        (movimiento_id,),
    ) == 0


def test_acta_entrega_sin_duplicado_en_update_noop(conn):
    material_a = crear_material(conn)
    _, movimiento_id = stockear_equipo_teams(conn, material_a, 50)
    assert _valor(
        conn,
        "SELECT count(*) FROM actas_reportes WHERE tipo = 'ENTREGA' AND movimiento_id = %s",
        (movimiento_id,),
    ) == 1

    _ejecuta(
        conn,
        "UPDATE movimientos_cabecera SET estado = 'CONFIRMADO' WHERE id = %s",
        (movimiento_id,),
    )
    assert _valor(
        conn,
        "SELECT count(*) FROM actas_reportes WHERE tipo = 'ENTREGA' AND movimiento_id = %s",
        (movimiento_id,),
    ) == 1


def test_acta_entrega_snapshot_conservado_tras_cancelacion(conn):
    material_a = crear_material(conn)
    _, movimiento_id = stockear_equipo_teams(conn, material_a, 50)
    _uno(conn, "SELECT fn_cancelar_movimiento(%s, %s)", (movimiento_id, "motivo QA"))

    assert _valor(
        conn,
        "SELECT count(*) FROM actas_reportes WHERE tipo = 'ENTREGA' AND movimiento_id = %s",
        (movimiento_id,),
    ) == 1  # el snapshot histórico permanece inmutable


# ================================================================
# T1.7 — Concurrencia con FOR UPDATE (sin deadlocks, resultado exacto)
# ================================================================


def test_concurrencia_sumas_paralelas_for_update(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    resultado = [None, None]
    barrera = threading.Barrier(2)
    hilos = [
        threading.Thread(
            target=_hilo(
                "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', NULL)",
                (material_id,),
                resultado,
                0,
                barrera,
            )
        ),
        threading.Thread(
            target=_hilo(
                "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 7, 'qa', NULL)",
                (material_id,),
                resultado,
                1,
                barrera,
            )
        ),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert resultado == ["ok", "ok"]

    assert stock_general(conn, material_id) == 22  # 10 + 5 + 7, sin pérdidas
    assert eventos(conn, "SUMA_CANTIDAD") == 2


def test_concurrencia_movimientos_opuestos_sin_deadlock(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)
    carga_inicial_fibra(conn, "PAQUETE", material_id, 10)

    resultado = [None, None]
    barrera = threading.Barrier(2)
    hilos = [
        threading.Thread(
            target=_hilo(
                "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'PAQUETE', %s, 3, 'qa', NULL)",
                (material_id,),
                resultado,
                0,
                barrera,
            )
        ),
        threading.Thread(
            target=_hilo(
                "SELECT fn_mover_material('FO', 'PAQUETE', 'GENERAL', NULL, %s, 2, 'qa', NULL)",
                (material_id,),
                resultado,
                1,
                barrera,
            )
        ),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert resultado == ["ok", "ok"]

    # Resultado determinista independiente del orden de serialización.
    assert stock_general(conn, material_id) == 9
    assert stock_fibra(conn, "PAQUETE", material_id) == 11
    assert eventos(conn, "MOVIMIENTO_INVENTARIO") == 2


def test_concurrencia_suma_y_mover_mismo_material(conn):
    material_id = crear_material(conn)
    carga_inicial_general(conn, material_id, 10)

    resultado = [None, None]
    barrera = threading.Barrier(2)
    hilos = [
        threading.Thread(
            target=_hilo(
                "SELECT fn_sumar_cantidad('GENERAL', NULL, %s, 5, 'qa', NULL)",
                (material_id,),
                resultado,
                0,
                barrera,
            )
        ),
        threading.Thread(
            target=_hilo(
                "SELECT fn_mover_material('GENERAL', NULL, 'FO', 'EN_USO', %s, 3, 'qa', NULL)",
                (material_id,),
                resultado,
                1,
                barrera,
            )
        ),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert resultado == ["ok", "ok"]

    assert stock_general(conn, material_id) == 12  # (10+5)-3 o (10-3)+5
    assert stock_fibra(conn, "EN_USO", material_id) == 3
    assert eventos(conn, "SUMA_CANTIDAD") == 1
    assert eventos(conn, "MOVIMIENTO_INVENTARIO") == 1
