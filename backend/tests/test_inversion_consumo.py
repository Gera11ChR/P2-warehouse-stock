"""Inversión de la lógica de consumo (paquete 2026-10-12-inversion-consumo).

El cierre de un seguimiento recibe lo CONSUMIDO (`consumidos`) y el sistema
lo descuenta directamente del inventario de la unidad. Cubre RF-2..RF-13
(REQ-CONSUMO-002..013). El concepto "Sobrante" deja de existir.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.models import ActaReporte, AuditoriaEvento
from tests.conftest import ADMIN_DB_URL
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    procesar,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _unidad_con_stock(
    client: AsyncClient, *, stock: int = 50, materiales: int = 1
) -> tuple[list[dict], dict]:
    mats = []
    equipo = await crear_equipo(client, nombre="Unidad Consumo")
    for i in range(materiales):
        m = await crear_material(client, descripcion=f"Material consumo {i}")
        await carga_inicial(client, material_id=m["id_lista"], cantidad=200)
        b = await borrador_teams(
            client,
            almacen_id=1,
            equipo_id=equipo["equipo_id"],
            material_id=m["id_lista"],
            cantidad=stock,
        )
        await procesar(client, b["id"])
        mats.append(m)
    return mats, equipo


async def _abrir(client: AsyncClient, equipo: dict, items: list[tuple[dict, int]]) -> int:
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={
            "items": [
                {"material_id": m["id_lista"], "cantidad_tomada": t} for m, t in items
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


def _url(equipo: dict, sid: int) -> str:
    return f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{sid}/cerrar"


def _linea(m: dict, consumida: int) -> dict:
    return {"material_id": m["id_lista"], "cantidad_consumida": consumida}


async def _stock(client: AsyncClient, equipo: dict, m: dict) -> int:
    filas = await inventario_equipo(client, equipo["equipo_id"])
    return int(filas[m["id_lista"]]["stock_actual"]) if m["id_lista"] in filas else 0


async def _estado(client: AsyncClient, equipo: dict, sid: int) -> dict:
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{sid}"
    )
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


# ── RF-2: descuento directo del consumido ─────────────────────────────────


async def test_REQ_CONSUMO_002_cierre_descuenta_exactamente_lo_consumido(
    client: AsyncClient,
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 15)]})
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["cantidad_consumida"] == 15
    assert "cantidad_sobrante" not in item
    assert resp.json()["estado"] == "CERRADA"
    # 50 - 15 = 35; el remanente (5) NO se suma ni se mueve.
    assert await _stock(client, equipo, m) == 35


async def test_REQ_CONSUMO_002_consumido_cero_no_descuenta_y_cierra(
    client: AsyncClient,
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 0)]})
    assert resp.status_code == 200, resp.text
    assert await _stock(client, equipo, m) == 50


async def test_REQ_CONSUMO_002_consumido_igual_a_tomada(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 20)]})
    assert resp.status_code == 200, resp.text
    assert await _stock(client, equipo, m) == 30


# ── RF-3: contrato del DTO ────────────────────────────────────────────────


async def test_REQ_CONSUMO_003_payload_sobrantes_rechazado_422(
    client: AsyncClient, session
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(
        _url(equipo, sid),
        json={"sobrantes": [{"material_id": m["id_lista"], "cantidad_sobrante": 5}]},
    )
    assert resp.status_code == 422
    assert await _stock(client, equipo, m) == 50
    assert (await _estado(client, equipo, sid))["estado"] == "ABIERTA"


async def test_REQ_CONSUMO_003_campo_extra_en_linea_rechazado_422(
    client: AsyncClient,
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(
        _url(equipo, sid),
        json={"consumidos": [{**_linea(m, 5), "cantidad_sobrante": 1}]},
    )
    assert resp.status_code == 422


# ── RF-4: líneas obligatorias ─────────────────────────────────────────────


async def test_REQ_CONSUMO_004_cuerpo_sin_consumidos_422(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={})
    assert resp.status_code == 422
    assert await _stock(client, equipo, m) == 50


async def test_REQ_CONSUMO_004_lista_vacia_422(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": []})
    assert resp.status_code == 422
    assert (await _estado(client, equipo, sid))["estado"] == "ABIERTA"


async def test_REQ_CONSUMO_004_falta_una_linea_422_sin_tocar_inventario(
    client: AsyncClient,
) -> None:
    (m1, m2), equipo = await _unidad_con_stock(client, stock=50, materiales=2)
    sid = await _abrir(client, equipo, [(m1, 10), (m2, 10)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m1, 4)]})
    assert resp.status_code == 422
    assert "Falta la cantidad consumida" in resp.json()["error"]["message"]
    assert await _stock(client, equipo, m1) == 50
    assert await _stock(client, equipo, m2) == 50
    estado = await _estado(client, equipo, sid)
    assert estado["estado"] == "ABIERTA"
    assert all(i["cantidad_consumida"] is None for i in estado["items"])


# ── RF-5: validaciones por línea ──────────────────────────────────────────


async def test_REQ_CONSUMO_005_negativo_422(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, -1)]})
    assert resp.status_code == 422
    assert await _stock(client, equipo, m) == 50


async def test_REQ_CONSUMO_005_duplicado_422(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(
        _url(equipo, sid), json={"consumidos": [_linea(m, 2), _linea(m, 3)]}
    )
    assert resp.status_code == 422
    assert await _stock(client, equipo, m) == 50


async def test_REQ_CONSUMO_005_mayor_que_tomada_400(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 21)]})
    assert resp.status_code == 400
    assert "Consumo inválido" in resp.json()["error"]["message"]
    assert await _stock(client, equipo, m) == 50
    assert (await _estado(client, equipo, sid))["estado"] == "ABIERTA"


async def test_REQ_CONSUMO_005_material_ajeno_400(client: AsyncClient) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    ajeno = await crear_material(client, descripcion="Material ajeno consumo")
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(
        _url(equipo, sid), json={"consumidos": [_linea(m, 1), _linea(ajeno, 1)]}
    )
    assert resp.status_code == 400
    assert "no pertenece a este seguimiento" in resp.json()["error"]["message"]
    assert await _stock(client, equipo, m) == 50


# ── RF-6: stock insuficiente ──────────────────────────────────────────────


async def test_REQ_CONSUMO_006_consumido_mayor_que_stock_400_rollback_total(
    client: AsyncClient,
) -> None:
    (m1, m2), equipo = await _unidad_con_stock(client, stock=30, materiales=2)
    sid = await _abrir(client, equipo, [(m1, 20), (m2, 20)])
    # Tras abrir, el stock baja por fuera del seguimiento (DEVOL de 25 de m2).
    from tests.helpers.fabrica import borrador_devol

    b = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=m2["id_lista"],
        cantidad=25,
    )
    await procesar(client, b["id"])
    resp = await client.post(
        _url(equipo, sid), json={"consumidos": [_linea(m1, 10), _linea(m2, 10)]}
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en la Unidad" in resp.json()["error"]["message"]
    assert await _stock(client, equipo, m1) == 30  # rollback total
    assert await _stock(client, equipo, m2) == 5
    assert (await _estado(client, equipo, sid))["estado"] == "ABIERTA"


# ── RF-7: la función recibe p_consumidos ──────────────────────────────────


async def test_REQ_CONSUMO_007_firma_de_fn_cerrar_seguimiento(session) -> None:
    firmas = (
        await session.execute(
            text(
                "SELECT pg_get_function_identity_arguments(p.oid) FROM pg_proc p "
                "WHERE p.proname = 'fn_cerrar_seguimiento'"
            )
        )
    ).scalars().all()
    assert len(firmas) == 1
    assert "p_consumidos jsonb" in firmas[0]
    assert "p_sobrantes" not in firmas[0]


# ── RF-8: columna real, sin sobrante ──────────────────────────────────────


async def test_REQ_CONSUMO_008_esquema_seguimiento_items(session) -> None:
    cols = {
        r[0]: (r[1], r[2])
        for r in (
            await session.execute(
                text(
                    "SELECT column_name, is_generated, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'seguimiento_items'"
                )
            )
        ).all()
    }
    assert "cantidad_sobrante" not in cols
    assert cols["cantidad_consumida"][0] == "NEVER"  # columna real, no generada
    chk = (
        await session.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'seguimiento_items'::regclass AND contype = 'c'"
            )
        )
    ).scalars().all()
    assert "ck_seguimiento_items_consumida" in chk
    assert "ck_seguimiento_items_sobrante" not in chk


# ── RF-9: auditoría y acta sin sobrante ───────────────────────────────────


async def test_REQ_CONSUMO_009_evento_y_acta_nuevos_sin_clave_sobrante(
    client: AsyncClient, session
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    resp = await client.post(
        _url(equipo, sid),
        json={"consumidos": [_linea(m, 15)], "observaciones_cierre": "obs"},
    )
    assert resp.status_code == 200, resp.text

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "SEGUIMIENTO_CERRADO"
            )
        )
    ).scalars().one()
    assert evento.cantidad == 15
    det = evento.detalles or {}
    assert det["cantidad_tomada"] == 20
    assert det["cantidad_consumida"] == 15
    assert det["stock_remanente_equipo"] == 35
    assert det["observaciones_cierre"] == "obs"
    assert "cantidad_sobrante" not in det

    acta = (
        await session.execute(
            select(ActaReporte).where(ActaReporte.tipo == "CONSUMO")
        )
    ).scalars().one()
    item = acta.snapshot["items"][0]
    assert item["cantidad_tomada"] == 20 and item["cantidad_consumida"] == 15
    assert "cantidad_sobrante" not in item


# ── RF-10/RF-12: reportes ─────────────────────────────────────────────────


async def test_REQ_CONSUMO_012_reporte_consumo_sin_cantidad_sobrante(
    client: AsyncClient,
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 15)]})
    resp = await client.get("/api/v1/reportes/consumo")
    assert resp.status_code == 200, resp.text
    item = resp.json()["actas"][0]["items"][0]
    assert (item["cantidad_tomada"], item["cantidad_consumida"]) == (20, 15)
    assert "cantidad_sobrante" not in item


async def test_REQ_CONSUMO_010_acta_antigua_con_sobrante_sigue_consultable(
    client: AsyncClient, session
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    await client.post(_url(equipo, sid), json={"consumidos": [_linea(m, 15)]})
    # Acta histórica (formato previo) insertada tal cual: inmutable, con la clave antigua.
    vieja = (
        await session.execute(
            text(
                "INSERT INTO seguimientos (equipo_id, fecha, usuario, estado) "
                "VALUES (:e, CURRENT_DATE, 'qa', 'CERRADA') RETURNING id"
            ),
            {"e": equipo["equipo_id"]},
        )
    ).scalar_one()
    await session.execute(
        text(
            "INSERT INTO actas_reportes (tipo, seguimiento_id, snapshot) "
            "VALUES ('CONSUMO', :sid, CAST(:s AS JSONB))"
        ),
        {
            "sid": vieja,
            "s": '{"equipo_id": %d, "equipo_nombre": "Vieja", "items": [{"material_id": %d, '
            '"cantidad_tomada": 10, "cantidad_sobrante": 4, "cantidad_consumida": 6}]}'
            % (equipo["equipo_id"], m["id_lista"])
        },
    )
    await session.commit()
    resp = await client.get("/api/v1/reportes/consumo")
    assert resp.status_code == 200, resp.text
    actas = resp.json()["actas"]
    assert sorted(a["items"][0]["cantidad_consumida"] for a in actas) == [6, 15]
    assert all("cantidad_sobrante" not in a["items"][0] for a in actas)


# ── RF-13: segundo cierre ─────────────────────────────────────────────────


async def test_REQ_CONSUMO_013_segundo_cierre_409_sin_doble_descuento(
    client: AsyncClient,
) -> None:
    (m,), equipo = await _unidad_con_stock(client, stock=50)
    sid = await _abrir(client, equipo, [(m, 20)])
    body = {"consumidos": [_linea(m, 15)]}
    assert (await client.post(_url(equipo, sid), json=body)).status_code == 200
    resp = await client.post(_url(equipo, sid), json=body)
    assert resp.status_code == 409
    assert await _stock(client, equipo, m) == 35


async def test_REQ_CONSUMO_013_openapi_contrato_nuevo(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    comps = schema["components"]["schemas"]
    assert "SobranteLine" not in comps and "ConsumoLine" in comps
    req = comps["CerrarSeguimientoRequest"]
    assert "consumidos" in req["properties"] and "sobrantes" not in req["properties"]
    assert "consumidos" in req["required"]
    assert "cantidad_sobrante" not in comps["SeguimientoItemOut"]["properties"]
    assert "cantidad_sobrante" not in comps["ActaItemOut"]["properties"]


# ── RF-11: migración 0025 con backfill (BD aparte) ────────────────────────


def _alembic(url: str, *args: str) -> None:
    env = {**os.environ, "P2_DATABASE_URL": url}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr[-2000:]


def test_REQ_CONSUMO_011_migracion_backfill_y_downgrade() -> None:
    admin = make_url(ADMIN_DB_URL)
    nombre = "p2_mig_test"
    mig_psy = admin.set(database=nombre).render_as_string(hide_password=False)
    mig_sa = admin.set(
        drivername="postgresql+psycopg", database=nombre
    ).render_as_string(hide_password=False)
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {nombre}")
        c.execute(f"CREATE DATABASE {nombre}")
    try:
        _alembic(mig_sa, "upgrade", "0024")
        with psycopg.connect(mig_psy, autocommit=True) as c:
            c.execute("INSERT INTO categorias (nombre) VALUES ('c')")
            mat = c.execute(
                "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
                "VALUES ('M1','Mat','PZ') RETURNING id_lista"
            ).fetchone()[0]
            c.execute("INSERT INTO equipos (nombre) VALUES ('U')")
            eq = c.execute("SELECT equipo_id FROM equipos").fetchone()[0]
            c.execute(
                "INSERT INTO seguimientos (equipo_id, fecha, usuario, estado) "
                "VALUES (%s, CURRENT_DATE, 'qa', 'CERRADA')", (eq,)
            )
            s1 = c.execute("SELECT max(id) FROM seguimientos").fetchone()[0]
            c.execute(
                "INSERT INTO seguimiento_items (seguimiento_id, material_id, "
                "cantidad_tomada, cantidad_sobrante) VALUES (%s,%s,20,5)", (s1, mat)
            )
            m2 = c.execute(
                "INSERT INTO catalogo_materiales (codigo, descripcion, u_m) "
                "VALUES ('M2','Mat2','PZ') RETURNING id_lista"
            ).fetchone()[0]
            c.execute(
                "INSERT INTO seguimientos (equipo_id, fecha, usuario, estado) "
                "VALUES (%s, CURRENT_DATE, 'qa', 'ABIERTA')", (eq,)
            )
            s2 = c.execute("SELECT max(id) FROM seguimientos").fetchone()[0]
            c.execute(
                "INSERT INTO seguimiento_items (seguimiento_id, material_id, "
                "cantidad_tomada) VALUES (%s,%s,7)", (s2, m2)
            )
        _alembic(mig_sa, "upgrade", "0025")
        with psycopg.connect(mig_psy, autocommit=True) as c:
            filas = dict(
                c.execute(
                    "SELECT cantidad_tomada, cantidad_consumida FROM seguimiento_items"
                ).fetchall()
            )
            assert filas == {20: 15, 7: None}  # cerrado migrado; abierto NULL
        _alembic(mig_sa, "downgrade", "0024")
        with psycopg.connect(mig_psy, autocommit=True) as c:
            filas = {
                r[0]: (r[1], r[2])
                for r in c.execute(
                    "SELECT cantidad_tomada, cantidad_sobrante, cantidad_consumida "
                    "FROM seguimiento_items"
                ).fetchall()
            }
            assert filas == {20: (5, 15), 7: (None, None)}
        _alembic(mig_sa, "upgrade", "0025")
    finally:
        with psycopg.connect(ADMIN_DB_URL, autocommit=True) as c:
            c.execute(f"DROP DATABASE IF EXISTS {nombre} WITH (FORCE)")
