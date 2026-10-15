"""Transferencias multi-origen (paquete 2026-10-12-transferencias-multi-origen,
adaptado al Inventario FO unificado 0027).

Un movimiento TEAMS (TRANSF) puede combinar líneas de Inventario General y del
Inventario FO (sección de ruteo única 'FO'): cada línea conserva y valida su
sección de origen. Cubre RF-2..RF-14 (REQ-TRFM-002..014). El origen de cabecera
es NULL si el carrito es mixto. Los eventos ya no registran `modulo_fo` (RF-1).

La prueba de migración 0026 (REQ-TRFM-013) opera IN-PLACE sobre `p2_test`
(véase tests/helpers/migraciones.py: el rol de QA no tiene CREATEDB).
"""

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import ActaReporte, AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    fibra_carga_inicial,
    inventario_equipo,
    inventario_fo,
    procesar,
    seccion_fo,
)
from tests.helpers.migraciones import alembic, esquema_en, sql

GENERAL = 1


async def _escenario(client: AsyncClient, session) -> dict[str, Any]:
    """Material G (General 100), F (FO 50) y U (FO 30) + unidad."""
    fo = await seccion_fo(client)
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('qa', :i) ON CONFLICT DO NOTHING"
        ),
        {"i": fo["almacen_id"]},
    )
    await session.commit()
    g = await crear_material(client, descripcion="Mat General TRFM")
    f = await crear_material(client, descripcion="Mat FO TRFM")
    u = await crear_material(client, descripcion="Mat FO TRFM 2")
    await carga_inicial(client, material_id=g["id_lista"], cantidad=100)
    await fibra_carga_inicial(client, material_id=f["id_lista"], cantidad=50)
    await fibra_carga_inicial(client, material_id=u["id_lista"], cantidad=30)
    eq = await crear_equipo(client, nombre="Unidad TRFM")
    return {"g": g, "f": f, "u": u, "eq": eq, "fo": fo["almacen_id"]}


def _linea(m: dict, cant: int, origen: int | None = None) -> dict:
    d: dict[str, Any] = {"material_id": m["id_lista"], "cantidad": cant}
    if origen is not None:
        d["origen_almacen_id"] = origen
    return d


def _teams(eq: dict, detalle: list[dict], cabecera_origen: int | None = None) -> dict:
    p: dict[str, Any] = {
        "tipo_movimiento": "TEAMS",
        "destino_equipo_id": eq["equipo_id"],
        "detalle": detalle,
    }
    if cabecera_origen is not None:
        p["origen_almacen_id"] = cabecera_origen
    return p


async def _borrador(client: AsyncClient, payload: dict, expect: int = 201) -> dict:
    resp = await client.post("/api/v1/movimientos", json=payload)
    assert resp.status_code == expect, resp.text
    return dict(resp.json())


async def _mixto(client: AsyncClient, e: dict) -> dict:
    return await _borrador(
        client,
        _teams(
            e["eq"],
            [
                _linea(e["g"], 10, GENERAL),
                _linea(e["f"], 20, e["fo"]),
                _linea(e["u"], 5, e["fo"]),
            ],
        ),
    )


async def _stock_g(client: AsyncClient, m: dict) -> int:
    filas = (await client.get(f"/api/v1/inventario/secciones/{GENERAL}")).json()
    return int({f["material_id"]: f["stock_actual"] for f in filas}[m["id_lista"]])


async def _stock_fo(client: AsyncClient, m: dict) -> int:
    filas = await inventario_fo(client)
    return int(filas[m["id_lista"]]["stock_actual"])


# ── RF-2/RF-4: borrador mixto, origen por línea, cabecera NULL ────────────


