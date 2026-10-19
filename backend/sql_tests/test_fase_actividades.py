"""Pruebas SQL de actividades por Unidad — paquete
2026-10-actividades-unidad, T3 (REQ-ACT-002/003/004/008/009/010/011/012/015).

Cobertura 100 % SQL (psycopg sobre p2_test, autocommit por sentencia):
  * fn_crear_actividad: feliz (folio, fecha now(), snapshot con
    valor_unitario congelado), folio correlativo y sin huecos (rollback no
    consume número), concurrencia sobre el mismo seguimiento (una gana,
    la otra 409), inmutabilidad de la tabla, validaciones (seguimiento
    abierto/ajeno/inexistente, duplicado, campos y celdas fuera de rango).
  * fn_actividad_pendiente: solo el CERRADA más reciente sin actividad,
    con materiales y valor_unitario vigente; vacío tras confirmar;
    seguimiento sin consumo confirmable (materiales '[]').
  * Auditoría: evento ACTIVIDAD_CONFIRMADA con convención de
    ACTA_CONSUMO_GENERADA; inventario/actas/seguimientos intactos.
"""

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.errors import RaiseException

# URL nativa psycopg a p2_test (misma convención que test_fase1_consumo.py).
PSYCOPG_TEST_URL = os.environ["P2_TEST_DATABASE_URL"].replace(
    "postgresql+psycopg://", "postgresql://"
)

P0001 = "P0001"


# ================================================================
# Helpers
# ================================================================


