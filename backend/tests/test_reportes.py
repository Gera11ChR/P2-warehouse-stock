"""Reportes de despliegues — REQ-REPORT-001/002.

GET /api/v1/reportes/despliegues: historial plano centrado exclusivamente
en la función DESPLIEGUE con catálogo resuelto (código, descripción,
categoría y U.M.), aislamiento por equipo visible del actor, filtros de
fecha y exportación CSV con sanitización anti-inyección de fórmulas.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    procesar,
)


async def _setup_reportes(
    client: AsyncClient, client_admin: AsyncClient
) -> tuple[dict, dict, dict, dict, dict, dict]:
    """Dos despliegues propios (uno CERRADO con sobrantes y uno ABIERTO) y
    un despliegue ajeno creado por el administrador en otro equipo."""
    m1 = await crear_material(
        client,
        descripcion="=cmd|calc",
        codigo="F1",
        u_m="METRO (M)",
        nueva_categoria="Redes",
    )
    m2 = await crear_material(
        client,
        descripcion="Patchcord QA",
        codigo="F2",
        u_m="PZ",
        nueva_categoria="Redes",
    )
    equipo = await crear_equipo(client, nombre="Equipo Reportes")
    await carga_inicial(client, material_id=m1["id_lista"], cantidad=100)
    await carga_inicial(client, material_id=m2["id_lista"], cantidad=100)
    b1 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=m1["id_lista"],
        cantidad=50,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=m2["id_lista"],
        cantidad=30,
    )
    await procesar(client, b2["id"])

    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues",
        json={
            "observaciones": " =2+2",
            "items": [
                {"material_id": m1["id_lista"], "cantidad_tomada": 20},
                {"material_id": m2["id_lista"], "cantidad_tomada": 10},
            ],
        },
    )
    d1 = resp.json()
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues/"
        f"{d1['id']}/cerrar",
        json={
            "sobrantes": [
                {"material_id": m1["id_lista"], "cantidad_sobrante": 5}
            ]
        },
    )
    assert resp.status_code == 200
    d1_cerrado = resp.json()

    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues",
        json={
            "items": [{"material_id": m1["id_lista"], "cantidad_tomada": 10}]
        },
    )
    d2 = resp.json()

    ajeno = await crear_equipo(
        client, nombre="Equipo Ajeno", integrantes=["otro"]
    )
    resp = await client_admin.post(
        f"/api/v1/equipos/{ajeno['equipo_id']}/despliegues",
        json={
            "items": [{"material_id": m2["id_lista"], "cantidad_tomada": 7}]
        },
    )
    assert resp.status_code == 201
    d_ajeno = resp.json()

    return m1, m2, equipo, ajeno, d1_cerrado, d_ajeno


@pytest.mark.critical
async def test_REQ_REPORT_001_json_contiene_despliegues_con_items_y_catalogo(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-001: el reporte JSON expone el historial DESPLIEGUE con
    equipo, estado, observaciones y líneas de material con catálogo
    resuelto (código, descripción, categoría y U.M.)."""
    m1, m2, equipo, _, d1, _ = await _setup_reportes(client, client_admin)

    resp = await client.get("/api/v1/reportes/despliegues")
    assert resp.status_code == 200
    propios = [
        d
        for d in resp.json()["despliegues"]
        if d["equipo_id"] == equipo["equipo_id"]
    ]
    assert len(propios) == 2

    cerrado = next(d for d in propios if d["estado"] == "CERRADA")
    assert cerrado["despliegue_id"] == d1["id"]
    assert cerrado["equipo_nombre"] == "Equipo Reportes"
    assert cerrado["observaciones"] == " =2+2"
    assert cerrado["closed_at"] is not None
    items = {i["material_id"]: i for i in cerrado["items"]}
    linea_m1 = items[m1["id_lista"]]
    assert linea_m1["codigo"] == "F1"
    assert linea_m1["descripcion"] == "=cmd|calc"
    assert linea_m1["categoria"] == "Redes"
    assert linea_m1["um"] == "METRO (M)"
    assert linea_m1["cantidad_tomada"] == 20
    assert linea_m1["cantidad_sobrante"] == 5
    assert linea_m1["cantidad_consumida"] == 15
    linea_m2 = items[m2["id_lista"]]
    assert linea_m2["cantidad_sobrante"] == 0
    assert linea_m2["cantidad_consumida"] == 10

    abierto = next(d for d in propios if d["estado"] == "ABIERTA")
    assert abierto["closed_at"] is None
    assert abierto["items"][0]["cantidad_sobrante"] is None


