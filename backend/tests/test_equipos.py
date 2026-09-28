"""CRUD de equipos e integrantes vía API — DMS - TELECOM.

Incluye el contrato autónomo del inventario del equipo
(REQ-DOMAIN-001/002): el equipo nace con inventario VACÍO ([] en 200) y solo
registra stock físico originado en movimientos TEAMS auditados.
"""

from httpx import AsyncClient

from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    procesar,
)


async def test_crear_equipo_con_integrantes(client: AsyncClient) -> None:
    equipo = await crear_equipo(
        client, nombre="Brigada Norte", integrantes=["juan", "ana"]
    )
    assert equipo["equipo_id"] >= 1
    assert equipo["is_active"] is True
    assert set(equipo["integrantes"]) == {"juan", "ana"}


async def test_obtener_y_listar(client: AsyncClient) -> None:
    equipo = await crear_equipo(client, nombre="Cuadrilla A")
    resp = await client.get(f"/api/v1/equipos/{equipo['equipo_id']}")
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Cuadrilla A"

    resp = await client.get("/api/v1/equipos")
    assert resp.status_code == 200
    nombres = {e["nombre"] for e in resp.json()}
    assert "Cuadrilla A" in nombres


async def test_obtener_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/equipos/9999")
    assert resp.status_code == 404


async def test_patch_nombre_e_integrantes(client: AsyncClient) -> None:
    equipo = await crear_equipo(client, nombre="Cuadrilla B")
    resp = await client.patch(
        f"/api/v1/equipos/{equipo['equipo_id']}",
        json={"nombre": "Cuadrilla B+", "integrantes": ["pedro"]},
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Cuadrilla B+"
    assert resp.json()["integrantes"] == ["pedro"]


async def test_delete_soft_delete(client: AsyncClient) -> None:
    equipo = await crear_equipo(client, nombre="Cuadrilla C")
    resp = await client.delete(f"/api/v1/equipos/{equipo['equipo_id']}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/equipos/{equipo['equipo_id']}")
    assert resp.status_code == 404


async def test_equipo_nuevo_inventario_vacio_200(client: AsyncClient) -> None:
    """REQ-DOMAIN-001/002: el equipo nuevo devuelve [] (200) en su inventario
    autónomo — cero herencia del catálogo global."""
    await crear_material(client, descripcion="Material del catálogo global")
    equipo = await crear_equipo(client, nombre="Equipo Autónomo Nuevo")

    resp = await client.get(f"/api/v1/equipos/{equipo['equipo_id']}/inventario")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_inventario_tras_teams_con_trazabilidad(
    client: AsyncClient,
) -> None:
    """REQ-DOMAIN-002: tras un TEAMS auditado la fila aparece con
    `ultimo_movimiento_id` = movimiento de origen."""
    material = await crear_material(client, descripcion="Material TEAMS EQ")
    equipo = await crear_equipo(client, nombre="Equipo Trazado")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=50
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=20,
    )
    await procesar(client, b["id"])

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 20
    assert filas[material["id_lista"]]["ultimo_movimiento_id"] == b["id"]


async def test_inventario_equipo_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/equipos/9999/inventario")
    assert resp.status_code == 404


async def test_REQ_VIEW_001_consulta_inventario_solo_lectura_aislada(
    client: AsyncClient, client_factory
) -> None:
    """REQ-VIEW-001: vista dedicada de consulta segura del inventario del
    equipo — GET puro (sin flujo de edición) y aislada por integrante
    (SEC-003): un actor que no es integrante ni administrador recibe 403."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    equipo = await crear_equipo(client, nombre="Equipo Consulta Segura")

    resp = await client.get(f"/api/v1/equipos/{equipo['equipo_id']}/inventario")
    assert resp.status_code == 200

    extrano = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Actor": "extrano"},
    )
    try:
        resp = await extrano.get(
            f"/api/v1/equipos/{equipo['equipo_id']}/inventario"
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    finally:
        await extrano.aclose()