def _valor(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()[0]


def _uno(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def _ejecuta(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)


def _falla(conn, query, params=()):
    """Ejecuta y espera un RAISE EXCEPTION (SQLSTATE P0001); devuelve el
    mensaje."""
    with pytest.raises(RaiseException) as excinfo:
        with conn.cursor() as cur:
            cur.execute(query, params)
    assert excinfo.value.sqlstate == P0001
    return str(excinfo.value)


def crear_material(conn, descripcion="Material QA", u_m="PZ", valor="1.000"):
    return _valor(
        conn,
        "INSERT INTO catalogo_materiales (descripcion, u_m, valor_unitario) "
        "VALUES (%s, %s, %s) RETURNING id_lista",
        (descripcion, u_m, valor),
    )


def crear_equipo(conn, nombre="Unidad QA"):
    return _valor(
        conn, "INSERT INTO equipos (nombre) VALUES (%s) RETURNING equipo_id", (nombre,)
    )


def crear_seguimiento(conn, equipo_id, estado="CERRADA", usuario="qa"):
    return _valor(
        conn,
        "INSERT INTO seguimientos (equipo_id, usuario, estado, closed_at) "
        "VALUES (%s, %s, %s, CASE WHEN %s = 'CERRADA' THEN now() END) RETURNING id",
        (equipo_id, usuario, estado, estado),
    )


def crear_item(conn, seguimiento_id, material_id, tomada=10, consumida=4):
    _ejecuta(
        conn,
        "INSERT INTO seguimiento_items (seguimiento_id, material_id, "
        "cantidad_tomada, cantidad_consumida) VALUES (%s,%s,%s,%s)",
        (seguimiento_id, material_id, tomada, consumida),
    )


def confirmar(conn, equipo_id, seguimiento_id, vehiculo="Camioneta 1",
              clientes="Cliente A", direcciones="Calle 1",
              actividades='["Tendido de fibra"]', comentarios=None):
    return _valor(
        conn,
        "SELECT fn_crear_actividad(%s,%s,%s,%s,%s,%s::jsonb,%s,'qa')",
        (equipo_id, seguimiento_id, vehiculo, clientes, direcciones,
         actividades, comentarios),
    )


def escenario_consumo(conn, valor="12.345", nombre="Unidad QA"):
    """Unidad + material + seguimiento CERRADA con un item consumido."""
    eq = crear_equipo(conn, nombre)
    mat = crear_material(conn, valor=valor)
    seg = crear_seguimiento(conn, eq)
    crear_item(conn, seg, mat)
    return eq, mat, seg


# ================================================================
# fn_crear_actividad — flujo feliz y folio
# ================================================================


def test_feliz_folio_fecha_snapshot_y_evento(conn):
    eq, mat, seg = escenario_consumo(conn)
    aid = confirmar(conn, eq, seg)

    row = _uno(
        conn,
        "SELECT folio_num, vehiculo, clientes, direcciones, actividades, "
        "comentarios, usuario, created_at, materiales "
        "FROM actividades_reportes WHERE id = %s",
        (aid,),
    )
    assert row[0] == 1
    assert row[1:4] == ("Camioneta 1", "Cliente A", "Calle 1")
    assert row[4] == ["Tendido de fibra"]
    assert row[5] is None
    assert row[6] == "qa"
    assert abs(row[7] - datetime.now(timezone.utc)) < timedelta(minutes=5)  # now()
    materiales = row[8]
    assert len(materiales) == 1
    assert materiales[0]["material_id"] == mat
    assert materiales[0]["cantidad_consumida"] == 4
    assert Decimal(str(materiales[0]["valor_unitario"])) == Decimal("12.345")

    ev = _uno(
        conn,
        "SELECT usuario, tipo_accion, equipo_origen_id, resultado, detalles "
        "FROM auditoria_eventos WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA'",
    )
    assert ev[0] == "qa" and ev[1] == "ACTIVIDAD_CONFIRMADA"
    assert ev[2] == eq and ev[3] == "EXITO"
    assert ev[4]["folio"] == "R0001"
    assert ev[4]["actividad_id"] == aid
    assert ev[4]["seguimiento_id"] == seg
    assert ev[4]["equipo_id"] == eq


def test_folio_correlativo_global_y_formato_r4(conn):
    eq1, _, s1 = escenario_consumo(conn)
    eq2 = crear_equipo(conn, "Unidad B")
    s2 = crear_seguimiento(conn, eq2)
    confirmar(conn, eq1, s1)
    confirmar(conn, eq2, s2, vehiculo="Van 9")
    folios = _valor(
        conn, "SELECT array_agg(folio_num ORDER BY folio_num) FROM actividades_reportes"
    )
    assert folios == [1, 2]  # global: la segunda Unidad continúa la serie


def test_rollback_no_consume_folio(conn):
    eq, _, seg = escenario_consumo(conn)
    with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute(
            "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')", (eq, seg)
        )
        cur.execute("ROLLBACK")
    eq2, _, s2 = escenario_consumo(conn, nombre="Unidad Rollback")
    aid = confirmar(conn, eq2, s2)
    assert _valor(
        conn, "SELECT folio_num FROM actividades_reportes WHERE id = %s", (aid,)
    ) == 1


def test_inmutabilidad_update_delete(conn):
    eq, _, seg = escenario_consumo(conn)
    confirmar(conn, eq, seg)
    assert "append-only" in _falla(
        conn, "UPDATE actividades_reportes SET vehiculo = 'ZZ'"
    )
    assert "append-only" in _falla(conn, "DELETE FROM actividades_reportes")


def test_concurrencia_mismo_seguimiento_una_sola_actividad(conn):
    """Dos sesiones compiten por el mismo seguimiento: exactamente una gana
    (FOR UPDATE) y la otra recibe el rechazo de duplicado; folio único."""
    eq, _, seg = escenario_consumo(conn)
    barrier = threading.Barrier(2)
    resultados: list = []
    errores: list = []

    def intento():
        with psycopg.connect(PSYCOPG_TEST_URL) as c:
            barrier.wait()
            try:
                with c.cursor() as cur:
                    cur.execute(
                        "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
                        (eq, seg),
                    )
                    resultados.append(cur.fetchone()[0])
                c.commit()
            except RaiseException as exc:
                errores.append(str(exc))

    hilos = [threading.Thread(target=intento) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(resultados) == 1
    assert len(errores) == 1
    assert "ya tiene una actividad confirmada" in errores[0]
    assert _valor(conn, "SELECT count(*) FROM actividades_reportes") == 1
    assert _valor(conn, "SELECT count(*) FROM actividades_reportes WHERE folio_num = 1") == 1


def test_concurrencia_seguimientos_distintos_folios_unicos(conn):
    """El advisory lock serializa el MAX+1: folios distintos sin huecos."""
    eq1, _, s1 = escenario_consumo(conn)
    eq2 = crear_equipo(conn, "Unidad C")
    s2 = crear_seguimiento(conn, eq2)
    barrier = threading.Barrier(2)

    def intento(eq, seg):
        with psycopg.connect(PSYCOPG_TEST_URL) as c:
            barrier.wait()
            with c.cursor() as cur:
                cur.execute(
                    "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
                    (eq, seg),
                )
            c.commit()

    hilos = [threading.Thread(target=intento, args=a) for a in ((eq1, s1), (eq2, s2))]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(_valor(
        conn, "SELECT array_agg(folio_num) FROM actividades_reportes"
    )) == [1, 2]


# ================================================================
# Validaciones (RF-3, RF-13 en defensa de profundidad)
# ================================================================


def test_validaciones_seguimiento(conn):
    eq, _, _ = escenario_consumo(conn)
    abierto = crear_seguimiento(conn, eq, estado="ABIERTA")
    assert "debe estar cerrado" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
        (eq, abierto),
    )
    # Seguimiento de otra Unidad -> mismo 404 «inexistente para la Unidad».
    eq2 = crear_equipo(conn, "Otra")
    s2 = crear_seguimiento(conn, eq2)
    assert "inexistente para la Unidad" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
        (eq, s2),
    )
    # Inexistente.
    assert "inexistente para la Unidad" in _falla(
        conn, "SELECT fn_crear_actividad(%s,999999,'V','C','D','[\"A\"]',NULL,'qa')", (eq,)
    )


def test_duplicado_rechazado(conn):
    eq, _, seg = escenario_consumo(conn)
    confirmar(conn, eq, seg)
    assert "ya tiene una actividad confirmada" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
        (eq, seg),
    )


