"""Purga radical del legado Paquete / En Uso del dominio Fibra Óptica —
cambio 2026-10-purga-legacy-fo (T2, plan §1).

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-16

Migración DESTRUCTIVA, ATÓMICA y VERIFICADA (una sola transacción: ante
cualquier fallo, rollback total y la base queda en 0027 con ambos triggers
de inmutabilidad activos). Amparada por la enmienda constitucional acotada
E-1 (`openspec/changes/2026-10-purga-legacy-fo/spec.md` §3.1): dispensa
singular a §2.4/§6.2 limitada a la lista cerrada RF-1 (a)-(d), a esta
revisión y a las bases `p2` y `p2_test` (guardia técnica `_guardia_e1`).

upgrade() (plan §1.1; los números son los pasos del plan):

0a. Guardia E-1: con secciones legacy y `current_database()` fuera de
    {p2, p2_test} -> RuntimeError sin efectos.
0b. (adición de @dba-guard, aditiva) `lock_timeout` acotado y `LOCK TABLE`
    por adelantado, en orden fijo, de todas las tablas que la purga toca:
    ningún escritor concurrente puede alterar saldos/ledger entre la
    instantánea y las verificaciones (evita falsos abortos del paso 12(c)
    y carreras de bloqueo a mitad de la purga).
0.  Instantánea: saldos por fila de inventario_almacen / inventario_fibra /
    inventario_equipos, conteos, huella (md5 de la fila) de los eventos que
    NO se eliminan.
1.  DISABLE de `tg_ledger_auditoria_inmutable` (auditoria_eventos) y
    `tg_ledger_actas_inmutable` (actas_reportes). Transaccional: un
    rollback los restaura.
2.  Tablas temporales ON COMMIT DROP: _purga_secc, _purga_mov, _purga_acta.
3-8. Borrado en orden: eventos -> idempotencia (+ puntero
    inventario_equipos.ultimo_movimiento_id -> NULL) -> actas -> líneas ->
    cabeceras -> scopes -> guardia de saldos -> secciones legacy.
9.  `ck_secciones_tipo` -> ('GENERAL','FO').
10. fn_procesar_movimiento / fn_cancelar_movimiento republicadas: COPIA
    VERBATIM de FN_PROCESAR_NUEVA / FN_CANCELAR_NUEVA de 0027 (importadas
    en tiempo de carga; 0027 no se edita) con SOLO estas sustituciones
    exactas (se afirma el número de ocurrencias): los tres IN legacy ->
    `= 'FO'` y los comentarios que citaban el legado.
11. ENABLE de ambos triggers y UN evento `PURGA_LEGACY_FO`.
12. Verificaciones (a)-(g) + (d2); cada fallo -> RuntimeError (rollback).

Decisión de diseño (E7): si NO existen secciones legacy (base ya purgada,
p. ej. re-upgrade tras downgrade), la purga de datos NO se ejecuta (la
guardia E-1 no aplica sin datos legacy; un borrado por criterios JSON sin
guardia sería una purga de ledger fuera de E-1), no se emite evento y solo
se redefinen CHECK y funciones (idempotente).

downgrade(): SOLO ESQUEMA. Restablece `ck_secciones_tipo` ampliado y las
funciones con el cuerpo VERBATIM de 0027; no recrea filas ni aborta; no toca
los triggers de inmutabilidad. Los datos purgados solo se recuperan desde el
`pg_dump` previo (/tmp/opencode/p2_pre_0028.dump). Limitación documentada:
tras 0028 el downgrade de 0027 aborta si la sección `FO` tiene referencias
(su paso 1b).

Sin DROP/TRUNCATE de tablas, sin tocar permisos, roles ni secuencias.
"""

import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

# ================================================================
# Constantes de la migración
# ================================================================

