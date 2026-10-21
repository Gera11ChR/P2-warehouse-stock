"""Migración 0030 (Referencia de materiales por Unidad) — pruebas IN-PLACE
sobre `p2_test` (véase tests/helpers/migraciones.py). Cada prueba degrada
p2_test a 0029, verifica creación/eliminación de objetos y restaura SIEMPRE
la cabeza (`esquema_en` garantiza `upgrade head` en `finally` aunque la
prueba falle).

Cubre (paquete 2026-10-referencia-materiales-unidades, T3, plan §3):
creación de la tabla `referencia_materiales` con columnas/tipos/defaults
correctos, PK compuesta, CHECK de cantidad positiva y FKs ON DELETE
RESTRICT; trigger y función de auditoría habilitados en `public`; downgrade
que elimina SOLO los objetos del paquete y conserva los eventos
`REFERENCIA_LINEA_*` ya escritos; ciclo upgrade → downgrade → upgrade con
esquema completo y operativo (REQ-REF-011/012/018).
"""

from decimal import Decimal

from tests.helpers.migraciones import alembic, esquema_en, sql


def _rev() -> str:
    return sql("SELECT version_num FROM alembic_version")[0][0]


def _existe_tabla() -> bool:
    return sql("SELECT to_regclass('referencia_materiales') IS NOT NULL")[0][0]


def _existe_fn(nombre: str) -> bool:
    return sql(
        "SELECT count(*) FROM pg_proc WHERE proname = %s "
        "AND pronamespace = 'public'::regnamespace",
        (nombre,),
    )[0][0] == 1


def _existe_trigger(nombre: str) -> bool:
    return sql(
        "SELECT count(*) FROM pg_trigger WHERE tgname = %s", (nombre,)
    )[0][0] == 1


def _columnas() -> list[tuple]:
    return sql(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_name = 'referencia_materiales' ORDER BY ordinal_position"
    )


def _sembrar_linea(cantidad: str = "5.000", sufijo: str = "") -> tuple[int, int]:
    """Unidad + material + línea de Referencia (con el trigger activo).
    `sufijo` permite sembrar dos veces en el mismo test (equipos.nombre y
    catalogo_materiales.descripcion son únicos)."""
    eq = sql(
        "INSERT INTO equipos (nombre) VALUES (%s) RETURNING equipo_id",
        (f"U30{sufijo}",),
    )[0][0]
    mat = sql(
        "INSERT INTO catalogo_materiales (descripcion, u_m) VALUES (%s,'PZ') "
        "RETURNING id_lista",
        (f"M30{sufijo}",),
    )[0][0]
    sql(
        "INSERT INTO referencia_materiales (equipo_id, material_id, cantidad_semanal) "
        "VALUES (%s,%s,%s)",
        (eq, mat, cantidad),
    )
    return eq, mat


def _evento_creada() -> list[tuple]:
    return sql(
        "SELECT usuario, material_id, resultado, detalles FROM auditoria_eventos "
        "WHERE tipo_accion = 'REFERENCIA_LINEA_CREADA' ORDER BY id"
    )


def test_req_ref_018_upgrade_crea_tabla_constraints_trigger_y_funcion() -> None:
    """REQ-REF-018 (plan §3.1-§3.2): el upgrade 0029→0030 crea la tabla con
    las columnas/tipos/defaults correctos (NUMERIC(12,3), TIMESTAMPTZ con
    CURRENT_TIMESTAMP), la PK compuesta `pk_referencia_materiales`, el CHECK
    `ck_referencia_cantidad_positiva`, las FKs `fk_referencia_equipo` y
    `fk_referencia_material` ON DELETE RESTRICT, la función de auditoría en
    `public` y el trigger habilitado."""
    with esquema_en("0029"):
        assert not _existe_tabla()
        assert not _existe_fn("fn_auditar_referencia_materiales")
        assert not _existe_trigger("tg_auditar_referencia_materiales")

        alembic("upgrade", "0030")
        assert _rev() == "0030"
        assert _existe_tabla()
        assert _existe_fn("fn_auditar_referencia_materiales")

        assert _columnas() == [
            ("equipo_id", "integer", "NO", None),
            ("material_id", "integer", "NO", None),
            ("cantidad_semanal", "numeric", "NO", None),
            ("created_at", "timestamp with time zone", "NO", "CURRENT_TIMESTAMP"),
            ("updated_at", "timestamp with time zone", "NO", "CURRENT_TIMESTAMP"),
        ]
        assert sql(
            "SELECT numeric_precision, numeric_scale FROM information_schema.columns "
            "WHERE table_name = 'referencia_materiales' "
            "AND column_name = 'cantidad_semanal'"
        ) == [(12, 3)]

        assert sql(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'pk_referencia_materiales'"
        ) == [("PRIMARY KEY (equipo_id, material_id)",)]
        assert sql(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_referencia_cantidad_positiva'"
        ) == [("CHECK ((cantidad_semanal > (0)::numeric))",)]
        for nombre, esperado in (
            (
                "fk_referencia_equipo",
                "FOREIGN KEY (equipo_id) REFERENCES equipos(equipo_id) "
                "ON DELETE RESTRICT",
            ),
            (
                "fk_referencia_material",
                "FOREIGN KEY (material_id) REFERENCES catalogo_materiales(id_lista) "
                "ON DELETE RESTRICT",
            ),
        ):
            assert sql(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
                (nombre,),
            ) == [(esperado,)]
        assert sql(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname IN ('fk_referencia_equipo','fk_referencia_material') "
            "ORDER BY conname"
        ) == [("r",), ("r",)]

        assert sql(
            "SELECT tgfoid::regprocedure::text, tgenabled FROM pg_trigger "
            "WHERE tgname = 'tg_auditar_referencia_materiales'"
        ) == [("fn_auditar_referencia_materiales()", "O")]
        defn = sql(
            "SELECT pg_get_functiondef('fn_auditar_referencia_materiales()'::regprocedure)"
        )[0][0]
        for tipo in (
            "REFERENCIA_LINEA_CREADA",
            "REFERENCIA_LINEA_MODIFICADA",
            "REFERENCIA_LINEA_ELIMINADA",
        ):
            assert tipo in defn
        assert "app.actor" in defn
        assert "IS NOT DISTINCT FROM" in defn  # UPDATE sin cambio: sin evento