def test_validaciones_campos_y_celdas(conn):
    eq, _, seg = escenario_consumo(conn)
    assert "vehículo es obligatorio" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'   ','C','D','[\"A\"]',NULL,'qa')",
        (eq, seg),
    )
    assert "cliente es obligatorio" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V',' ','D','[\"A\"]',NULL,'qa')",
        (eq, seg),
    )
    assert "dirección es obligatoria" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','','[\"A\"]',NULL,'qa')",
        (eq, seg),
    )
    assert "comentarios no pueden exceder" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',%s,'qa')",
        (eq, seg, "x" * 2001),
    )
    assert "entre 1 y 30 celdas" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[]',NULL,'qa')", (eq, seg)
    )
    assert "entre 1 y 30 celdas" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D',%s,NULL,'qa')",
        (eq, seg, json.dumps([f"a{i}" for i in range(31)])),
    )
    assert "texto de 1 a 500" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[1]',NULL,'qa')", (eq, seg)
    )
    assert "texto de 1 a 500" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"   \"]',NULL,'qa')",
        (eq, seg),
    )
    assert "texto de 1 a 500" in _falla(
        conn, "SELECT fn_crear_actividad(%s,%s,'V','C','D',%s,NULL,'qa')",
        (eq, seg, json.dumps(["x" * 501])),
    )
    # Límite superior exacto: 30 celdas de 500 caracteres entran.
    _valor(
        conn,
        "SELECT fn_crear_actividad(%s,%s,'V','C','D',%s,NULL,'qa')",
        (eq, seg, json.dumps(["x" * 500 for _ in range(30)])),
    )


# ================================================================
# fn_actividad_pendiente (RF-2/3/4) y snapshot congelado (RF-10)
# ================================================================


def test_pendiente_solo_mas_reciente_cerrada_sin_actividad(conn):
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    viejo = crear_seguimiento(conn, eq)
    crear_item(conn, viejo, mat, consumida=2)
    crear_seguimiento(conn, eq, estado="ABIERTA")
    nuevo = crear_seguimiento(conn, eq)
    crear_item(conn, nuevo, mat, consumida=7)

    pend = _uno(conn, "SELECT * FROM fn_actividad_pendiente(%s)", (eq,))
    assert pend[0] == nuevo  # el más reciente; el viejo se ignora en la UI
    assert pend[1] is not None
    assert pend[2][0]["cantidad_consumida"] == 7

    confirmar(conn, eq, nuevo)
    # C-1: tras confirmar el más reciente, el siguiente pendiente es el
    # seguimiento cerrado anterior sin actividad (el backend no lo bloquea).
    pend = _uno(conn, "SELECT * FROM fn_actividad_pendiente(%s)", (eq,))
    assert pend[0] == viejo
    assert pend[2][0]["cantidad_consumida"] == 2


