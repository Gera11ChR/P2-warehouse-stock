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