def test_req_ref_018_downgrade_elimina_solo_objetos_del_paquete() -> None:
    """REQ-REF-018 (plan §3.1): el downgrade 0030→0029 elimina la tabla
    (con sus filas), el trigger y la función; ningún objeto preexistente
    cambia (`equipos`, `catalogo_materiales`, `auditoria_eventos` y sus
    triggers siguen existiendo y habilitados)."""
    with esquema_en("0029"):
        alembic("upgrade", "0030")
        _sembrar_linea()
        assert sql("SELECT count(*) FROM referencia_materiales")[0][0] == 1

        alembic("downgrade", "0029")
        assert _rev() == "0029"
        assert not _existe_tabla()
        assert not _existe_fn("fn_auditar_referencia_materiales")
        assert not _existe_trigger("tg_auditar_referencia_materiales")

        for tabla in ("equipos", "catalogo_materiales", "auditoria_eventos"):
            assert sql("SELECT to_regclass(%s) IS NOT NULL", (tabla,))[0][0], tabla
        assert sql(
            "SELECT tgname, tgenabled FROM pg_trigger WHERE tgname IN "
            "('tg_ledger_auditoria_inmutable','tg_auditar_modificacion_material') "
            "ORDER BY tgname"
        ) == [
            ("tg_auditar_modificacion_material", "O"),
            ("tg_ledger_auditoria_inmutable", "O"),
        ]


def test_req_ref_018_ciclo_upgrade_downgrade_upgrade_completo_y_operativo() -> None:
    """REQ-REF-018 (escenario «Migration round trip»): tras el re-upgrade el
    esquema queda completo (tabla + constraints + trigger + función) y
    operativo (inserta y audita); la tabla no recrea las filas del ciclo
    anterior."""
    with esquema_en("0029"):
        alembic("upgrade", "0030")
        _sembrar_linea()
        alembic("downgrade", "0029")
        assert not _existe_tabla()
        alembic("upgrade", "0030")

        assert _rev() == "0030"
        assert _existe_tabla()
        assert _existe_fn("fn_auditar_referencia_materiales")
        assert sql(
            "SELECT count(*) FROM pg_constraint WHERE conname IN "
            "('pk_referencia_materiales','ck_referencia_cantidad_positiva',"
            "'fk_referencia_equipo','fk_referencia_material')"
        )[0][0] == 4
        assert sql(
            "SELECT tgenabled FROM pg_trigger "
            "WHERE tgname = 'tg_auditar_referencia_materiales'"
        ) == [("O",)]
        # La tabla vuelve vacía (el downgrade no preserva las filas).
        assert sql("SELECT count(*) FROM referencia_materiales")[0][0] == 0

        # Operativa: insertar una línea dispara el evento de auditoría. El
        # evento del primer ciclo sobrevivió al round trip (append-only), así
        # que ahora hay dos: el antiguo y el de la línea recién insertada.
        eq, mat = _sembrar_linea("2.500", sufijo="-2")
        assert sql(
            "SELECT cantidad_semanal FROM referencia_materiales "
            "WHERE equipo_id = %s AND material_id = %s",
            (eq, mat),
        ) == [(Decimal("2.500"),)]
        assert len(_evento_creada()) == 2
        assert int(
            sql(
                "SELECT detalles->>'equipo_id' FROM auditoria_eventos "
                "WHERE tipo_accion = 'REFERENCIA_LINEA_CREADA' ORDER BY id DESC LIMIT 1"
            )[0][0]
        ) == eq


def test_req_ref_018_downgrade_preserva_eventos_ya_escritos() -> None:
    """REQ-REF-018 (plan §3.1, ledger append-only): el downgrade elimina la
    tabla y la configuración almacenada, pero el evento
    REFERENCIA_LINEA_CREADA ya escrito permanece idéntico en
    `auditoria_eventos` (REQ-REF-012: el evento es inmutable y conserva
    valores)."""
    with esquema_en("0029"):
        alembic("upgrade", "0030")
        eq, mat = _sembrar_linea("7.000")
        antes = _evento_creada()
        assert len(antes) == 1
        assert antes[0][1] == mat
        assert antes[0][2] == "EXITO"
        det = antes[0][3]
        assert det["modulo"] == "REFERENCIA" and det["accion"] == "CREAR"
        assert det["equipo_id"] == eq
        assert det["valores_anteriores"] is None
        assert Decimal(str(det["valores_nuevos"]["cantidad_semanal"])) == Decimal(
            "7.000"
        )

        alembic("downgrade", "0029")
        assert not _existe_tabla()
        assert _evento_creada() == antes  # el evento sobrevive idéntico

        # El re-upgrade no recrea las filas ni duplica eventos.
        alembic("upgrade", "0030")
        assert sql("SELECT count(*) FROM referencia_materiales")[0][0] == 0
        assert _evento_creada() == antes