def test_valor_unitario_vigente_en_pendiente_y_congelado_en_confirmacion(conn):
    eq, mat, seg = escenario_consumo(conn, valor="5.500")
    pend = _uno(conn, "SELECT * FROM fn_actividad_pendiente(%s)", (eq,))
    assert Decimal(str(pend[2][0]["valor_unitario"])) == Decimal("5.500")

    # El catálogo cambia ANTES de confirmar: el snapshot congela el nuevo
    # valor vigente en ese instante.
    _ejecuta(conn, "UPDATE catalogo_materiales SET valor_unitario = 9.999 WHERE id_lista = %s", (mat,))
    aid = confirmar(conn, eq, seg)
    row = _uno(conn, "SELECT materiales FROM actividades_reportes WHERE id = %s", (aid,))
    assert Decimal(str(row[0][0]["valor_unitario"])) == Decimal("9.999")

    # Un cambio POSTERIOR no altera el registro confirmado.
    _ejecuta(conn, "UPDATE catalogo_materiales SET valor_unitario = 1.111 WHERE id_lista = %s", (mat,))
    row = _uno(conn, "SELECT materiales FROM actividades_reportes WHERE id = %s", (aid,))
    assert Decimal(str(row[0][0]["valor_unitario"])) == Decimal("9.999")


def test_seguimiento_sin_consumo_confirmable_con_materiales_vacios(conn):
    """RF-4: cero consumo -> pendiente con materiales '[]' y confirmación
    permitida."""
    eq = crear_equipo(conn)
    seg = crear_seguimiento(conn, eq)
    pend = _uno(conn, "SELECT * FROM fn_actividad_pendiente(%s)", (eq,))
    assert pend[2] == []
    aid = confirmar(conn, eq, seg)
    row = _uno(conn, "SELECT materiales FROM actividades_reportes WHERE id = %s", (aid,))
    assert row[0] == []


# ================================================================
# Sin efectos sobre inventario (RF-15)
# ================================================================


def test_inventario_seguimientos_y_actas_intactos(conn):
    eq, mat, seg = escenario_consumo(conn)
    _ejecuta(
        conn,
        "INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual) "
        "VALUES (%s,%s,42.5)",
        (eq, mat),
    )
    actas_antes = _valor(conn, "SELECT count(*) FROM actas_reportes")
    confirmar(conn, eq, seg)
    assert _uno(
        conn, "SELECT stock_actual FROM inventario_equipos WHERE equipo_id = %s AND material_id = %s",
        (eq, mat),
    )[0] == Decimal("42.5")
    assert _valor(conn, "SELECT count(*) FROM actas_reportes") == actas_antes
    assert _uno(
        conn, "SELECT estado FROM seguimientos WHERE id = %s", (seg,)
    )[0] == "CERRADA"


def test_folio_10000_o_mayor_no_se_trunca_en_el_evento(conn):
    """T7/F-6: el folio no se trunca al superar 4 dígitos (R10000). El evento
    inmutable debe registrar el folio completo (lpad trunca por la derecha)."""
    eq, mat, seg = escenario_consumo(conn)
    # Siembra una actividad previa con folio 9999 (INSERT permitido; solo
    # UPDATE/DELETE están bloqueados) para que la siguiente sea la 10000.
    previo = crear_seguimiento(conn, eq)
    _ejecuta(
        conn,
        "INSERT INTO actividades_reportes (folio_num, seguimiento_id, equipo_id, "
        "vehiculo, clientes, direcciones, actividades, materiales, usuario) "
        "VALUES (9999, %s, %s, 'V', 'C', 'D', '[\"A\"]'::jsonb, '[]'::jsonb, 'qa')",
        (previo, eq),
    )
    aid = confirmar(conn, eq, seg)
    assert _valor(
        conn, "SELECT folio_num FROM actividades_reportes WHERE id = %s", (aid,)
    ) == 10000
    ev = _valor(
        conn,
        "SELECT detalles->>'folio' FROM auditoria_eventos "
        "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA' "
        "AND (detalles->>'actividad_id')::int = %s",
        (aid,),
    )
    assert ev == "R10000"
