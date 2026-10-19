"""Migración 0029 (actividades por Unidad) — pruebas IN-PLACE sobre
`p2_test` (véase tests/helpers/migraciones.py). Cada prueba degrada p2_test
a 0028, verifica creación/eliminación de objetos y restaura SIEMPRE la
cabeza.

Cubre (paquete 2026-10-actividades-unidad, T3): creación de tabla,
CHECKs, UNIQUEs, FKs RESTRICT, índice, trigger de inmutabilidad y funciones
(REQ-ACT-008/009/010/011/012/015/020); downgrade solo de esquema que
conserva eventos y tablas ajenas; re-aplicación no-op.
"""

from tests.helpers.migraciones import BACKEND_DIR, alembic, esquema_en, sql


def _rev() -> str:
    return sql("SELECT version_num FROM alembic_version")[0][0]


def _existe_tabla() -> bool:
    return sql("SELECT to_regclass('actividades_reportes') IS NOT NULL")[0][0]


def _existe_fn(nombre: str) -> bool:
    return sql(
        "SELECT count(*) FROM pg_proc WHERE proname = %s "
        "AND pronamespace = 'public'::regnamespace",
        (nombre,),
    )[0][0] == 1


def test_req_act_020_creacion_de_objetos_y_downgrade_limpio() -> None:
    with esquema_en("0028"):
        assert not _existe_tabla()
        assert not _existe_fn("fn_crear_actividad")
        assert not _existe_fn("fn_actividad_pendiente")

        alembic("upgrade", "0029")
        assert _rev() == "0029"
        assert _existe_tabla()
        assert _existe_fn("fn_crear_actividad")
        assert _existe_fn("fn_actividad_pendiente")

        for nombre in (
            "ck_actividades_folio_positivo",
            "ck_actividades_vehiculo_no_vacio",
            "ck_actividades_clientes_no_vacio",
            "ck_actividades_direcciones_no_vacio",
            "ck_actividades_actividades_rango",
            "ck_actividades_materiales_array",
            "uq_actividades_folio",
            "uq_actividades_seguimiento",
            "fk_actividades_seguimiento",
            "fk_actividades_equipo",
        ):
            assert sql(
                "SELECT count(*) FROM pg_constraint WHERE conname = %s", (nombre,)
            )[0][0] == 1, nombre
        assert sql(
            "SELECT count(*) FROM pg_indexes WHERE indexname = "
            "'ix_actividades_equipo_created'"
        )[0][0] == 1
        assert sql(
            "SELECT tgenabled FROM pg_trigger WHERE tgname = "
            "'tg_ledger_actividades_inmutable'"
        ) == [("O",)]

        # La función de folio usa advisory lock y emite el evento nuevo.
        defn = sql(
            "SELECT pg_get_functiondef('fn_crear_actividad(integer, integer, "
            "text, text, text, jsonb, text, text)'::regprocedure)"
        )[0][0]
        assert "pg_advisory_xact_lock" in defn
        assert "ACTIVIDAD_CONFIRMADA" in defn

        # Las tablas preexistentes no se alteran: la cadena completa sigue
        # recorrible y el downgrade elimina SOLO los objetos de 0029.
        alembic("downgrade", "0028")
        assert _rev() == "0028"
        assert not _existe_tabla()
        assert not _existe_fn("fn_crear_actividad")
        assert not _existe_fn("fn_actividad_pendiente")
        assert sql("SELECT to_regclass('seguimientos') IS NOT NULL")[0][0]
        assert sql("SELECT to_regclass('actas_reportes') IS NOT NULL")[0][0]

        alembic("upgrade", "0029")
        assert _existe_tabla()


def test_req_act_020_downgrade_conserva_eventos_auditoria_ya_escritos() -> None:
    """El downgrade elimina la tabla pero NO los eventos ACTIVIDAD_CONFIRMADA
    ya escritos (ledger append-only); seguimientos y catálogo quedan intactos."""
    with esquema_en("0028"):
        alembic("upgrade", "0029")
        eq = sql("INSERT INTO equipos (nombre) VALUES ('U29') RETURNING equipo_id")[0][0]
        mat = sql(
            "INSERT INTO catalogo_materiales (descripcion, u_m) VALUES ('M29','PZ') "
            "RETURNING id_lista"
        )[0][0]
        seg = sql(
            "INSERT INTO seguimientos (equipo_id, usuario, estado, closed_at) "
            "VALUES (%s,'qa','CERRADA', now()) RETURNING id",
            (eq,),
        )[0][0]
        sql(
            "INSERT INTO seguimiento_items (seguimiento_id, material_id, "
            "cantidad_tomada, cantidad_consumida) VALUES (%s,%s,10,3)",
            (seg, mat),
        )
        aid = sql(
            "SELECT fn_crear_actividad(%s,%s,'V','C','D','[\"A\"]',NULL,'qa')",
            (eq, seg),
        )[0][0]
        assert aid == 1

        alembic("downgrade", "0028")
        assert not _existe_tabla()
        assert sql("SELECT count(*) FROM auditoria_eventos "
                   "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA'")[0][0] == 1
        assert sql("SELECT count(*) FROM seguimientos WHERE id = %s", (seg,))[0][0] == 1
        assert sql("SELECT count(*) FROM catalogo_materiales WHERE id_lista = %s", (mat,))[0][0] == 1

        # Re-aplicación: la tabla vuelve vacía (no recrea filas).
        alembic("upgrade", "0029")
        assert sql("SELECT count(*) FROM actividades_reportes")[0][0] == 0


def test_req_act_020_reupgrade_es_noop_y_modulo_compila() -> None:
    """Aplicar 0029 estando ya en 0029 no falla ni duplica objetos."""
    with esquema_en("0028"):
        alembic("upgrade", "0029")
        alembic("upgrade", "0029")
        assert _rev() == "0029"
        assert sql(
            "SELECT count(*) FROM pg_constraint WHERE conname = 'uq_actividades_folio'"
        )[0][0] == 1
        assert (BACKEND_DIR / "alembic" / "versions" / "0029_actividades_unidad.py").exists()
