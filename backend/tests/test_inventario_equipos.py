"""Modelo Sparse (Invariante 2) — vista vw_inventario_equipo_completo,
filas vivas con stock 0 y secciones semilla del SDD."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Seccion
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    catalogo_equipo,
    crear_equipo,
    crear_material,
    procesar,
)


@pytest.mark.critical
async def test_sin_registro_fisico_stock_cero(
    client: AsyncClient,
) -> None:
    material = await crear_material(client, descripcion="Sparse 1")
    equipo = await crear_equipo(client, nombre="Equipo Sparse")

    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] in filas
    assert filas[material["id_lista"]]["stock_actual"] == 0
    assert filas[material["id_lista"]]["alerta_stock"] is False


async def test_con_stock_real(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Sparse 2")
    equipo = await crear_equipo(client, nombre="Equipo Sparse 2")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, b["id"])

    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 40


async def test_secciones_semilla_tres_activas(
    client: AsyncClient, session
) -> None:
    resp = await client.get("/api/v1/inventario/secciones")
    assert resp.status_code == 200
    secciones = resp.json()
    assert len(secciones) == 3
    assert {s["nombre"] for s in secciones} == {
        "Inventario General",
        "Fibra Optica - Paquete",
        "Fibra Optica - En Uso",
    }
    total = len((await session.execute(select(Seccion))).scalars().all())
    assert total == 3


async def test_stock_seccion_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/inventario/secciones/9999")
    assert resp.status_code == 404


async def test_alerta_stock_bandera(client: AsyncClient) -> None:
    material = await crear_material(
        client, descripcion="Sparse 3", stock_minimo=70
    )
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=(await crear_equipo(client, nombre="Eq A3"))["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, b["id"])

    resp = await client.get("/api/v1/inventario/secciones/1")
    fila = next(
        f for f in resp.json() if f["material_id"] == material["id_lista"]
    )
    assert fila["stock_actual"] == 60
    assert fila["alerta_stock"] is True