BASES_PERMITIDAS = ("p2", "p2_test")
RUTA_DUMP = "/tmp/opencode/p2_pre_0028.dump"
LOCK_TIMEOUT = "30s"
TRIGGERS_LEDGER = (
    ("tg_ledger_auditoria_inmutable", "auditoria_eventos"),
    ("tg_ledger_actas_inmutable", "actas_reportes"),
)

# Orden fijo de bloqueo (SHARE ROW EXCLUSIVE: bloquea escritores, permite
# lecturas). `secciones` va aparte en ACCESS EXCLUSIVE (se le hace ALTER).
_TABLAS_LOCK = (
    "auditoria_eventos",
    "actas_reportes",
    "operaciones_idempotencia",
    "movimientos_cabecera",
    "movimientos_detalle",
    "actor_almacen_scopes",
    "inventario_almacen",
    "inventario_fibra",
    "inventario_equipos",
)

# Predicado cerrado de eventos a eliminar (spec RF-1 (a)-(d); plan §1.3).
# Alias obligatorio: `e`. Criterio por CLAVE JSON, jamás por texto.
_PRED_EVENTOS = """(
       e.almacen_origen_id  IN (SELECT almacen_id FROM _purga_secc)
    OR e.almacen_destino_id IN (SELECT almacen_id FROM _purga_secc)
    OR e.detalles::jsonb @? '$.**.modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
    OR e.detalles::jsonb @? '$.**.origen_modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
    OR e.detalles::jsonb @? '$.**.destino_modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
    OR e.tipo_accion = 'FO_UNIFICADO'
    OR (e.detalles::jsonb ->> 'movimiento_id') IN (SELECT id::text FROM _purga_mov)
    OR (e.detalles::jsonb ->> 'acta_id')       IN (SELECT id::text FROM _purga_acta)
)"""

_STOCK_ACTUAL = """
SELECT 'inventario_almacen'::text AS tabla, almacen_id AS k1, material_id AS k2, stock_actual
  FROM inventario_almacen
UNION ALL
SELECT 'inventario_fibra', material_id, 0, stock_actual FROM inventario_fibra
UNION ALL
SELECT 'inventario_equipos', equipo_id, material_id, stock_actual FROM inventario_equipos
"""

# ================================================================
# Funciones 0027 (fuente única, sin copias a mano) y su versión purgada
# ================================================================


