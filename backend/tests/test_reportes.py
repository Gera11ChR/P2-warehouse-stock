"""Reportes oficiales — Acta de Entrega y Acta de Consumo (XLSX).

REQ-P2-REP-001..008 / REQ-P2-CON-005.

  * GET /api/v1/reportes/entrega  (hito A: TEAMS confirmado -> CONFIRMADO).
  * GET /api/v1/reportes/consumo  (hito B: cierre de seguimiento).
  * formato=json|normal|extenso; CSV legacy DESCARTADO.

Las actas son snapshots jsonb escritos por PostgreSQL en la transacción del
evento (trigger tg_acta_entrega / fn_cerrar_seguimiento); el XLSX se genera
bajo demanda inyectando datos sobre las plantillas corporativas.
"""

import io
import re
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

from app.services.plantilla_reporte import MEDIA_TYPE_XLSX
from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    procesar,
)


async def _entrega(
    client: AsyncClient,
    *,
    equipo_nombre: str = "Equipo Reportes",
    integrantes: list[str] | None = None,
    descripcion: str = "CABLE FIBRA OPTICA ADSS 12 HILOS",
    u_m: str = "METRO (M)",
    cantidad: int = 50,
) -> tuple[dict, dict, dict]:
    """TEAMS confirmado (Inventario General -> equipo): PostgreSQL registra
    el Acta de Entrega en la misma transacción de la confirmación."""
    material = await crear_material(
        client, descripcion=descripcion, u_m=u_m, nueva_categoria="Cables"
    )
    equipo = await crear_equipo(
        client, nombre=equipo_nombre, integrantes=integrantes
    )
    await carga_inicial(client, material_id=material["id_lista"], cantidad=200)
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=cantidad,
    )
    await procesar(client, borrador["id"])
    return material, equipo, borrador