@pytest.mark.critical
async def test_REQ_REPORT_002_csv_headers_y_contenido(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-002: la exportación CSV devuelve 200 con media type
    text/csv, Content-Disposition attachment, cabecera canónica y los
    valores del reporte presentes en las celdas."""
    _, _, _, _, d1, _ = await _setup_reportes(client, client_admin)

    resp = await client.get(
        "/api/v1/reportes/despliegues", params={"format": "csv"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    assert "attachment" in disposition
    assert f"reporte-despliegues-{date.today().isoformat()}.csv" in disposition

    texto = resp.text
    lineas = texto.splitlines()
    assert lineas[0] == (
        "despliegue_id,equipo_id,equipo_nombre,fecha,estado,usuario,"
        "observaciones,material_id,codigo,descripcion,categoria,um,"
        "cantidad_tomada,cantidad_sobrante,cantidad_consumida,"
        "created_at,closed_at"
    )
    assert "Equipo Reportes" in texto
    assert "Patchcord QA" in texto
    assert str(d1["id"]) in texto


async def test_REQ_REPORT_002_csv_sanitizacion_formulas(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-002 + V5: las celdas cuyo texto inicia con =, +, - o @
    (incluso tras espacios líderes) se prefijan con comilla simple —
    neutralización OWASP CSV Injection probada con datos reales."""
    await _setup_reportes(client, client_admin)

    resp = await client.get(
        "/api/v1/reportes/despliegues", params={"format": "csv"}
    )
    assert resp.status_code == 200
    texto = resp.text

    # Descripción peligrosa sin espacios: "=cmd|calc" → "'=cmd|calc".
    assert "'=cmd|calc" in texto
    assert ",=cmd|calc" not in texto

    # Observaciones con espacio líder: " =2+2" → "' =2+2".
    assert "' =2+2" in texto
    assert ", =2+2" not in texto


async def test_REQ_REPORT_001_aislamiento_no_admin_solo_equipos_propios(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-001: el actor regular SIN equipo_id ve únicamente los
    despliegues de los equipos donde es integrante."""
    _, _, equipo, ajeno, _, _ = await _setup_reportes(client, client_admin)

    resp = await client.get("/api/v1/reportes/despliegues")
    assert resp.status_code == 200
    despliegues = resp.json()["despliegues"]
    assert despliegues
    assert all(d["equipo_id"] == equipo["equipo_id"] for d in despliegues)
    assert all(d["equipo_id"] != ajeno["equipo_id"] for d in despliegues)


async def test_REQ_REPORT_001_admin_ve_todos(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-001: el administrador visualiza los despliegues de TODOS
    los equipos sin restricción de membresía."""
    _, _, equipo, ajeno, _, _ = await _setup_reportes(client, client_admin)

    resp = await client_admin.get("/api/v1/reportes/despliegues")
    assert resp.status_code == 200
    equipos = {d["equipo_id"] for d in resp.json()["despliegues"]}
    assert equipo["equipo_id"] in equipos
    assert ajeno["equipo_id"] in equipos


async def test_REQ_REPORT_001_equipo_id_foraneo_403(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-001: pedir explícitamente el equipo de otro actor exige
    membresía → 403."""
    _, _, _, ajeno, _, _ = await _setup_reportes(client, client_admin)

    resp = await client.get(
        "/api/v1/reportes/despliegues",
        params={"equipo_id": ajeno["equipo_id"]},
    )
    assert resp.status_code == 403


async def test_REQ_REPORT_001_filtros_fechas(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-REPORT-001: los filtros desde/hasta se aplican sobre
    despliegues.fecha (rango inclusivo)."""
    _, _, equipo, _, _, _ = await _setup_reportes(client, client_admin)
    hoy = date.today().isoformat()
    ayer = (date.today() - timedelta(days=1)).isoformat()

    resp = await client.get(
        "/api/v1/reportes/despliegues", params={"desde": hoy, "hasta": hoy}
    )
    assert resp.status_code == 200
    assert len(resp.json()["despliegues"]) == 2

    resp = await client.get(
        "/api/v1/reportes/despliegues",
        params={"desde": "2000-01-01", "hasta": ayer},
    )
    assert resp.status_code == 200
    assert resp.json()["despliegues"] == []


async def test_REQ_REPORT_001_fecha_invalida_422(client: AsyncClient) -> None:
    """REQ-REPORT-001: una fecha mal formada viola el tipo de query param
    (date ISO) → 422."""
    resp = await client.get(
        "/api/v1/reportes/despliegues", params={"desde": "no-es-fecha"}
    )
    assert resp.status_code == 422
