"""CRUD de equipos e integrantes vía API — DMS - TELECOM."""

from httpx import AsyncClient

from tests.helpers.fabrica import crear_equipo


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