async def _consumo(
    client: AsyncClient, material: dict, equipo: dict, *, tomada=20, sobrante=5
) -> dict:
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": tomada}]},
    )
    assert resp.status_code == 201, resp.text
    seguimiento = resp.json()
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/"
        f"{seguimiento['id']}/cerrar",
        json={
            "sobrantes": [
                {"material_id": material["id_lista"], "cantidad_sobrante": sobrante}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _xlsx(resp) -> object:
    assert resp.status_code == 200, resp.text
    return load_workbook(io.BytesIO(resp.content)).active


# ── Hito A: Acta de Entrega ────────────────────────────────────────────────


@pytest.mark.critical
async def test_REQ_P2_REP_003_confirmar_teams_registra_acta_de_entrega(
    client: AsyncClient,
) -> None:
    """Al confirmar TEAMS (estado CONFIRMADO) el acta queda registrada y
    consultable, con snapshot del equipo destino y las líneas entregadas."""
    material, equipo, borrador = await _entrega(client)

    resp = await client.get("/api/v1/reportes/entrega")
    assert resp.status_code == 200
    actas = resp.json()["actas"]
    assert len(actas) == 1
    acta = actas[0]
    assert acta["tipo"] == "ENTREGA"
    assert acta["movimiento_id"] == borrador["id"]
    assert acta["equipo_id"] == equipo["equipo_id"]
    assert acta["equipo_nombre"] == "Equipo Reportes"
    assert acta["usuario"] == "qa"
    item = acta["items"][0]
    assert item["material_id"] == material["id_lista"]
    assert item["descripcion"] == "CABLE FIBRA OPTICA ADSS 12 HILOS"
    assert item["u_m"] == "METRO (M)"
    assert item["categoria"] == "Cables"
    assert item["cantidad"] == 50


async def test_borrador_sin_confirmar_no_genera_acta(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Sin confirmar")
    equipo = await crear_equipo(client, nombre="Equipo Borrador")
    await carga_inicial(client, material_id=material["id_lista"], cantidad=10)
    await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=5,
    )
    resp = await client.get("/api/v1/reportes/entrega")
    assert resp.json()["actas"] == []


async def test_devol_no_genera_acta_de_entrega(client: AsyncClient) -> None:
    material, equipo, _ = await _entrega(client, cantidad=30)
    devol = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, devol["id"])
    actas = (await client.get("/api/v1/reportes/entrega")).json()["actas"]
    assert [a["tipo"] for a in actas] == ["ENTREGA"]  # solo la del TEAMS


@pytest.mark.critical
@pytest.mark.parametrize(
    "formato,titulo,primera_fila",
    [
        ("normal", "ACTA DE ENTREGA DE EQUIPOS Y MATERIALES", 10),
        ("extenso", "ACTA DE ENTREGA DE MATERIALES", 9),
    ],
)
async def test_REQ_P2_REP_002_entrega_xlsx_sobre_plantilla_corporativa(
    client: AsyncClient, formato: str, titulo: str, primera_fila: int
) -> None:
    await _entrega(client)

    resp = await client.get(f"/api/v1/reportes/entrega?formato={formato}")
    assert resp.headers["content-type"].startswith(MEDIA_TYPE_XLSX)
    disposicion = resp.headers["content-disposition"]
    assert re.fullmatch(
        rf'attachment; filename="acta-entrega-{formato}-\d{{4}}-\d{{2}}-\d{{2}}\.xlsx"',
        disposicion,
    )
    ws = _xlsx(resp)
    assert ws["A2"].value == titulo
    assert ws["A5"].value.startswith("FECHA: ")
    assert ws.cell(row=primera_fila, column=1).value == 50
    assert ws.cell(row=primera_fila, column=2).value == "CABLE FIBRA OPTICA ADSS 12 HILOS"
    assert ws.cell(row=primera_fila, column=5).value == "METRO (M)"
    assert len(ws._images) == 1  # logo corporativo conservado


async def test_entrega_xlsx_por_acta_individual(client: AsyncClient) -> None:
    await _entrega(client, equipo_nombre="Equipo Uno", descripcion="Material Uno")
    material2, _, _ = await _entrega(
        client, equipo_nombre="Equipo Dos", descripcion="Material Dos", cantidad=7
    )
    actas = (await client.get("/api/v1/reportes/entrega")).json()["actas"]
    assert len(actas) == 2
    segunda = next(a for a in actas if a["equipo_nombre"] == "Equipo Dos")

    ws = _xlsx(
        await client.get(
            f"/api/v1/reportes/entrega?formato=normal&acta_id={segunda['acta_id']}"
        )
    )
    assert ws["B10"].value == "Material Dos"
    assert ws["A10"].value == 7
    assert ws["B11"].value is None  # solo esa acta


# ── Hito B: Acta de Consumo ────────────────────────────────────────────────


@pytest.mark.critical
async def test_REQ_P2_CON_005_cerrar_seguimiento_genera_acta_de_consumo(
    client: AsyncClient,
) -> None:
    material, equipo, _ = await _entrega(client)
    await _consumo(client, material, equipo, tomada=20, sobrante=5)

    resp = await client.get("/api/v1/reportes/consumo")
    actas = resp.json()["actas"]
    assert len(actas) == 1
    acta = actas[0]
    assert acta["tipo"] == "CONSUMO"
    assert acta["equipo_id"] == equipo["equipo_id"]
    assert acta["seguimiento_id"] is not None
    item = acta["items"][0]
    # tomada, sobrante y consumida las calcula PostgreSQL (columna GENERATED).
    assert (item["cantidad_tomada"], item["cantidad_sobrante"]) == (20, 5)
    assert item["cantidad_consumida"] == 15


async def test_seguimiento_abierto_no_genera_acta_de_consumo(
    client: AsyncClient,
) -> None:
    material, equipo, _ = await _entrega(client)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": 10}]},
    )
    assert resp.status_code == 201
    assert (await client.get("/api/v1/reportes/consumo")).json()["actas"] == []


@pytest.mark.critical
@pytest.mark.parametrize(
    "formato,primera_fila", [("normal", 10), ("extenso", 9)]
)
async def test_REQ_P2_REP_004_consumo_xlsx_titulo_y_cantidad_consumida(
    client: AsyncClient, formato: str, primera_fila: int
) -> None:
    material, equipo, _ = await _entrega(client)
    await _consumo(client, material, equipo, tomada=20, sobrante=5)

    resp = await client.get(f"/api/v1/reportes/consumo?formato={formato}")
    assert re.fullmatch(
        rf'attachment; filename="acta-consumo-{formato}-[\d-]+\.xlsx"',
        resp.headers["content-disposition"],
    )
    ws = _xlsx(resp)
    assert ws["A2"].value == "ACTA DE CONSUMO"
    assert ws.cell(row=primera_fila, column=1).value == 15  # CANT. = consumida
    assert ws.cell(row=primera_fila, column=2).value == "CABLE FIBRA OPTICA ADSS 12 HILOS"
    assert len(ws._images) == 1