async def test_REQ_TRFM_002_004_borrador_mixto_201_cabecera_null(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _mixto(client, e)
    assert b["origen_almacen_id"] is None
    origenes = {d["material_id"]: d["origen_almacen_id"] for d in b["detalle"]}
    assert origenes == {
        e["g"]["id_lista"]: GENERAL,
        e["f"]["id_lista"]: e["fo"],
        e["u"]["id_lista"]: e["fo"],
    }


async def test_REQ_TRFM_004_homogeneo_conserva_origen_de_cabecera(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _borrador(
        client, _teams(e["eq"], [_linea(e["f"], 5, e["fo"])])
    )
    assert b["origen_almacen_id"] == e["fo"]
    assert b["detalle"][0]["origen_almacen_id"] == e["fo"]


# ── RF-3: compatibilidad con el payload legado ────────────────────────────


async def test_REQ_TRFM_003_payload_legado_hereda_origen_de_cabecera(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await borrador_teams(
        client, almacen_id=GENERAL, equipo_id=e["eq"]["equipo_id"],
        material_id=e["g"]["id_lista"], cantidad=7,
    )
    assert b["origen_almacen_id"] == GENERAL
    assert b["detalle"][0]["origen_almacen_id"] == GENERAL
    await procesar(client, b["id"])
    assert await _stock_g(client, e["g"]) == 93


# ── RF-5 / RF-14: validaciones 422 ────────────────────────────────────────


async def test_REQ_TRFM_005_linea_sin_origen_422(client, session) -> None:
    e = await _escenario(client, session)
    resp = await client.post(
        "/api/v1/movimientos",
        json=_teams(e["eq"], [_linea(e["g"], 1, GENERAL), _linea(e["f"], 1)]),
    )
    assert resp.status_code == 422


async def test_REQ_TRFM_005_origen_inexistente_422(client, session) -> None:
    e = await _escenario(client, session)
    resp = await client.post(
        "/api/v1/movimientos", json=_teams(e["eq"], [_linea(e["g"], 1, 9999)])
    )
    assert resp.status_code == 422


async def test_REQ_TRFM_005_general_inactiva_422(client, session) -> None:
    from sqlalchemy import text

    e = await _escenario(client, session)
    sid = (
        await session.execute(
            text(
                "INSERT INTO secciones (nombre, tipo, is_active) "
                "VALUES ('Gen inactiva TRFM','GENERAL',false) "
                "ON CONFLICT (nombre) DO UPDATE SET is_active = false RETURNING almacen_id"
            )
        )
    ).scalar_one()
    await session.commit()
    resp = await client.post(
        "/api/v1/movimientos", json=_teams(e["eq"], [_linea(e["g"], 1, sid)])
    )
    await session.execute(text("DELETE FROM secciones WHERE almacen_id = :i"), {"i": sid})
    await session.commit()
    assert resp.status_code == 422


async def test_REQ_TRFM_014_devol_con_origen_por_linea_422(client, session) -> None:
    e = await _escenario(client, session)
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": e["eq"]["equipo_id"],
            "destino_almacen_id": GENERAL,
            "detalle": [_linea(e["g"], 1, GENERAL)],
        },
    )
    assert resp.status_code == 422


# ── RF-6: scope por cada origen ───────────────────────────────────────────


async def test_REQ_TRFM_006_sin_scope_en_un_origen_403(client, session) -> None:
    from sqlalchemy import text

    e = await _escenario(client, session)
    await session.execute(
        text("DELETE FROM actor_almacen_scopes WHERE actor_id='qa' AND almacen_id=:i"),
        {"i": e["fo"]},
    )
    await session.commit()
    resp = await client.post(
        "/api/v1/movimientos",
        json=_teams(e["eq"], [_linea(e["g"], 1, GENERAL), _linea(e["u"], 1, e["fo"])]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    assert (await client.get("/api/v1/movimientos")).json()["movimientos"] == []


# ── RF-7/RF-10: confirmación mixta atómica + auditoría por línea ──────────


async def test_REQ_TRFM_007_010_procesar_mixto_200_descuenta_cada_origen(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _mixto(client, e)
    await procesar(client, b["id"])

    assert await _stock_g(client, e["g"]) == 90
    assert await _stock_fo(client, e["f"]) == 30
    assert await _stock_fo(client, e["u"]) == 25
    filas = await inventario_equipo(client, e["eq"]["equipo_id"])
    assert {
        m["id_lista"]: filas[m["id_lista"]]["stock_actual"]
        for m in (e["g"], e["f"], e["u"])
    } == {
        e["g"]["id_lista"]: 10,
        e["f"]["id_lista"]: 20,
        e["u"]["id_lista"]: 5,
    }

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().all()
    por_material = {
        ev.material_id: (
            ev.almacen_origen_id,
            (ev.detalles or {}).get("modulo_fo"),
            (ev.detalles or {}).get("stock_remanente_origen"),
        )
        for ev in eventos
    }
    # RF-1: el evento ya no registra modulo_fo; el FO unificado reporta el
    # remanente del material en la MISMA raíz para ambas líneas FO.
    assert por_material == {
        e["g"]["id_lista"]: (GENERAL, None, 90),
        e["f"]["id_lista"]: (e["fo"], None, 30),
        e["u"]["id_lista"]: (e["fo"], None, 25),
    }


async def test_REQ_TRFM_008_linea_insuficiente_400_rollback_total(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _borrador(
        client,
        _teams(e["eq"], [_linea(e["g"], 10, GENERAL), _linea(e["f"], 999, e["fo"])]),
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en Origen (Inventario FO)" in resp.json()["error"][
        "message"
    ]

    assert await _stock_g(client, e["g"]) == 100
    assert await _stock_fo(client, e["f"]) == 50
    assert await inventario_equipo(client, e["eq"]["equipo_id"]) == {}
    assert (await client.get(f"/api/v1/movimientos/{b['id']}")).json()["estado"] == "BORRADOR"
    assert (await session.execute(select(ActaReporte))).scalars().all() == []
    assert (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().all() == []


async def test_REQ_TRFM_008_linea_general_sin_stock_nombra_su_seccion(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _borrador(
        client,
        _teams(e["eq"], [_linea(e["g"], 999, GENERAL), _linea(e["f"], 1, e["fo"])]),
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}
    )
    assert resp.status_code == 400
    assert "Sección ID 1" in resp.json()["error"]["message"]


# ── RF-9: bloqueos en orden determinista ──────────────────────────────────


async def test_REQ_TRFM_009_confirmaciones_concurrentes_orden_inverso_sin_interbloqueo(
    client, client_factory, session
) -> None:
    e = await _escenario(client, session)
    ida = [_linea(e["g"], 1, GENERAL), _linea(e["f"], 1, e["fo"])]
    for _ in range(3):
        a = await _borrador(client, _teams(e["eq"], ida))
        b = await _borrador(client, _teams(e["eq"], list(reversed(ida))))
        c1, c2 = client_factory(), client_factory()
        try:
            r = await asyncio.gather(
                c1.post("/api/v1/movimientos/procesar", json={"movimiento_id": a["id"]}),
                c2.post("/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}),
            )
        finally:
            await c1.aclose()
            await c2.aclose()
        assert [x.status_code for x in r] == [200, 200], [x.text for x in r]
    assert await _stock_g(client, e["g"]) == 94
    assert await _stock_fo(client, e["f"]) == 44


# ── RF-11: un acta (folio único) por operación ────────────────────────────


async def test_REQ_TRFM_011_acta_unica_con_todas_las_lineas_y_origenes(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _mixto(client, e)
    await procesar(client, b["id"])

    actas = (
        await session.execute(
            select(ActaReporte).where(ActaReporte.tipo == "ENTREGA")
        )
    ).scalars().all()
    assert len(actas) == 1
    snap = actas[0].snapshot
    assert snap["origen"] is None
    assert {i["material_id"]: i["origen"]["almacen_id"] for i in snap["items"]} == {
        e["g"]["id_lista"]: GENERAL,
        e["f"]["id_lista"]: e["fo"],
        e["u"]["id_lista"]: e["fo"],
    }
    assert sorted(o["almacen_id"] for o in snap["origenes"]) == sorted(
        [GENERAL, e["fo"]]
    )

    resp = await client.get("/api/v1/reportes/entrega")
    assert resp.status_code == 200, resp.text
    api = resp.json()["actas"]
    assert len(api) == 1 and len(api[0]["items"]) == 3
    assert {i["origen_almacen_id"] for i in api[0]["items"]} == {GENERAL, e["fo"]}

    ev = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "ACTA_ENTREGA_GENERADA"
            )
        )
    ).scalars().one()
    assert ev.almacen_origen_id is None
    assert sorted((ev.detalles or {})["origen_almacen_ids"]) == sorted(
        [GENERAL, e["fo"]]
    )


# ── RF-12: cancelación restituye cada origen ──────────────────────────────


async def test_REQ_TRFM_012_cancelar_mixto_restituye_cada_origen(
    client, session
) -> None:
    e = await _escenario(client, session)
    b = await _mixto(client, e)
    await procesar(client, b["id"])
    resp = await client.post(
        f"/api/v1/movimientos/{b['id']}/cancelar", json={"motivo": "Prueba"}
    )
    assert resp.status_code == 200, resp.text

    assert await _stock_g(client, e["g"]) == 100
    assert await _stock_fo(client, e["f"]) == 50
    assert await _stock_fo(client, e["u"]) == 30
    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MOVIMIENTO_CANCELADO"
            )
        )
    ).scalars().all()
    assert {ev.material_id: ev.almacen_origen_id for ev in eventos} == {
        e["g"]["id_lista"]: GENERAL,
        e["f"]["id_lista"]: e["fo"],
        e["u"]["id_lista"]: e["fo"],
    }


# ── PATCH de borrador recalcula el origen de cabecera ─────────────────────


async def test_REQ_TRFM_004_patch_recalcula_cabecera(client, session) -> None:
    e = await _escenario(client, session)
    b = await _borrador(client, _teams(e["eq"], [_linea(e["g"], 1, GENERAL)]))
    assert b["origen_almacen_id"] == GENERAL
    resp = await client.patch(
        f"/api/v1/movimientos/{b['id']}",
        json={"detalle": [_linea(e["g"], 1, GENERAL), _linea(e["f"], 2, e["fo"])]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["origen_almacen_id"] is None
    resp = await client.patch(
        f"/api/v1/movimientos/{b['id']}",
        json={"detalle": [_linea(e["f"], 2, e["fo"])]},
    )
    assert resp.json()["origen_almacen_id"] == e["fo"]
    await procesar(client, b["id"])
    assert await _stock_fo(client, e["f"]) == 48


# ── RF-17: contrato ───────────────────────────────────────────────────────


async def test_REQ_TRFM_017_openapi_aditivo(client) -> None:
    comps = (await client.get("/openapi.json")).json()["components"]["schemas"]
    assert "origen_almacen_id" in comps["DetalleLine"]["properties"]
    assert "origen_almacen_id" in comps["DetalleOut"]["properties"]
    assert set(comps["ProcesarRequest"]["properties"]) == {"movimiento_id"}


# ── RF-13: migración 0026 con backfill (IN-PLACE sobre p2_test) ───────────
# p2admin (rol QA) carece de CREATEDB: la prueba degrada p2_test a 0025,
# siembra, sube a 0026 y valida el backfill y el ABORTO del downgrade con
# carrito mixto; `esquema_en` restaura SIEMPRE la cabeza (0027).


def test_REQ_TRFM_013_migracion_backfill_y_downgrade() -> None:
    with esquema_en("0025"):
        sql(
            "INSERT INTO secciones (nombre, tipo) VALUES ('Inventario General',"
            "'GENERAL') ON CONFLICT DO NOTHING"
        )
        gid = sql(
            "SELECT almacen_id FROM secciones WHERE tipo='GENERAL' LIMIT 1"
        )[0][0]
        m = sql(
            "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
            "VALUES ('MX','M','PZ') RETURNING id_lista"
        )[0][0]
        sql("INSERT INTO equipos (nombre) VALUES ('U')")
        eq = sql("SELECT equipo_id FROM equipos")[0][0]
        mv = sql(
            "INSERT INTO movimientos_cabecera (tipo_movimiento, estado, "
            "usuario, origen_almacen_id, destino_equipo_id) "
            "VALUES ('TEAMS','BORRADOR','qa',%s,%s) RETURNING id",
            (gid, eq),
        )[0][0]
        sql(
            "INSERT INTO movimientos_detalle (movimiento_id, material_id, "
            "cantidad) VALUES (%s,%s,3)",
            (mv, m),
        )
        alembic("upgrade", "0026")
        assert sql("SELECT origen_almacen_id FROM movimientos_detalle")[0][0] == gid
        # cabecera NULL (mixto) ahora permitida
        sql("UPDATE movimientos_cabecera SET origen_almacen_id = NULL")
        # downgrade con un movimiento mixto: aborta sin cambios
        r = alembic("downgrade", "0025", ok=False)
        assert r.returncode != 0 and "mixto" in (r.stderr + r.stdout).lower()
        sql("UPDATE movimientos_cabecera SET origen_almacen_id = %s", (gid,))
        alembic("downgrade", "0025")
        cols = [
            row[0]
            for row in sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='movimientos_detalle'"
            )
        ]
        assert "origen_almacen_id" not in cols
        alembic("upgrade", "0026")