def _cargar_0027() -> Any:
    ruta = Path(__file__).with_name("0027_fo_unificado_valor_unitario.py")
    spec = importlib.util.spec_from_file_location("_alembic_rev_0027_fuente", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_R0027 = _cargar_0027()
FN_PROCESAR_0027: str = _R0027.FN_PROCESAR_NUEVA
FN_CANCELAR_0027: str = _R0027.FN_CANCELAR_NUEVA


def _sustituir(texto: str, reemplazos: list[tuple[str, str, int]]) -> str:
    """Aplica sustituciones exactas afirmando cuántas ocurrencias hay: si la
    fuente de 0027 no coincide, la migración falla en import (jamás republica
    algo distinto a lo previsto)."""
    for viejo, nuevo, veces in reemplazos:
        n = texto.count(viejo)
        if n != veces:
            raise RuntimeError(
                f"0028: la fuente de 0027 difiere de lo previsto ({n} != {veces} "
                f"ocurrencias de {viejo!r})."
            )
        texto = texto.replace(viejo, nuevo)
    return texto


_IN_LEGACY = "IN ('FO','FO_PAQUETE','FO_EN_USO') THEN"

FN_PROCESAR_NUEVA_0028 = _sustituir(
    FN_PROCESAR_0027,
    [
        (
            "    -- Inventario General y de Fibra Óptica (secciones FO/FO_* = manejadores\n"
            "    -- de ruteo hacia el inventario_fibra unificado de 0027).\n",
            "    -- Inventario General y de Fibra Óptica (la sección FO enruta hacia el\n"
            "    -- inventario_fibra unificado).\n",
            1,
        ),
        (
            "            ELSIF v_origen_tipo " + _IN_LEGACY + "\n"
            "                -- Inventario FO unificado (0027): la sección 'FO' y los tipos\n"
            "                -- legacy FO_PAQUETE/FO_EN_USO enrutan al mismo inventario_fibra,\n"
            "                -- resuelto por material_id SIN modulo (RF-9).\n",
            "            ELSIF v_origen_tipo = 'FO' THEN\n"
            "                -- Inventario FO unificado: inventario_fibra se resuelve por\n"
            "                -- material_id.\n",
            1,
        ),
        (
            "            ELSIF v_destino_tipo " + _IN_LEGACY,
            "            ELSIF v_destino_tipo = 'FO' THEN",
            1,
        ),
    ],
)

FN_CANCELAR_NUEVA_0028 = _sustituir(
    FN_CANCELAR_0027,
    [
        (
            "            -- C. Sumar al origen de la línea (GENERAL -> inventario_almacen;\n"
            "            --    FO/FO_PAQUETE/FO_EN_USO -> inventario_fibra unificado, RF-9)\n",
            "            -- C. Sumar al origen de la línea (GENERAL -> inventario_almacen;\n"
            "            --    FO -> inventario_fibra unificado)\n",
            1,
        ),
        (
            "            ELSIF v_origen_tipo " + _IN_LEGACY,
            "            ELSIF v_origen_tipo = 'FO' THEN",
            1,
        ),
        (
            "            ELSIF v_destino_tipo " + _IN_LEGACY,
            "            ELSIF v_destino_tipo = 'FO' THEN",
            1,
        ),
    ],
)

# Aserción de import: ningún literal legacy en lo que se va a republicar.
for _fn in (FN_PROCESAR_NUEVA_0028, FN_CANCELAR_NUEVA_0028):
    if "FO_PAQUETE" in _fn or "FO_EN_USO" in _fn:
        raise RuntimeError("0028: la función republicada aún contiene literales legacy.")

# ================================================================
# Utilidades
# ================================================================


def _guardia_e1(bind_o_nombre_db: Any, n_dependientes: int) -> None:
    """Guardia técnica de E-1 (spec RF-6, plan §1.1 paso 0a).

    `n_dependientes` = filas que dependen del legado FO (movimientos,
    scopes, saldos de sección y eventos de ledger que cumplen RF-1). Si es
    > 0 y la base no es p2/p2_test lanza RuntimeError SIN efectos. Una base
    nueva (0010 siembra las secciones legacy, sin dependientes) pasa: la
    purga solo retira las dos secciones y no toca ningún ledger.
    Acepta un nombre de base (str) o una conexión/bind con `execute`.
    """
    if isinstance(bind_o_nombre_db, str):
        nombre = bind_o_nombre_db
    else:
        nombre = bind_o_nombre_db.execute(sa.text("SELECT current_database()")).scalar_one()
    if n_dependientes > 0 and nombre not in BASES_PERMITIDAS:
        raise RuntimeError(
            f"0028 abortada por la guardia E-1: la base {nombre!r} contiene "
            f"{n_dependientes} fila(s) que dependen del legado FO y la purga "
            f"solo está autorizada para {', '.join(BASES_PERMITIDAS)}. Sin efectos."
        )


def _scalar(bind: Any, query: str, **params: Any) -> Any:
    return bind.execute(sa.text(query), params).scalar_one()


def _run(bind: Any, query: str, **params: Any) -> int:
    """Ejecuta una sentencia y devuelve `rowcount`."""
    return bind.execute(sa.text(query), params).rowcount


def _estado_triggers(bind: Any) -> dict[str, str | None]:
    estado: dict[str, str | None] = {}
    for trg, tabla in TRIGGERS_LEDGER:
        filas = bind.execute(
            sa.text(
                "SELECT tgenabled FROM pg_trigger "
                "WHERE tgname = :t AND tgrelid = CAST(:r AS regclass) AND NOT tgisinternal"
            ),
            {"t": trg, "r": f"public.{tabla}"},
        ).fetchall()
        estado[trg] = filas[0][0] if len(filas) == 1 else None
    return estado


def _residuos(bind: Any, ids_purgados: list[int]) -> list[str]:
    """12(d2): barrido diagnóstico NO circular (no usa el predicado de borrado)
    sobre las filas supervivientes. Devuelve la lista de hallazgos."""
    hallazgos: list[str] = []
    fuentes = (
        ("auditoria_eventos", "detalles", "CAST(detalles AS jsonb)"),
        ("actas_reportes", "snapshot", "snapshot"),
        ("operaciones_idempotencia", "resultado", "resultado"),
    )
    for tabla, col, jexpr in fuentes:
        n = _scalar(
            bind,
            f"SELECT count(*) FROM {tabla} "
            f"WHERE CAST({col} AS text) LIKE '%FO\\_PAQUETE%' "
            f"   OR CAST({col} AS text) LIKE '%FO\\_EN\\_USO%'",
        )
        if n:
            hallazgos.append(f"{tabla}.{col}: {n} fila(s) con literal FO_PAQUETE/FO_EN_USO")
        for clave in ("almacen_id", "origen_almacen_id", "destino_almacen_id"):
            for sid in ids_purgados:
                n = _scalar(
                    bind,
                    f"SELECT count(*) FROM {tabla} "
                    f"WHERE jsonb_path_exists({jexpr}, "
                    f"'$.**.{clave} ? (@ == $id || @ == $ids)', "
                    f"jsonb_build_object('id', CAST(:i AS int), 'ids', CAST(:s AS text)))",
                    i=sid,
                    s=str(sid),
                )
                if n:
                    hallazgos.append(f"{tabla}.{col}: {n} fila(s) con {clave}={sid} (sección purgada)")
    return hallazgos


# ================================================================
# upgrade()
# ================================================================


def _redefinir_check_y_funciones(bind: Any) -> None:
    # Paso 9 — ck_secciones_tipo solo GENERAL/FO.
    op.execute(sa.text("ALTER TABLE secciones DROP CONSTRAINT ck_secciones_tipo"))
    op.execute(
        sa.text(
            "ALTER TABLE secciones ADD CONSTRAINT ck_secciones_tipo "
            "CHECK (tipo IN ('GENERAL','FO'))"
        )
    )
    # Paso 10 — misma firma que 0027 (CREATE OR REPLACE, sin DROP).
    op.execute(sa.text(FN_PROCESAR_NUEVA_0028))
    op.execute(sa.text(FN_CANCELAR_NUEVA_0028))


def upgrade() -> None:
    bind = op.get_bind()
    prev_lock_timeout = _scalar(bind, "SELECT current_setting('lock_timeout')")
    bind.execute(sa.text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))

    # ---- Paso 0a: guardia E-1 -------------------------------------
    n_legacy = _scalar(
        bind, "SELECT count(*) FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')"
    )

    if n_legacy == 0:
        # E7: sin datos legacy -> no-op de datos (ver docstring).
        _redefinir_check_y_funciones(bind)
        bind.execute(sa.text("SELECT set_config('lock_timeout', :p, true)"), {"p": prev_lock_timeout})
        _verificar_esquema(bind)
        return

    # ---- Paso 0b: bloqueo anticipado en orden fijo ----------------
    bind.execute(sa.text("LOCK TABLE secciones IN ACCESS EXCLUSIVE MODE"))
    bind.execute(
        sa.text("LOCK TABLE " + ", ".join(_TABLAS_LOCK) + " IN SHARE ROW EXCLUSIVE MODE")
    )

    # Guardia E-1 DESPUÉS de bloquear (sin TOCTOU): los conteos ya no pueden
    # cambiar por escritores concurrentes. Aborta con rollback (sin efectos).
    n_dependientes = _scalar(
        bind,
        """
SELECT
  (SELECT count(*) FROM movimientos_cabecera
    WHERE origen_almacen_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO'))
       OR destino_almacen_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')))
+ (SELECT count(*) FROM movimientos_detalle
    WHERE origen_almacen_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')))
+ (SELECT count(*) FROM actor_almacen_scopes
    WHERE almacen_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')))
+ (SELECT count(*) FROM inventario_almacen
    WHERE almacen_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')))
+ (SELECT count(*) FROM auditoria_eventos
    WHERE tipo_accion = 'FO_UNIFICADO'
       OR almacen_origen_id  IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO'))
       OR almacen_destino_id IN (SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO'))
       OR detalles::jsonb @? '$.**.modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
       OR detalles::jsonb @? '$.**.origen_modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
       OR detalles::jsonb @? '$.**.destino_modulo ? (@ == "PAQUETE" || @ == "EN_USO")')
+ (SELECT count(*) FROM operaciones_idempotencia
    WHERE resultado @? '$.modulo ? (@ == "PAQUETE" || @ == "EN_USO")')
""",
    )
    _guardia_e1(bind, n_dependientes)

    # ---- Paso 2 (previo a la instantánea): conjuntos de purga -----
    bind.execute(
        sa.text(
            "CREATE TEMP TABLE _purga_secc ON COMMIT DROP AS "
            "SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')"
        )
    )
    bind.execute(
        sa.text(
            """
CREATE TEMP TABLE _purga_mov ON COMMIT DROP AS
SELECT id FROM movimientos_cabecera
 WHERE origen_almacen_id  IN (SELECT almacen_id FROM _purga_secc)
    OR destino_almacen_id IN (SELECT almacen_id FROM _purga_secc)
UNION
SELECT movimiento_id FROM movimientos_detalle
 WHERE origen_almacen_id IN (SELECT almacen_id FROM _purga_secc)
"""
        )
    )
    bind.execute(
        sa.text(
            "CREATE TEMP TABLE _purga_acta ON COMMIT DROP AS "
            "SELECT id FROM actas_reportes WHERE movimiento_id IN (SELECT id FROM _purga_mov)"
        )
    )
    ids_purgados = [r[0] for r in bind.execute(sa.text("SELECT almacen_id FROM _purga_secc ORDER BY 1"))]
    n_mov = _scalar(bind, "SELECT count(*) FROM _purga_mov")
    n_acta = _scalar(bind, "SELECT count(*) FROM _purga_acta")

    # ---- Paso 0: instantánea previa -------------------------------
    bind.execute(
        sa.text("CREATE TEMP TABLE _purga_stock_antes ON COMMIT DROP AS " + _STOCK_ACTUAL)
    )
    antes = {
        t: _scalar(bind, f"SELECT count(*) FROM {t}")
        for t in (
            "auditoria_eventos",
            "actas_reportes",
            "operaciones_idempotencia",
            "movimientos_cabecera",
            "movimientos_detalle",
            "actor_almacen_scopes",
            "secciones",
        )
    }
    por_tipo = {
        r[0]: r[1]
        for r in bind.execute(
            sa.text(
                f"SELECT e.tipo_accion, count(*) FROM auditoria_eventos e "
                f"WHERE COALESCE({_PRED_EVENTOS}, FALSE) GROUP BY e.tipo_accion "
                f"ORDER BY e.tipo_accion"
            )
        )
    }
    bind.execute(
        sa.text(
            f"CREATE TEMP TABLE _purga_ev_cons ON COMMIT DROP AS "
            f"SELECT e.id, md5(e::text) AS h FROM auditoria_eventos e "
            f"WHERE NOT COALESCE({_PRED_EVENTOS}, FALSE)"
        )
    )

    # ---- Paso 1: DISABLE de ambos triggers de ledger --------------
    estado = _estado_triggers(bind)
    for trg, st in estado.items():
        if st != "O":
            raise RuntimeError(
                f"0028 abortada: el trigger {trg} no está habilitado (tgenabled={st!r}) "
                "antes de la purga; estado anómalo del ledger."
            )
    for trg, tabla in TRIGGERS_LEDGER:
        bind.execute(sa.text(f"ALTER TABLE {tabla} DISABLE TRIGGER {trg}"))

    # ---- Pasos 3-8: borrado en orden ------------------------------
    eliminados: dict[str, int] = {}
    eliminados["auditoria_eventos"] = _run(
        bind, f"DELETE FROM auditoria_eventos e WHERE {_PRED_EVENTOS}"
    )  # 3
    eliminados["operaciones_idempotencia"] = _run(
        bind,
        "DELETE FROM operaciones_idempotencia "
        "WHERE resultado @? '$.modulo ? (@ == \"PAQUETE\" || @ == \"EN_USO\")' "
        "   OR resultado ->> 'movimiento_id' IN (SELECT id::text FROM _purga_mov)",
    )  # 4
    eliminados["inventario_equipos.ultimo_movimiento_id_a_NULL"] = _run(
        bind,
        "UPDATE inventario_equipos SET ultimo_movimiento_id = NULL "
        "WHERE ultimo_movimiento_id IN (SELECT id FROM _purga_mov)",
    )  # 4 (puntero sin FK; no es saldo)
    eliminados["actas_reportes"] = _run(
        bind, "DELETE FROM actas_reportes WHERE id IN (SELECT id FROM _purga_acta)"
    )  # 5
    eliminados["movimientos_detalle"] = _run(
        bind, "DELETE FROM movimientos_detalle WHERE movimiento_id IN (SELECT id FROM _purga_mov)"
    )  # 6
    eliminados["movimientos_cabecera"] = _run(
        bind, "DELETE FROM movimientos_cabecera WHERE id IN (SELECT id FROM _purga_mov)"
    )  # 6
    eliminados["actor_almacen_scopes"] = _run(
        bind,
        "DELETE FROM actor_almacen_scopes WHERE almacen_id IN (SELECT almacen_id FROM _purga_secc)",
    )  # 7

    # Paso 8 — guardia de saldos: jamás se borran saldos.
    refs = _scalar(
        bind,
        "SELECT (SELECT count(*) FROM inventario_almacen WHERE almacen_id IN (SELECT almacen_id FROM _purga_secc))"
        " + (SELECT count(*) FROM movimientos_cabecera WHERE origen_almacen_id IN (SELECT almacen_id FROM _purga_secc)"
        "      OR destino_almacen_id IN (SELECT almacen_id FROM _purga_secc))"
        " + (SELECT count(*) FROM movimientos_detalle WHERE origen_almacen_id IN (SELECT almacen_id FROM _purga_secc))"
        " + (SELECT count(*) FROM actor_almacen_scopes WHERE almacen_id IN (SELECT almacen_id FROM _purga_secc))",
    )
    if refs:
        raise RuntimeError(
            f"0028 abortada: {refs} fila(s) (saldos/movimientos/scopes) aún referencian "
            "secciones legacy; la purga no borra saldos. Rollback total."
        )
    eliminados["secciones"] = _run(
        bind, "DELETE FROM secciones WHERE almacen_id IN (SELECT almacen_id FROM _purga_secc)"
    )  # 8

    # ---- Pasos 9-10 -----------------------------------------------
    _redefinir_check_y_funciones(bind)

    # ---- Paso 11: ENABLE + evento único ---------------------------
    for trg, tabla in TRIGGERS_LEDGER:
        bind.execute(sa.text(f"ALTER TABLE {tabla} ENABLE TRIGGER {trg}"))

    detalles = {
        "enmienda": "E-1",
        "migracion": "0028",
        "cambio": "2026-10-purga-legacy-fo",
        "base_datos": _scalar(bind, "SELECT current_database()"),
        "respaldo_pg_dump": RUTA_DUMP,
        "secciones_purgadas": ids_purgados,
        "eliminados_por_tabla": eliminados,
        "eliminados_por_tipo_accion": por_tipo,
    }
    bind.execute(
        sa.text(
            "INSERT INTO auditoria_eventos (usuario, tipo_accion, resultado, detalles) "
            "VALUES ('migracion-0028', 'PURGA_LEGACY_FO', 'EXITO', CAST(:d AS json))"
        ),
        {"d": json.dumps(detalles, ensure_ascii=False)},
    )

    bind.execute(sa.text("SELECT set_config('lock_timeout', :p, true)"), {"p": prev_lock_timeout})

    # ---- Paso 12: verificaciones (abortan con rollback total) -----
    # (a) cero filas legacy.
    for tabla, cond in (
        ("secciones", "tipo IN ('FO_PAQUETE','FO_EN_USO')"),
        (
            "movimientos_cabecera",
            "origen_almacen_id IN (SELECT almacen_id FROM _purga_secc) "
            "OR destino_almacen_id IN (SELECT almacen_id FROM _purga_secc)",
        ),
        ("movimientos_detalle", "origen_almacen_id IN (SELECT almacen_id FROM _purga_secc)"),
        ("actor_almacen_scopes", "almacen_id IN (SELECT almacen_id FROM _purga_secc)"),
        ("inventario_almacen", "almacen_id IN (SELECT almacen_id FROM _purga_secc)"),
    ):
        n = _scalar(bind, f"SELECT count(*) FROM {tabla} WHERE {cond}")
        if n:
            raise RuntimeError(f"0028 verificación (a) falló: {n} fila(s) legacy en {tabla}.")
    if _scalar(bind, "SELECT count(*) FROM movimientos_cabecera WHERE id IN (SELECT id FROM _purga_mov)"):
        raise RuntimeError("0028 verificación (a) falló: persisten movimientos purgados.")

    # (b) cero eventos que cumplan el predicado (no circular con (d2)).
    n = _scalar(
        bind, f"SELECT count(*) FROM auditoria_eventos e WHERE COALESCE({_PRED_EVENTOS}, FALSE)"
    )
    if n:
        raise RuntimeError(f"0028 verificación (b) falló: {n} evento(s) legacy persisten.")

    # (c) saldos idénticos fila a fila (⊇ SUM por material).
    n = _scalar(
        bind,
        f"SELECT count(*) FROM ("
        f"(SELECT * FROM _purga_stock_antes EXCEPT SELECT * FROM ({_STOCK_ACTUAL}) a) "
        f"UNION ALL "
        f"(SELECT * FROM ({_STOCK_ACTUAL}) b EXCEPT SELECT * FROM _purga_stock_antes)"
        f") d",
    )
    if n:
        raise RuntimeError(f"0028 verificación (c) falló: {n} diferencia(s) de saldo; rollback total.")

    # (d) conteo, identidad y contenido de eventos conservados.
    total_ev = _scalar(bind, "SELECT count(*) FROM auditoria_eventos")
    if total_ev != antes["auditoria_eventos"] - eliminados["auditoria_eventos"] + 1:
        raise RuntimeError(
            f"0028 verificación (d) falló: eventos {total_ev} != "
            f"{antes['auditoria_eventos']} - {eliminados['auditoria_eventos']} + 1."
        )
    n = _scalar(
        bind,
        "SELECT count(*) FROM _purga_ev_cons c LEFT JOIN auditoria_eventos e "
        "ON e.id = c.id AND md5(e::text) = c.h WHERE e.id IS NULL",
    )
    ajenos = _scalar(
        bind,
        "SELECT count(*) FROM auditoria_eventos WHERE id NOT IN (SELECT id FROM _purga_ev_cons)",
    )
    if n or ajenos != 1:
        raise RuntimeError(
            f"0028 verificación (d) falló: {n} evento(s) conservado(s) alterado(s)/perdido(s); "
            f"{ajenos} evento(s) nuevo(s) (esperado 1)."
        )
    if (
        eliminados["movimientos_cabecera"] != n_mov
        or eliminados["actas_reportes"] != n_acta
        or _scalar(bind, "SELECT count(*) FROM movimientos_cabecera") != antes["movimientos_cabecera"] - n_mov
    ):
        raise RuntimeError("0028 verificación (d) falló: conteo de movimientos/actas purgados inconsistente.")

    # (d2) barrido diagnóstico no circular sobre filas supervivientes.
    hallazgos = _residuos(bind, ids_purgados)
    if hallazgos:
        raise RuntimeError("0028 verificación (d2) falló: " + "; ".join(hallazgos))

    # (e)-(g) + estado de triggers.
    _verificar_esquema(bind)


