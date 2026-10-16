"""Migración 0027 (Inventario FO unificado + Valor Unitario + Valor Total)
— pruebas IN-PLACE sobre `p2_test` (véase tests/helpers/migraciones.py:
el rol de QA no posee CREATEDB; cada prueba degrada p2_test, siembra en la
revisión objetivo y restaura SIEMPRE la cabeza en `finally`).

Cubre RF-1 (fusión FO con una fila por material y evento FO_UNIFICADO),
RF-3 (default 1.000 en el catálogo existente), RF-7 (ledger inmutable:
conteo y contenido de eventos previos) y E14 (downgrade que ABORTA con
stock fraccionario, sin pérdida silenciosa; downgrade limpio con enteros y
re-upgrade sin pérdida de cantidad).
"""

from decimal import Decimal

from tests.helpers.migraciones import alembic, esquema_en, sql


def _audit_rows_antes() -> list[tuple]:
    """Snapshot de identidad (contenido íntegro) de los eventos previos."""
    return sql(
        "SELECT id, usuario, tipo_accion, material_id, equipo_origen_id, "
        "equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, "
        "resultado, detalles::text, created_at::text FROM auditoria_eventos "
        "ORDER BY id"
    )


def _audit_rows_despues() -> list[tuple]:
    return sql(
        "SELECT id, usuario, tipo_accion, material_id, equipo_origen_id, "
        "equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, "
        "resultado, detalles::text, created_at::text FROM auditoria_eventos "
        "ORDER BY id"
    )


def test_RF_001_007_fusion_fo_unificado_y_ledger_intacto() -> None:
    """RF-1/RF-3/RF-7: sobre una BD sembrada en 0026, la migración a 0027
    suma las particiones PAQUETE+EN_USO en UNA fila por material (sin
    pérdida ni creación de cantidad), emite un evento FO_UNIFICADO por
    material fusionado, asigna valor_unitario 1.000 a todo el catálogo
    existente y conserva íntegros (conteo Y contenido) los eventos previos
    del ledger."""
    with esquema_en("0026"):
        # Siembra 0026: catálogo, particiones FO legacy y ledger previo.
        m1 = sql(
            "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
            "VALUES ('F1','Fibra uno','PZ') RETURNING id_lista"
        )[0][0]
        m2 = sql(
            "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
            "VALUES ('F2','Fibra dos','PZ') RETURNING id_lista"
        )[0][0]
        # Material con ambas particiones (E6) y material con una sola (E7).
        sql(
            "INSERT INTO inventario_fibra (modulo, material_id, stock_actual) "
            "VALUES ('PAQUETE', %s, 10), ('EN_USO', %s, 5), ('PAQUETE', %s, 7)",
            (m1, m1, m2),
        )
        # Ledger previo con identidad numérica: tres eventos históricos.
        sql(
            "INSERT INTO auditoria_eventos "
            "(usuario, tipo_accion, material_id, cantidad, resultado, detalles) "
            "VALUES "
            "('hist','AJUSTE_INVENTARIO_FO',%s,10,'EXITO',"
            " '{\"modulo\":\"PAQUETE\",\"stock_nuevo\":10}'),"
            "('hist','AJUSTE_INVENTARIO_FO',%s,5,'EXITO',"
            " '{\"modulo\":\"EN_USO\",\"stock_nuevo\":5}'),"
            "('hist','STOCK_INICIAL_FO',%s,3,'EXITO',"
            " '{\"modulo\":\"PAQUETE\",\"motivo\":\"previo\"}')",
            (m1, m1, m2),
        )
        antes = _audit_rows_antes()
        assert len(antes) == 3

        alembic("upgrade", "0027")

        # RF-1: una sola fila por material; suma exacta (10+5=15; 7).
        filas = sql(
            "SELECT material_id, stock_actual FROM inventario_fibra "
            "ORDER BY material_id"
        )
        assert [(f[0], Decimal(f[1])) for f in filas] == [
            (m1, Decimal("15.000")),
            (m2, Decimal("7.000")),
        ]
        # La columna modulo desapareció del esquema.
        cols = sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'inventario_fibra'"
        )
        assert all(c[0] != "modulo" for c in cols)

        # RF-1: evento FO_UNIFICADO por material fusionado (10, 5 y 15).
        eventos = sql(
            "SELECT material_id, cantidad, usuario, detalles FROM "
            "auditoria_eventos WHERE tipo_accion = 'FO_UNIFICADO' "
            "ORDER BY material_id"
        )
        assert [(e[0], Decimal(e[1]), e[2]) for e in eventos] == [
            (m1, Decimal("15.000"), "migracion-0027"),
            (m2, Decimal("7.000"), "migracion-0027"),
        ]
        det_m1 = eventos[0][3]
        assert det_m1["modulo"] == "Inventario FO"
        assert dict(det_m1["valores_anteriores"]) == {
            "PAQUETE": Decimal("10.000"),
            "EN_USO": Decimal("5.000"),
        }
        assert det_m1["valores_nuevos"] == {"stock_actual": Decimal("15.000")}

        # RF-3: default 1.000 en TODO el catálogo existente.
        valores = sql(
            "SELECT id_lista, valor_unitario FROM catalogo_materiales "
            "ORDER BY id_lista"
        )
        assert [(v[0], Decimal(v[1])) for v in valores] == [
            (m1, Decimal("1.000")),
            (m2, Decimal("1.000")),
        ]

        # RF-7: ledger inmutable — los eventos PREVIOS conservan identidad
        # de contenido (conteo y valores, incl. `cantidad` ahora NUMERIC).
        despues = [
            f
            for f in _audit_rows_despues()
            if f[2] != "FO_UNIFICADO"
        ]
        assert despues == antes

        # Sección de ruteo única FO insertada; legacy conservadas.
        secciones = sql(
            "SELECT nombre, tipo, is_active FROM secciones ORDER BY almacen_id"
        )
        assert any(
            s[0] == "Inventario FO" and s[1] == "FO" and s[2] is False
            for s in secciones
        )
        tipos = {s[1] for s in secciones}
        assert {"FO_PAQUETE", "FO_EN_USO"} <= tipos