async def test_consumo_xlsx_omite_lineas_sin_consumo(client: AsyncClient) -> None:
    """Una línea devuelta completa (consumida = 0) no certifica consumo."""
    material, equipo, _ = await _entrega(client)
    await _consumo(client, material, equipo, tomada=20, sobrante=20)
    assert (await client.get("/api/v1/reportes/consumo")).json()["actas"]
    ws = _xlsx(await client.get("/api/v1/reportes/consumo?formato=normal"))
    assert ws["B10"].value is None


# ── Contrato: CSV descartado, ruta legacy eliminada, errores ───────────────


@pytest.mark.parametrize("ruta", ["entrega", "consumo"])
async def test_REQ_P2_REP_001_formato_csv_descartado(
    client: AsyncClient, ruta: str
) -> None:
    resp = await client.get(f"/api/v1/reportes/{ruta}?formato=csv")
    assert resp.status_code == 422


async def test_ruta_legacy_reportes_despliegues_eliminada(
    client: AsyncClient,
) -> None:
    assert (await client.get("/api/v1/reportes/despliegues")).status_code == 404
    assert (
        await client.get("/api/v1/reportes/despliegues?format=csv")
    ).status_code == 404


@pytest.mark.parametrize("ruta", ["entrega", "consumo"])
async def test_xlsx_sin_actas_devuelve_404(client: AsyncClient, ruta: str) -> None:
    resp = await client.get(f"/api/v1/reportes/{ruta}?formato=normal")
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "No hay actas para los filtros indicados"


# ── Aislamiento por equipo y filtros ───────────────────────────────────────