def _verificar_esquema(bind: Any) -> None:
    # (e) ambos triggers habilitados ('O').
    for trg, st in _estado_triggers(bind).items():
        if st != "O":
            raise RuntimeError(f"0028 verificación (e) falló: trigger {trg} tgenabled={st!r} (esperado 'O').")

    # (f) ninguna función de `public` contiene literales legacy.
    cuales = [
        r[0]
        for r in bind.execute(
            sa.text(
                "SELECT p.proname FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace "
                "AND p.prokind = 'f' "
                "AND (pg_get_functiondef(p.oid) LIKE '%FO\\_PAQUETE%' "
                "  OR pg_get_functiondef(p.oid) LIKE '%FO\\_EN\\_USO%')"
            )
        )
    ]
    if cuales:
        raise RuntimeError(f"0028 verificación (f) falló: funciones con literales legacy: {cuales}.")

    # (g) ck_secciones_tipo enumera exactamente GENERAL/FO y ningún otro
    #     constraint/enum de la base enumera los valores legacy.
    defn = _scalar(
        bind,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ck_secciones_tipo' AND conrelid = 'secciones'::regclass",
    )
    if set(re.findall(r"'([^']+)'", defn)) != {"GENERAL", "FO"}:
        raise RuntimeError(f"0028 verificación (g) falló: ck_secciones_tipo = {defn}.")
    otros = _scalar(
        bind,
        "SELECT count(*) FROM pg_constraint WHERE pg_get_constraintdef(oid) LIKE '%FO\\_PAQUETE%' "
        "OR pg_get_constraintdef(oid) LIKE '%FO\\_EN\\_USO%'",
    ) + _scalar(
        bind,
        "SELECT count(*) FROM pg_enum WHERE enumlabel IN ('FO_PAQUETE','FO_EN_USO')",
    )
    if otros:
        raise RuntimeError(f"0028 verificación (g) falló: {otros} constraint(s)/enum(s) enumeran valores legacy.")


