"""Migración 0028 (purga del legado Paquete / En Uso de FO) — pruebas
IN-PLACE sobre `p2_test` (véase tests/helpers/migraciones.py). Cada prueba
degrada p2_test a 0027, siembra datos legacy y restaura SIEMPRE la cabeza.

Cubre RF-1 (purga de dependientes), RF-2 (esquema/funciones sin legado),
RF-3 (stock y ledger no legacy intactos), RF-6 (triggers reactivados,
guardia E-1, evento PURGA_LEGACY_FO, abortos con rollback, downgrade de
esquema) y los casos límite E1-E13 de spec.md.
"""

import importlib.util
import json
from pathlib import Path

import psycopg
import pytest
import sqlalchemy as sa

from tests.helpers.migraciones import (
    SA_TEST_URL,
    BACKEND_DIR,
    alembic,
    esquema_en,
    sql,
)

TRIGGERS = {
    "tg_ledger_auditoria_inmutable": "O",
    "tg_ledger_actas_inmutable": "O",
}


def _rev() -> str:
    return sql("SELECT version_num FROM alembic_version")[0][0]


def _triggers() -> dict[str, str]:
    return dict(
        sql(
            "SELECT tgname, tgenabled FROM pg_trigger WHERE tgname IN "
            "('tg_ledger_auditoria_inmutable','tg_ledger_actas_inmutable')"
        )
    )


def _fn(nombre: str) -> str:
    return sql(f"SELECT pg_get_functiondef('{nombre}'::regproc)")[0][0]