def test_RF_E14_downgrade_aborta_con_fracciones_y_upgrade_limpio() -> None:
    """E14: con stock fraccionario, el downgrade a 0026 ABORTA con error
    explícito (cero pérdida silenciosa) y la BD queda intacta; tras sanear
    a enteros, el downgrade aplica (existencia total en PAQUETE) y un nuevo
    upgrade NO pierde cantidad."""
    with esquema_en("head"):
        # En la cabeza: material con stock fraccionario.
        m = sql(
            "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
            "VALUES ('FX','Fibra fraccional','PZ') RETURNING id_lista"
        )[0][0]
        sql(
            "INSERT INTO inventario_fibra (material_id, stock_actual) "
            "VALUES (%s, 1.5)",
            (m,),
        )

        # E14: downgrade ABORTA.
        r = alembic("downgrade", "0026", ok=False)
        assert r.returncode != 0
        assert "fraccionarios" in (r.stderr + r.stdout).lower()
        # Sin efectos: stock, esquema (sin modulo) y valor_unitario intactos.
        assert Decimal(sql("SELECT stock_actual FROM inventario_fibra")[0][0]) == Decimal("1.500")
        cols = sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'inventario_fibra'"
        )
        assert all(c[0] != "modulo" for c in cols)
        assert any(
            c[0] == "valor_unitario"
            for c in sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'catalogo_materiales'"
            )
        )

        # Saneo a entero → downgrade limpio a 0026.
        sql("UPDATE inventario_fibra SET stock_actual = 2")
        alembic("downgrade", "0026")

        # Esquema 0026: columna modulo restaurada y existencia en PAQUETE.
        filas = sql("SELECT modulo, stock_actual FROM inventario_fibra")
        assert [(f[0], f[1]) for f in filas] == [("PAQUETE", 2)]
        assert not any(
            c[0] == "valor_unitario"
            for c in sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'catalogo_materiales'"
            )
        )
        assert not any(
            s[0] == "Inventario FO"
            for s in sql("SELECT nombre FROM secciones")
        )

        # Re-upgrade: la cantidad se conserva SIN pérdida (cero pérdida).
        alembic("upgrade", "0027")
        filas = sql("SELECT material_id, stock_actual FROM inventario_fibra")
        assert [(f[0], Decimal(f[1])) for f in filas] == [
            (m, Decimal("2.000"))
        ]
        # El valor_unitario vuelve con default 1.000.
        assert Decimal(
            sql("SELECT valor_unitario FROM catalogo_materiales")[0][0]
        ) == Decimal("1.000")


def test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos() -> None:
    """E13 (RF-1/RF-7): reintentar la migración (`upgrade 0027` y
    `upgrade head` estando ya aplicada) es un NO-OP a nivel de Alembic: no
    duplica eventos FO_UNIFICADO, no vuelve a fusionar ni altera
    existencias, valor_unitario ni el conteo/contenido del ledger."""
    with esquema_en("0026"):
        m = sql(
            "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
            "VALUES ('R1','Fibra reintento','PZ') RETURNING id_lista"
        )[0][0]
        sql(
            "INSERT INTO inventario_fibra (modulo, material_id, stock_actual) "
            "VALUES ('PAQUETE', %s, 4), ('EN_USO', %s, 6)",
            (m, m),
        )
        alembic("upgrade", "0027")

        def _estado() -> tuple:
            return (
                [
                    (f[0], Decimal(f[1]))
                    for f in sql(
                        "SELECT material_id, stock_actual FROM inventario_fibra"
                    )
                ],
                sql(
                    "SELECT count(*) FROM auditoria_eventos "
                    "WHERE tipo_accion = 'FO_UNIFICADO'"
                )[0][0],
                _audit_rows_despues(),
                [
                    Decimal(v[0])
                    for v in sql("SELECT valor_unitario FROM catalogo_materiales")
                ],
                sql("SELECT version_num FROM alembic_version"),
            )

        primero = _estado()
        assert primero[0] == [(m, Decimal("10.000"))]
        assert primero[1] == 1  # un solo evento de fusión
        assert primero[4] == [("0027",)] or primero[4][0][0] >= "0027"

        # Reintentos: ambos terminan en éxito y no cambian NADA.
        alembic("upgrade", "0027")
        alembic("upgrade", "head")
        assert _estado() == primero