@pytest.mark.critical
async def test_aislamiento_actor_regular_solo_ve_sus_equipos(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    await _entrega(client, equipo_nombre="Equipo Propio")
    # El equipo ajeno lo opera el administrador (qa no es integrante).
    _, ajeno, _ = await _entrega(
        client_admin,
        equipo_nombre="Equipo Ajeno",
        integrantes=["otro"],
        descripcion="Ajeno",
    )

    propios = (await client.get("/api/v1/reportes/entrega")).json()["actas"]
    assert [a["equipo_nombre"] for a in propios] == ["Equipo Propio"]

    # Equipo ajeno explícito -> 403 (pertenencia exigida).
    resp = await client.get(f"/api/v1/reportes/entrega?equipo_id={ajeno['equipo_id']}")
    assert resp.status_code == 403
    # El XLSX tampoco filtra datos ajenos.
    ws = _xlsx(await client.get("/api/v1/reportes/entrega?formato=normal"))
    assert ws["B10"].value != "Ajeno"

    # El administrador ve todos los equipos.
    todos = (await client_admin.get("/api/v1/reportes/entrega")).json()["actas"]
    assert {a["equipo_nombre"] for a in todos} == {"Equipo Propio", "Equipo Ajeno"}


async def test_acta_id_de_equipo_ajeno_no_es_exportable(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """El aislamiento aplica también al exportar un acta por id: un actor
    regular no puede obtener (ni listar) el acta de un equipo ajeno."""
    await _entrega(client, equipo_nombre="Equipo Propio")
    await _entrega(
        client_admin,
        equipo_nombre="Equipo Ajeno",
        integrantes=["otro"],
        descripcion="Ajeno",
    )
    ajena = next(
        a
        for a in (await client_admin.get("/api/v1/reportes/entrega")).json()["actas"]
        if a["equipo_nombre"] == "Equipo Ajeno"
    )
    base = f"/api/v1/reportes/entrega?acta_id={ajena['acta_id']}"
    assert (await client.get(base)).json()["actas"] == []
    assert (await client.get(base + "&formato=normal")).status_code == 404
    # El administrador sí puede exportarla.
    ws = _xlsx(await client_admin.get(base + "&formato=normal"))
    assert ws["B10"].value == "Ajeno"


async def test_actor_sin_equipos_ve_reporte_vacio(
    client: AsyncClient, client_factory
) -> None:
    await _entrega(client)
    extraño = client_factory("extrano")
    try:
        resp = await extraño.get("/api/v1/reportes/consumo")
        assert resp.status_code == 200
        assert resp.json()["actas"] == []
        assert (await extraño.get("/api/v1/reportes/entrega")).json()["actas"] == []
    finally:
        await extraño.aclose()


async def test_filtros_equipo_y_rango_de_fechas(client: AsyncClient) -> None:
    _, e1, _ = await _entrega(client, equipo_nombre="Equipo A", descripcion="Mat A")
    _, e2, _ = await _entrega(client, equipo_nombre="Equipo B", descripcion="Mat B")

    solo_b = (
        await client.get(f"/api/v1/reportes/entrega?equipo_id={e2['equipo_id']}")
    ).json()["actas"]
    assert [a["equipo_nombre"] for a in solo_b] == ["Equipo B"]

    hoy = date.today()
    en_rango = (
        await client.get(
            f"/api/v1/reportes/entrega?desde={hoy.isoformat()}&hasta={hoy.isoformat()}"
        )
    ).json()["actas"]
    assert len(en_rango) == 2
    futuro = (
        await client.get(
            f"/api/v1/reportes/entrega?desde={(hoy + timedelta(days=1)).isoformat()}"
        )
    ).json()["actas"]
    assert futuro == []
    pasado = (
        await client.get(
            f"/api/v1/reportes/entrega?hasta={(hoy - timedelta(days=1)).isoformat()}"
        )
    ).json()["actas"]
    assert pasado == []
    assert e1["equipo_id"] != e2["equipo_id"]


async def test_documento_consolidado_concatena_lineas_sin_agregar(
    client: AsyncClient,
) -> None:
    """Varias actas en un mismo XLSX: las líneas se concatenan sin sumar ni
    recalcular cantidades (cero aritmética en Python)."""
    await _entrega(client, equipo_nombre="Equipo A", descripcion="Mat A", cantidad=3)
    await _entrega(client, equipo_nombre="Equipo B", descripcion="Mat B", cantidad=4)
    ws = _xlsx(await client.get("/api/v1/reportes/entrega?formato=normal"))
    filas = {
        (ws.cell(row=r, column=2).value, ws.cell(row=r, column=1).value)
        for r in (10, 11)
    }
    assert filas == {("Mat A", 3), ("Mat B", 4)}


async def test_REQ_P2_REP_001_cap_de_lineas_xlsx_422(
    client: AsyncClient, monkeypatch
) -> None:
    """B-1: el documento XLSX tiene un límite defensivo de líneas; al
    excederse responde 422 sin generar el workbook."""
    from app.services import reportes as reportes_svc

    # Un movimiento TEAMS con 3 líneas -> acta con 3 items.
    materiales = [
        await crear_material(client, descripcion=f"Cap linea {i}")
        for i in range(3)
    ]
    for m in materiales:
        await carga_inicial(client, material_id=m["id_lista"], cantidad=100)
    equipo = await crear_equipo(client, nombre="Equipo Cap")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": 1,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [
                {"material_id": m["id_lista"], "cantidad": 10}
                for m in materiales
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    await procesar(client, resp.json()["id"])

    monkeypatch.setattr(reportes_svc, "MAX_LINEAS_XLSX", 2)
    resp = await client.get("/api/v1/reportes/entrega?formato=normal")
    assert resp.status_code == 422, resp.text
    assert "límite de líneas" in resp.json()["error"]["message"]
    monkeypatch.undo()
    assert (await client.get("/api/v1/reportes/entrega?formato=normal")).status_code == 200


async def test_descripcion_maliciosa_no_se_escribe_como_formula(
    client: AsyncClient,
) -> None:
    await _entrega(client, descripcion="=cmd|' /C calc'!A0")
    ws = _xlsx(await client.get("/api/v1/reportes/entrega?formato=normal"))
    assert ws["B10"].data_type == "s"
    assert ws["B10"].value.startswith("'=")