def _modulo_0028():
    spec = importlib.util.spec_from_file_location(
        "m0028", BACKEND_DIR / "alembic" / "versions" / "0028_purga_legacy_fo.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _evento(tipo, det, ao=None, ad=None, mat=None, cant=None):
    sql(
        "INSERT INTO auditoria_eventos (usuario, tipo_accion, material_id, "
        "almacen_origen_id, almacen_destino_id, cantidad, resultado, detalles) "
        "VALUES ('qa', %s, %s, %s, %s, %s, 'EXITO', %s::json)",
        (tipo, mat, ao, ad, cant, None if det is None else json.dumps(det)),
    )


def _sembrar() -> dict:
    """Siembra en 0027 un escenario con casos que se purgan y que se
    conservan. Devuelve los ids relevantes."""
    sql("TRUNCATE TABLE actas_reportes, operaciones_idempotencia, "
        "movimientos_detalle, movimientos_cabecera, inventario_equipos, "
        "inventario_almacen, inventario_fibra, equipos, auditoria_eventos, "
        "actor_almacen_scopes, catalogo_materiales, categorias "
        "RESTART IDENTITY CASCADE")
    for nombre in ("PZ", "PAQUETE (100 PZ)"):
        sql("INSERT INTO ums (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (nombre,))
    for nombre, tipo in (
        ("Fibra Optica - Paquete", "FO_PAQUETE"),
        ("Fibra Optica - En Uso", "FO_EN_USO"),
        ("Inventario FO", "FO"),
    ):
        sql(
            "INSERT INTO secciones (nombre, tipo, is_active) VALUES (%s, %s, FALSE) "
            "ON CONFLICT (nombre) DO NOTHING",
            (nombre, tipo),
        )
    ids = {
        t: sql("SELECT almacen_id FROM secciones WHERE tipo = %s", (t,))[0][0]
        for t in ("GENERAL", "FO_PAQUETE", "FO_EN_USO", "FO")
    }
    sg, sp, su, sf = (ids[k] for k in ("GENERAL", "FO_PAQUETE", "FO_EN_USO", "FO"))
    m1 = sql("INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
             "VALUES ('M1','Mat uno','PZ') RETURNING id_lista")[0][0]
    m2 = sql("INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
             "VALUES ('M2','Mat paq','PAQUETE (100 PZ)') RETURNING id_lista")[0][0]
    sql("INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual) "
        "VALUES (%s,%s,100.5),(%s,%s,50)", (sg, m1, sg, m2))
    sql("INSERT INTO inventario_fibra (material_id, stock_actual) "
        "VALUES (%s,40),(%s,10.25)", (m1, m2))
    e1 = sql("INSERT INTO equipos (nombre) VALUES ('U1') RETURNING equipo_id")[0][0]
    e2 = sql("INSERT INTO equipos (nombre) VALUES ('U2') RETURNING equipo_id")[0][0]

    def mov(tipo, estado, orig, dest, oe, de):
        return sql(
            "INSERT INTO movimientos_cabecera (tipo_movimiento, estado, usuario, "
            "origen_almacen_id, destino_almacen_id, origen_equipo_id, "
            "destino_equipo_id) VALUES (%s,%s,'qa',%s,%s,%s,%s) RETURNING id",
            (tipo, estado, orig, dest, oe, de),
        )[0][0]

    def lin(mid, mat, cant, org=None):
        sql("INSERT INTO movimientos_detalle (movimiento_id, material_id, "
            "cantidad, origen_almacen_id) VALUES (%s,%s,%s,%s)", (mid, mat, cant, org))

    mv1 = mov("TEAMS", "CONFIRMADO", sp, None, None, e1)   # legacy cabecera
    lin(mv1, m1, 2, sp)
    lin(mv1, m2, 1, sp)
    mv2 = mov("TEAMS", "CONFIRMADO", sg, None, None, e1)   # MIXTO (E1)
    lin(mv2, m1, 1, su)
    lin(mv2, m2, 1, sg)
    mv3 = mov("TEAMS", "BORRADOR", su, None, None, e2)     # borrador (E2)
    lin(mv3, m1, 3, su)
    mv4 = mov("DEVOL", "CANCELADO", None, sp, e1, None)    # DEVOL destino legacy
    lin(mv4, m1, 1)
    mv5 = mov("TEAMS", "CONFIRMADO", sf, None, None, e2)   # FO vivo
    lin(mv5, m1, 1, sf)
    mv6 = mov("TEAMS", "CONFIRMADO", sg, None, None, e2)   # GENERAL vivo
    lin(mv6, m2, 1, sg)
    for mid in (mv1, mv2, mv6):
        sql("INSERT INTO actas_reportes (tipo, movimiento_id, snapshot) "
            "VALUES ('ENTREGA', %s, %s::jsonb)",
            (mid, json.dumps({"movimiento_id": mid, "u_m": "PAQUETE (100 PZ)"})))
    a1 = sql("SELECT id FROM actas_reportes WHERE movimiento_id = %s", (mv1,))[0][0]
    a6 = sql("SELECT id FROM actas_reportes WHERE movimiento_id = %s", (mv6,))[0][0]
    sql("INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual, "
        "ultimo_movimiento_id) VALUES (%s,%s,5,%s),(%s,%s,6,%s),(%s,%s,7,%s)",
        (e1, m1, mv1, e1, m2, mv6, e2, m1, mv3))
    sql("INSERT INTO actor_almacen_scopes (actor_id, almacen_id) VALUES "
        "('a1',%s),('a1',%s),('a1',%s),('a2',%s)", (sp, su, sf, sg))
    sql("INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor, resultado) "
        "VALUES ('TEAMS_CREAR','k1','a',%s::jsonb),('SUMA_CANTIDAD','k2','a',%s::jsonb),"
        "('MOVIMIENTO_INVENTARIO','k3','a',%s::jsonb),('TEAMS_CREAR','k4','a',%s::jsonb),"
        "('X','k5','a',%s::jsonb),('X','k6','a',NULL)",
        (json.dumps({"movimiento_id": mv1}), json.dumps({"modulo": "PAQUETE"}),
         json.dumps({"modulo": "EN_USO"}), json.dumps({"movimiento_id": mv6}),
         json.dumps({"stock_nuevo": 1})))
    # --- eventos a eliminar (13): (a) columna, (b) JSON anidado, (c), (d)
    _evento("TEAMS_TRANSFERENCIA", {"x": 1}, ao=sp)
    _evento("TEAMS_TRANSFERENCIA", {"x": 1}, ad=su)
    _evento("STOCK_INICIAL_FO", {"modulo": "PAQUETE"})
    _evento("SUMA_CANTIDAD", {"destino": "FO", "modulo": "EN_USO"})
    _evento("MOVIMIENTO_INVENTARIO",
            {"origen": {"tipo": "FO", "modulo": "EN_USO"}, "destino": {"tipo": "GENERAL"}})
    _evento("X", {"origen_modulo": "PAQUETE"})
    _evento("X", {"a": [{"b": {"destino_modulo": "EN_USO"}}]})
    _evento("FO_UNIFICADO", {"modulo": "Inventario FO"}, mat=m1, cant=15)
    _evento("TEAMS_TRANSFERENCIA", {"movimiento_id": mv1})
    _evento("DEVOL_DEVOLUCION", {"movimiento_id": mv4})
    _evento("ACTA_ENTREGA_GENERADA", {"acta_id": a1, "movimiento_id": mv1})
    _evento("TEAMS_TRANSFERENCIA", {"movimiento_id": mv2})
    _evento("TEAMS_TRANSFERENCIA", {"movimiento_id": mv3})
    # --- eventos a conservar (10): dominio vivo (E5), detalles NULL, otros
    _evento("MATERIAL_MODIFICADO", {"modulo": "CATALOGO", "accion": "MODIFICAR",
                                    "valores_nuevos": {"u_m": "PAQUETE (100 PZ)"}}, mat=m2)
    _evento("UM_CREADA", {"modulo": "CATALOGO", "u_m": "PAQUETE (100 PZ)"})
    _evento("MATERIAL_MODIFICADO", {"valores_anteriores": {"u_m": "PAQUETE (100 PZ)"},
                                    "valores_nuevos": {"u_m": "PZ", "modulo": "CATALOGO"}})
    _evento("AUDIT_NULL", None)
    _evento("TEAMS_TRANSFERENCIA", {"movimiento_id": mv5})
    _evento("ACTA_ENTREGA_GENERADA", {"acta_id": a6, "movimiento_id": mv6})
    _evento("DESPLIEGUE_X", {"modulo": "FO"})
    _evento("X", {"modulo": "PAQUETE_X"})
    _evento("X", {"modulo": "paquete"})
    _evento("AJUSTE", {"almacen_id": sg}, ao=sg, ad=sf)
    return {"sg": sg, "sp": sp, "su": su, "sf": sf, "m1": m1, "m2": m2,
            "e1": e1, "e2": e2, "mv5": mv5, "mv6": mv6, "a6": a6}


_TIPOS_CONSERVADOS = ("MATERIAL_MODIFICADO", "UM_CREADA", "AUDIT_NULL",
                      "DESPLIEGUE_X", "AJUSTE")


def _conservados(d: dict) -> list[tuple]:
    return sql(
        "SELECT id, md5(e::text) FROM auditoria_eventos e WHERE "
        "tipo_accion = ANY(%s) OR (tipo_accion='X' AND detalles::text ~ 'PAQUETE_X|paquete') "
        "OR (tipo_accion='TEAMS_TRANSFERENCIA' AND (detalles::jsonb->>'movimiento_id')::int = %s) "
        "OR (tipo_accion='ACTA_ENTREGA_GENERADA' AND (detalles::jsonb->>'acta_id')::int = %s) "
        "ORDER BY id",
        (list(_TIPOS_CONSERVADOS), d["mv5"], d["a6"]),
    )


def _stock() -> tuple:
    return (
        sql("SELECT * FROM inventario_almacen ORDER BY 1,2"),
        sql("SELECT * FROM inventario_fibra ORDER BY 1"),
        sql("SELECT equipo_id, material_id, stock_actual FROM inventario_equipos ORDER BY 1,2"),
    )


def test_RF_001_003_purga_conserva_dominio_vivo_y_ledger_no_legacy() -> None:
    """RF-1/RF-3/RF-6, E1-E5/E13: se purgan movimientos (incluido el mixto y
    el borrador), actas, scopes, idempotencia, eventos (a)-(d) y las
    secciones; se conservan stock, eventos de dominio vivo (unidad PAQUETE
    (100 PZ), CATALOGO, DESPLIEGUE_*, detalles NULL) y se emite UN evento
    PURGA_LEGACY_FO."""
    with esquema_en("0027"):
        d = _sembrar()
        stock0 = _stock()
        cons0 = _conservados(d)
        assert len(cons0) == 10
        assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == 23

        alembic("upgrade", "0028")

        assert _rev() == "0028"
        assert sql("SELECT tipo FROM secciones ORDER BY almacen_id") == [("GENERAL",), ("FO",)]
        assert sorted(r[0] for r in sql("SELECT id FROM movimientos_cabecera")) == sorted(
            [d["mv5"], d["mv6"]])
        assert sql("SELECT count(*) FROM movimientos_detalle")[0][0] == 2
        assert [r[0] for r in sql("SELECT id FROM actas_reportes")] == [d["a6"]]
        assert sorted(r[0] for r in sql(
            "SELECT actor_id || ':' || almacen_id FROM actor_almacen_scopes")) == sorted(
            [f"a1:{d['sf']}", f"a2:{d['sg']}"])
        assert sorted(r[0] for r in sql("SELECT clave FROM operaciones_idempotencia")) == [
            "k4", "k5", "k6"]
        # E13: puntero legacy -> NULL; el de un movimiento vivo se conserva.
        assert sql("SELECT equipo_id, material_id, ultimo_movimiento_id "
                   "FROM inventario_equipos ORDER BY 1,2") == [
            (d["e1"], d["m1"], None), (d["e1"], d["m2"], d["mv6"]), (d["e2"], d["m1"], None)]
        # RF-3: stock idéntico fila a fila y eventos conservados idénticos.
        assert _stock() == stock0
        assert _conservados(d) == cons0

        evs = sql("SELECT usuario, resultado, detalles::text FROM auditoria_eventos "
                  "WHERE tipo_accion = 'PURGA_LEGACY_FO'")
        assert len(evs) == 1 and evs[0][0] == "migracion-0028" and evs[0][1] == "EXITO"
        det = json.loads(evs[0][2])
        assert det["enmienda"] == "E-1" and det["migracion"] == "0028"
        assert det["eliminados_por_tabla"]["auditoria_eventos"] == 13
        assert det["eliminados_por_tabla"]["movimientos_cabecera"] == 4
        assert det["eliminados_por_tabla"]["secciones"] == 2
        assert sum(det["eliminados_por_tipo_accion"].values()) == 13
        assert "password" not in evs[0][2].lower()
        assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == 10 + 1

        # E6: un actor con scope solo legacy ('a3') pierde ese scope y no
        # recibe nada nuevo (la copia a FO fue cosa de 0027, no de 0028).
        # (Sembrado abajo en test_E6.)

        # RF-3: las secuencias de id no se reinician.
        assert sql("SELECT last_value FROM movimientos_cabecera_id_seq")[0][0] >= 6

        # E8: re-aplicar 0028 (ya en 0028) es un no-op.
        alembic("upgrade", "0028")
        assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == 10 + 1


def test_RF_002_006_esquema_funciones_y_triggers_tras_la_purga() -> None:
    """RF-2/RF-6: CHECK solo GENERAL/FO, funciones sin literales legacy y
    ambos triggers de ledger activos (DELETE/UPDATE posteriores fallan)."""
    with esquema_en("0027"):
        _sembrar()
        alembic("upgrade", "0028")

        assert _triggers() == TRIGGERS
        for tabla in ("auditoria_eventos", "actas_reportes"):
            for stmt in (f"DELETE FROM {tabla}", f"UPDATE {tabla} SET created_at = now()"):
                with pytest.raises(psycopg.errors.Error, match="append-only"):
                    sql(stmt)
        with pytest.raises(psycopg.errors.CheckViolation):
            sql("INSERT INTO secciones (nombre, tipo) VALUES ('x', 'FO_PAQUETE')")
        assert sql(
            "SELECT count(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace "
            "AND prokind = 'f' AND pg_get_functiondef(oid) ~ 'FO_PAQUETE|FO_EN_USO'"
        )[0][0] == 0
        assert "= 'FO'" in _fn("fn_procesar_movimiento")


@pytest.mark.parametrize(
    "motivo, preparar, esperado",
    [
        (
            "saldo legacy en inventario_almacen",
            lambda d: sql("INSERT INTO inventario_almacen (almacen_id, material_id, "
                          "stock_actual) VALUES (%s, %s, 5)", (d["sp"], d["m2"])),
            "aún referencian",
        ),
        (
            "literal FO_PAQUETE en evento superviviente (d2)",
            lambda d: _evento("X", {"nota": "FO_PAQUETE"}),
            "(d2)",
        ),
        (
            "clave origen_almacen_id hacia sección purgada (d2)",
            lambda d: _evento("X", {"a": {"origen_almacen_id": d["su"]}}),
            "(d2)",
        ),
    ],
)
def test_RF_006_abortos_con_rollback_total(motivo, preparar, esperado) -> None:
    """RF-6: ante cualquier verificación fallida la migración aborta, la base
    queda en 0027, los datos intactos y los triggers activos."""
    with esquema_en("0027"):
        d = _sembrar()
        try:
            preparar(d)
            n_eventos = sql("SELECT count(*) FROM auditoria_eventos")[0][0]
            r = alembic("upgrade", "0028", ok=False)
            assert r.returncode != 0 and esperado in r.stderr, (motivo, r.stderr[-400:])
            assert _rev() == "0027"
            assert _triggers() == TRIGGERS
            assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == n_eventos
            assert sql("SELECT count(*) FROM movimientos_cabecera")[0][0] == 6
            assert sql("SELECT count(*) FROM secciones WHERE tipo LIKE 'FO\\_%%'")[0][0] == 2
        finally:
            # Limpia el residuo sembrado para que la restauración a la
            # cabeza (esquema_en) pueda purgar sin abortar.
            sql("DELETE FROM inventario_almacen WHERE almacen_id IN "
                "(SELECT almacen_id FROM secciones WHERE tipo LIKE 'FO\\_%%')")
            sql("TRUNCATE TABLE auditoria_eventos RESTART IDENTITY")


def test_RF_006_trigger_previamente_deshabilitado_aborta() -> None:
    """RF-6: si un trigger de ledger no está habilitado antes de empezar, la
    migración aborta (estado anómalo) sin efectos."""
    with esquema_en("0027"):
        _sembrar()
        try:
            sql("ALTER TABLE actas_reportes DISABLE TRIGGER tg_ledger_actas_inmutable")
            r = alembic("upgrade", "0028", ok=False)
            assert r.returncode != 0 and "no está habilitado" in r.stderr
            assert _rev() == "0027"
        finally:
            sql("ALTER TABLE actas_reportes ENABLE TRIGGER tg_ledger_actas_inmutable")


def test_RF_006_guardia_e1_aborta_fuera_de_p2_y_p2_test() -> None:
    """RF-6/E12: con dependientes legacy y una base distinta de p2/p2_test la
    guardia aborta; sin dependientes (base nueva) o en p2/p2_test pasa."""
    m = _modulo_0028()
    with pytest.raises(RuntimeError, match="guardia E-1"):
        m._guardia_e1("otra_bd", 3)
    m._guardia_e1("otra_bd", 0)
    m._guardia_e1("p2", 3)
    m._guardia_e1("p2_test", 3)
    with sa.create_engine(SA_TEST_URL).connect() as c:
        m._guardia_e1(c, 3)  # conexión real: p2_test


def test_E7_sin_secciones_legacy_es_noop_de_datos() -> None:
    """E7: sin secciones legacy la migración no purga nada ni emite evento;
    solo redefine CHECK y funciones (los ledger quedan intactos)."""
    with esquema_en("0027"):
        d = _sembrar()
        # Quita toda dependencia y las secciones legacy a mano.
        sql("TRUNCATE TABLE actas_reportes, operaciones_idempotencia, movimientos_detalle, "
            "movimientos_cabecera, actor_almacen_scopes RESTART IDENTITY CASCADE")
        sql("DELETE FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')")
        n = sql("SELECT count(*) FROM auditoria_eventos")[0][0]
        alembic("upgrade", "0028")
        assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == n
        assert sql("SELECT count(*) FROM auditoria_eventos "
                   "WHERE tipo_accion = 'PURGA_LEGACY_FO'")[0][0] == 0
        assert _triggers() == TRIGGERS
        assert d["sg"]


def test_RF_006_downgrade_solo_esquema_y_reupgrade_noop() -> None:
    """RF-6/E11: `downgrade 0027` restaura el CHECK y las funciones de 0027
    sin recrear filas ni abortar; re-aplicar 0028 es un no-op de datos."""
    with esquema_en("0027"):
        _sembrar()
        fn_p27, fn_c27 = _fn("fn_procesar_movimiento"), _fn("fn_cancelar_movimiento")
        alembic("upgrade", "0028")
        assert _fn("fn_procesar_movimiento") != fn_p27

        alembic("downgrade", "0027")
        assert _rev() == "0027"
        assert _fn("fn_procesar_movimiento") == fn_p27
        assert _fn("fn_cancelar_movimiento") == fn_c27
        assert sql("SELECT count(*) FROM secciones WHERE tipo LIKE 'FO\\_%%'")[0][0] == 0
        assert sql("SELECT count(*) FROM movimientos_cabecera")[0][0] == 2  # sin recrear
        assert _triggers() == TRIGGERS
        sql("INSERT INTO secciones (nombre, tipo) VALUES ('Legacy x', 'FO_PAQUETE')")
        sql("DELETE FROM secciones WHERE nombre = 'Legacy x'")  # CHECK ampliado

        n = sql("SELECT count(*) FROM auditoria_eventos")[0][0]
        alembic("upgrade", "0028")
        # Sin secciones legacy: no-op de datos (sin segundo evento de purga).
        assert sql("SELECT count(*) FROM auditoria_eventos")[0][0] == n


def test_RF_008_ciclo_head_0026_head_en_p2_test_limpia() -> None:
    """RF-8/R5: la cadena es recorrible desde la cabeza en una base sin
    referencias a la sección FO (lo que usan esquema_en('0024'|'0025'|'0026'))."""
    with esquema_en("0026"):
        assert _rev() == "0026"
    assert _rev() == "0029"
    assert Path(BACKEND_DIR / "alembic" / "versions" / "0028_purga_legacy_fo.py").exists()


def test_E6_actor_con_scope_solo_legacy_pierde_el_scope_sin_recibir_nada() -> None:
    """E6: un actor con scope únicamente sobre una sección legacy queda sin
    scopes tras la purga; los scopes FO/GENERAL de otros actores se conservan."""
    with esquema_en("0027"):
        d = _sembrar()
        sql("INSERT INTO actor_almacen_scopes (actor_id, almacen_id) VALUES ('solo-legacy', %s)",
            (d["sp"],))
        alembic("upgrade", "0028")
        assert sql("SELECT count(*) FROM actor_almacen_scopes WHERE actor_id = 'solo-legacy'")[0][0] == 0
        assert sql("SELECT count(*) FROM actor_almacen_scopes WHERE actor_id IN ('a1','a2')")[0][0] == 2


def test_RF_006_downgrade_emite_notice_de_datos_no_restaurados() -> None:
    """RF-6: el downgrade avisa que los datos purgados no se restauran."""
    with esquema_en("0027"):
        _sembrar()
        alembic("upgrade", "0028")
        r = alembic("downgrade", "0027")
        assert "no se restauran" in (r.stderr + r.stdout)
        alembic("upgrade", "0028")
