"""Pruebas SQL de la Referencia de materiales por Unidad — paquete
2026-10-referencia-materiales-unidades, T3 (REQ-REF-011/012/018, plan §3).

Cobertura 100 % SQL (psycopg sobre p2_test):
  * Restricciones de la tabla (plan §3.1): PK compuesta — un duplicado de
    (equipo_id, material_id) viola la unicidad; CHECK — cantidad 0 o
    negativa viola ck_referencia_cantidad_positiva; FKs — equipo_id o
    material_id inexistente viola la FK.
  * ON DELETE RESTRICT: ni un material del catálogo ni una Unidad con
    línea de Referencia pueden borrarse físicamente; la línea se conserva.
  * Trigger de auditoría (plan §3.2, REQ-REF-012): exactamente un evento
    por INSERT/UPDATE/DELETE con detalles correctos (modulo, accion,
    valores_anteriores/valores_nuevos con cantidad_semanal, material_id y
    equipo_id), resultado EXITO y actor tomado de app.actor; un UPDATE que
    no cambia la cantidad no emite evento; un actor vacío cae a
    CURRENT_USER (NULLIF del GUC ya fijado en la sesión).
  * REQ-REF-011: las mutaciones de la Referencia dejan idénticas las tablas
    de negocio (snapshot de conteos/checksum antes y después) y la lectura
    no emite eventos.

El GUC app.actor se fija con set_config(…, true) DENTRO de la misma
transacción que el DML (igual que el backend), por lo que las pruebas de
auditoría usan una conexión transaccional propia; el resto usa el fixture
`conn` en autocommit (una sentencia fallida no aborta la sesión).
"""

import os
from contextlib import contextmanager
from decimal import Decimal

import psycopg
import pytest
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    RestrictViolation,
    UniqueViolation,
)

# URL nativa psycopg a p2_test (misma convención que test_fase_actividades.py).
PSYCOPG_TEST_URL = os.environ["P2_TEST_DATABASE_URL"].replace(
    "postgresql+psycopg://", "postgresql://"
)

# Tablas de negocio que la Referencia no puede alterar (REQ-REF-011).
TABLAS_NEGOCIO = (
    "inventario_equipos",
    "inventario_almacen",
    "inventario_fibra",
    "catalogo_materiales",
    "equipo_material_config",
    "movimientos_cabecera",
    "movimientos_detalle",
    "seguimientos",
    "seguimiento_items",
    "actividades_reportes",
    "actas_reportes",
)


# ================================================================
# Helpers
# ================================================================