def _scopes(actor: str | None = None) -> list[tuple[str, str]]:
    """(actor_id, tipo de sección) de actor_almacen_scopes, ordenado."""
    filtro = "WHERE sc.actor_id = %s " if actor else ""
    return [
        (f[0], f[1])
        for f in sql(
            "SELECT sc.actor_id, s.tipo FROM actor_almacen_scopes sc "
            "JOIN secciones s ON s.almacen_id = sc.almacen_id "
            + filtro
            + "ORDER BY sc.actor_id, s.tipo",
            (actor,) if actor else None,
        )
    ]


def test_RF_009_D2_scopes_legacy_se_copian_a_la_seccion_fo_y_downgrade_los_retira() -> None:
    """D-2 (RF-9, dictamen @arq-reviewer/@sec-ops T7): la migración copia los
    scopes de FO_PAQUETE/FO_EN_USO a la sección FO (continuidad de permisos
    de perfiles operativos), sin otorgar nada a actores sin scope legacy,
    de forma idempotente, conservando los scopes legacy; y el downgrade
    retira los scopes copiados (no queda bloqueado por su propio upgrade)."""
    with esquema_en("0026"):
        ids = {
            t: sql("SELECT almacen_id FROM secciones WHERE tipo = %s", (t,))[0][0]
            for t in ("GENERAL", "FO_PAQUETE", "FO_EN_USO")
        }
        sql(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) VALUES "
            "('op-paquete', %s), ('op-en-uso', %s), ('op-ambos', %s), "
            "('op-ambos', %s), ('op-general', %s)",
            (
                ids["FO_PAQUETE"],
                ids["FO_EN_USO"],
                ids["FO_PAQUETE"],
                ids["FO_EN_USO"],
                ids["GENERAL"],
            ),
        )
        antes_legacy = _scopes()

        alembic("upgrade", "0027")
        despues = _scopes()
        # Copiados a FO: solo actores con scope legacy; uno por actor.
        fo = [a for a, t in despues if t == "FO"]
        assert fo == ["op-ambos", "op-en-uso", "op-paquete"]
        # Sin concesión a actores sin scope legacy.
        assert "op-general" not in fo
        # Los scopes legacy previos se conservan intactos.
        assert [x for x in despues if x[1] != "FO"] == antes_legacy

        # Idempotencia: reintentos no duplican ni cambian nada.
        alembic("upgrade", "0027")
        alembic("upgrade", "head")
        assert _scopes() == despues

        # Downgrade: retira los scopes FO copiados y NO aborta por ellos.
        alembic("downgrade", "0026")
        assert _scopes() == antes_legacy
        assert not any(
            s[0] == "Inventario FO" for s in sql("SELECT nombre FROM secciones")
        )
        alembic("upgrade", "0027")


def test_RF_009_D2_scope_concedido_directo_a_fo_sigue_bloqueando_el_downgrade() -> None:
    """D-2: un scope concedido DIRECTAMENTE a la sección FO (actor sin scope
    legacy) no es derivado de la migración: el downgrade lo respeta y
    ABORTA con error explícito (sin pérdida silenciosa de permisos)."""
    with esquema_en("head"):
        fo_id = sql("SELECT almacen_id FROM secciones WHERE tipo = 'FO'")[0][0]
        sql(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('op-directo-fo', %s)",
            (fo_id,),
        )
        r = alembic("downgrade", "0026", ok=False)
        assert r.returncode != 0
        assert "inventario fo" in (r.stderr + r.stdout).lower()
        assert _scopes("op-directo-fo") == [("op-directo-fo", "FO")]


def test_RF_009_D2_actor_con_scope_legacy_y_fo_directo_downgrade_conserva_legacy() -> None:
    """D-2, caso límite documentado: un actor con scope legacy Y scope FO
    concedido directamente pierde solo el scope FO en el downgrade (la
    sección FO no existe en 0026); su scope legacy —permiso efectivo previo
    a 0027— se conserva y el downgrade termina limpio."""
    with esquema_en("0026"):
        legacy = sql("SELECT almacen_id FROM secciones WHERE tipo = 'FO_EN_USO'")[0][0]
        sql(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('op-mixto', %s)",
            (legacy,),
        )
        alembic("upgrade", "0027")
        fo_id = sql("SELECT almacen_id FROM secciones WHERE tipo = 'FO'")[0][0]
        # El upgrade ya le copió FO; añade además un scope «directo» (no-op
        # por PK, pero documenta el caso): sigue habiendo exactamente uno.
        sql(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('op-mixto', %s) ON CONFLICT DO NOTHING",
            (fo_id,),
        )
        assert _scopes("op-mixto") == [("op-mixto", "FO"), ("op-mixto", "FO_EN_USO")]
        alembic("downgrade", "0026")
        assert _scopes("op-mixto") == [("op-mixto", "FO_EN_USO")]
        alembic("upgrade", "0027")