# ================================================================
# downgrade() — SOLO ESQUEMA (plan §1.4, D-4)
# ================================================================


def downgrade() -> None:
    """Restablece únicamente el esquema de 0027: CHECK ampliado y cuerpos
    verbatim de fn_procesar_movimiento / fn_cancelar_movimiento. No recrea
    secciones, movimientos, actas, scopes ni eventos; no aborta; no toca los
    triggers de inmutabilidad. Los datos purgados solo se recuperan desde el
    pg_dump previo."""
    op.execute(sa.text("ALTER TABLE secciones DROP CONSTRAINT ck_secciones_tipo"))
    op.execute(
        sa.text(
            "ALTER TABLE secciones ADD CONSTRAINT ck_secciones_tipo "
            "CHECK (tipo IN ('GENERAL','FO','FO_PAQUETE','FO_EN_USO'))"
        )
    )
    op.execute(sa.text(FN_PROCESAR_0027))
    op.execute(sa.text(FN_CANCELAR_0027))
    op.execute(
        sa.text(
            "DO $$ BEGIN RAISE NOTICE "
            "'esquema restaurado; los datos purgados no se restauran (usar pg_dump)'; END $$"
        )
    )
    # El NOTICE del servidor no llega a la salida de Alembic: se replica en
    # el log del cliente para que el operador lo vea.
    logging.getLogger("alembic.runtime.migration").warning(
        "0028 downgrade: esquema restaurado; los datos purgados no se "
        "restauran (usar el pg_dump previo)."
    )