def _uno(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def _ejecuta(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)


def _valor(conn, query, params=()):
    return _uno(conn, query, params)[0]


def _todos(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def crear_material(conn, descripcion="Material QA", u_m="PZ"):
    return _valor(
        conn,
        "INSERT INTO catalogo_materiales (descripcion, u_m) VALUES (%s,%s) "
        "RETURNING id_lista",
        (descripcion, u_m),
    )


def crear_equipo(conn, nombre="Unidad QA"):
    return _valor(
        conn, "INSERT INTO equipos (nombre) VALUES (%s) RETURNING equipo_id", (nombre,)
    )


def linea(conn, equipo_id, material_id, cantidad="5.000"):
    _ejecuta(
        conn,
        "INSERT INTO referencia_materiales (equipo_id, material_id, cantidad_semanal) "
        "VALUES (%s,%s,%s)",
        (equipo_id, material_id, cantidad),
    )


def _eventos_referencia(conn):
    return _todos(
        conn,
        "SELECT id, usuario, tipo_accion, material_id, resultado, detalles "
        "FROM auditoria_eventos WHERE tipo_accion IN "
        "('REFERENCIA_LINEA_CREADA','REFERENCIA_LINEA_MODIFICADA',"
        "'REFERENCIA_LINEA_ELIMINADA') ORDER BY id",
    )


def _snapshot(conn) -> dict:
    """Conteo + checksum (md5 de la concatenación ordenada de los md5 de
    cada fila completa) de cada tabla de negocio: determinista y comparable
    antes/después de las mutaciones de la Referencia."""
    out = {}
    for tabla in TABLAS_NEGOCIO:
        out[tabla] = _uno(
            conn,
            f"SELECT count(*), "
            f"coalesce(md5(string_agg(md5(t::text), '' ORDER BY md5(t::text))), md5('')) "
            f"FROM {tabla} t",
        )
    return out


@contextmanager
def transaccion(actor=None, actor_previo_vacio=False):
    """Conexión psycopg transaccional: set_config('app.actor', …, true) y el
    DML conviven en la misma transacción (el context manager de psycopg hace
    commit al salir y rollback ante un fallo), igual que el backend."""
    with psycopg.connect(PSYCOPG_TEST_URL) as c:
        with c.cursor() as cur:
            if actor_previo_vacio:
                # GUC ya fijado en la sesión y luego vaciado: el NULLIF de la
                # función hace caer el actor a CURRENT_USER (plan §3.2/§3.3).
                cur.execute("SELECT set_config('app.actor','actor-previo',true)")
                cur.execute("SELECT set_config('app.actor','',true)")
            elif actor is not None:
                cur.execute("SELECT set_config('app.actor',%s,true)", (actor,))
            yield c, cur


# ================================================================
# Restricciones de la tabla (plan §3.1)
# ================================================================


def test_req_ref_018_pk_compuesta_rechaza_duplicado(conn):
    """REQ-REF-018 (plan §3.1/P-2; §6 carrera de altas): (equipo_id,
    material_id) es único; reinsertar la misma línea viola la PK sin
    duplicar ni emitir un segundo evento."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    linea(conn, eq, mat, "5.000")
    with pytest.raises(UniqueViolation):
        linea(conn, eq, mat, "9.000")
    assert _todos(
        conn, "SELECT cantidad_semanal FROM referencia_materiales"
    ) == [(Decimal("5.000"),)]
    assert len(_eventos_referencia(conn)) == 1


@pytest.mark.parametrize("cantidad", ["0", "-1", "-0.001"])
def test_req_ref_018_check_cantidad_positiva_rechaza_no_positivos(conn, cantidad):
    """REQ-REF-018 (plan §3.1; REQ-REF-007, cantidad > 0): cero o negativa
    viola ck_referencia_cantidad_positiva y no escribe fila ni evento."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    with pytest.raises(CheckViolation):
        linea(conn, eq, mat, cantidad)
    assert _valor(conn, "SELECT count(*) FROM referencia_materiales") == 0
    assert _valor(conn, "SELECT count(*) FROM auditoria_eventos") == 0


def test_req_ref_018_fks_rechazan_equipo_o_material_inexistente(conn):
    """REQ-REF-018 (plan §3.1): equipo_id y material_id son FKs hacia
    `equipos` y `catalogo_materiales`; un id inexistente viola la FK y no
    escribe."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    with pytest.raises(ForeignKeyViolation):
        linea(conn, 999999, mat, "5.000")
    with pytest.raises(ForeignKeyViolation):
        linea(conn, eq, 999999, "5.000")
    assert _valor(conn, "SELECT count(*) FROM referencia_materiales") == 0


def test_req_ref_018_restrict_no_borra_material_con_linea(conn):
    """REQ-REF-018 (plan §3.1, ON DELETE RESTRICT): el borrado físico de un
    material del catálogo con línea de Referencia falla y la línea se
    conserva (el material ya usa soft-delete vía is_active)."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    linea(conn, eq, mat)
    with pytest.raises(RestrictViolation):
        _ejecuta(conn, "DELETE FROM catalogo_materiales WHERE id_lista = %s", (mat,))
    assert _valor(
        conn,
        "SELECT count(*) FROM referencia_materiales "
        "WHERE equipo_id = %s AND material_id = %s",
        (eq, mat),
    ) == 1
    assert _valor(
        conn, "SELECT count(*) FROM catalogo_materiales WHERE id_lista = %s", (mat,)
    ) == 1


def test_req_ref_018_restrict_no_borra_unidad_con_linea(conn):
    """REQ-REF-018 (plan §3.1, ON DELETE RESTRICT): el borrado físico de una
    Unidad con línea de Referencia falla y la línea se conserva (la Unidad
    ya usa soft-delete vía is_active)."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    linea(conn, eq, mat)
    with pytest.raises(RestrictViolation):
        _ejecuta(conn, "DELETE FROM equipos WHERE equipo_id = %s", (eq,))
    assert _valor(
        conn,
        "SELECT count(*) FROM referencia_materiales "
        "WHERE equipo_id = %s AND material_id = %s",
        (eq, mat),
    ) == 1


# ================================================================
# Trigger de auditoría (plan §3.2, REQ-REF-012)
# ================================================================


def test_req_ref_012_auditoria_tres_eventos_con_detalles_y_actor(conn):
    """REQ-REF-012: INSERT/UPDATE/DELETE emiten exactamente un evento cada
    uno, en orden, con actor (app.actor), material_id, equipo_id y valores
    anteriores/nuevos de cantidad_semanal; resultado EXITO."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    with transaccion(actor="qa-ref") as (c, cur):
        cur.execute(
            "INSERT INTO referencia_materiales (equipo_id, material_id, cantidad_semanal) "
            "VALUES (%s,%s,%s)",
            (eq, mat, "5.000"),
        )
        cur.execute(
            "UPDATE referencia_materiales SET cantidad_semanal = '7.500' "
            "WHERE equipo_id = %s AND material_id = %s",
            (eq, mat),
        )
        cur.execute(
            "DELETE FROM referencia_materiales "
            "WHERE equipo_id = %s AND material_id = %s",
            (eq, mat),
        )

    evs = _eventos_referencia(conn)
    assert [e[2] for e in evs] == [
        "REFERENCIA_LINEA_CREADA",
        "REFERENCIA_LINEA_MODIFICADA",
        "REFERENCIA_LINEA_ELIMINADA",
    ]
    for ev in evs:
        assert ev[1] == "qa-ref"  # usuario = app.actor
        assert ev[3] == mat  # material_id (columna del ledger)
        assert ev[4] == "EXITO"
        det = ev[5]
        assert det["modulo"] == "REFERENCIA"
        assert det["equipo_id"] == eq

    creada, modificada, eliminada = (e[5] for e in evs)
    assert creada["accion"] == "CREAR"
    assert creada["valores_anteriores"] is None
    assert Decimal(str(creada["valores_nuevos"]["cantidad_semanal"])) == Decimal(
        "5.000"
    )
    assert modificada["accion"] == "MODIFICAR"
    assert Decimal(
        str(modificada["valores_anteriores"]["cantidad_semanal"])
    ) == Decimal("5.000")
    assert Decimal(str(modificada["valores_nuevos"]["cantidad_semanal"])) == Decimal(
        "7.500"
    )
    assert eliminada["accion"] == "ELIMINAR"
    assert Decimal(
        str(eliminada["valores_anteriores"]["cantidad_semanal"])
    ) == Decimal("7.500")
    assert eliminada["valores_nuevos"] is None


def test_req_ref_012_update_sin_cambio_de_cantidad_no_emite_evento(conn):
    """REQ-REF-012 (plan §3.2): un UPDATE con la misma cantidad (no-op
    idempotente) y un UPDATE que solo cambia updated_at NO emiten evento."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    linea(conn, eq, mat, "5.000")
    with transaccion(actor="qa-ref") as (c, cur):
        cur.execute(
            "UPDATE referencia_materiales SET cantidad_semanal = '5.000' "
            "WHERE equipo_id = %s AND material_id = %s",
            (eq, mat),
        )
        cur.execute(
            "UPDATE referencia_materiales SET updated_at = now() "
            "WHERE equipo_id = %s AND material_id = %s",
            (eq, mat),
        )
    evs = _eventos_referencia(conn)
    assert [e[2] for e in evs] == ["REFERENCIA_LINEA_CREADA"]


def test_req_ref_012_actor_vacio_cae_a_current_user(conn):
    """REQ-REF-012 (plan §3.2/§3.3): con app.actor ya fijado en la sesión y
    luego vaciado (''), el NULLIF de la función hace que el evento registre
    CURRENT_USER en lugar del actor vacío."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    with transaccion(actor_previo_vacio=True) as (c, cur):
        cur.execute(
            "INSERT INTO referencia_materiales (equipo_id, material_id, cantidad_semanal) "
            "VALUES (%s,%s,%s)",
            (eq, mat, "5.000"),
        )
    usuario_bd = _valor(conn, "SELECT CURRENT_USER")
    ev = _uno(
        conn,
        "SELECT usuario FROM auditoria_eventos WHERE tipo_accion = 'REFERENCIA_LINEA_CREADA'",
    )
    assert ev[0] == usuario_bd
    assert ev[0] not in ("", "actor-previo")


# ================================================================
# Sin efectos sobre tablas de negocio (REQ-REF-011)
# ================================================================


def test_req_ref_011_mutaciones_sin_efecto_sobre_tablas_de_negocio(conn):
    """REQ-REF-011: INSERT/UPDATE/DELETE de líneas de Referencia dejan
    idénticas las tablas de negocio listadas (conteos + checksum por fila
    completa); la única escritura fuera de `referencia_materiales` es el
    ledger de auditoría, y la lectura no emite eventos."""
    eq = crear_equipo(conn)
    mat = crear_material(conn)
    # Siembra mínima de negocio para que el checksum sea significativo.
    _ejecuta(
        conn,
        "INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual) "
        "VALUES (%s,%s,42.5)",
        (eq, mat),
    )
    _ejecuta(
        conn,
        "INSERT INTO inventario_fibra (material_id, stock_actual) VALUES (%s,40)",
        (mat,),
    )
    _ejecuta(
        conn,
        "INSERT INTO equipo_material_config (equipo_id, material_id, stock_minimo_local) "
        "VALUES (%s,%s,3)",
        (eq, mat),
    )
    general = _valor(conn, "SELECT almacen_id FROM secciones WHERE tipo = 'GENERAL'")
    _ejecuta(
        conn,
        "INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual) "
        "VALUES (%s,%s,10)",
        (general, mat),
    )
    antes = _snapshot(conn)

    linea(conn, eq, mat, "5.000")
    _ejecuta(
        conn,
        "UPDATE referencia_materiales SET cantidad_semanal = '9.000' "
        "WHERE equipo_id = %s AND material_id = %s",
        (eq, mat),
    )
    _ejecuta(
        conn,
        "DELETE FROM referencia_materiales WHERE equipo_id = %s AND material_id = %s",
        (eq, mat),
    )
    assert _snapshot(conn) == antes

    # La lectura de la Referencia no escribe ni emite eventos.
    n_eventos = _valor(conn, "SELECT count(*) FROM auditoria_eventos")
    _todos(conn, "SELECT * FROM referencia_materiales")
    assert _valor(conn, "SELECT count(*) FROM auditoria_eventos") == n_eventos
