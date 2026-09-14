"""Devoluciones DEVOL — éxito, bloqueo por falta de stock y multi-detalle."""

import pytest
from httpx import AsyncClient

from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    carga_inicial,
    catalogo_equipo,
    crear_equipo,
    crear_material,
    procesar,
    stock_seccion,
)


async def _equipo_con_stock(
    client: AsyncClient, *, cantidad: int
) -> tuple[dict, dict]:
    material = await crear_material(client, descripcion="Material DEVOL")
    equipo = await crear_equipo(client, nombre="Equipo DEVOL")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=cantidad
    )
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=cantidad,
    )
    await procesar(client, borrador["id"])
    return material, equipo


@pytest.mark.critical
async def test_devol_exitoso(client: AsyncClient) -> None:
    material, equipo = await _equipo_con_stock(client, cantidad=25)

    borrador = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=25,
    )
    resultado = await procesar(client, borrador["id"])
    assert resultado["estado"] == "CONFIRMADO"

    assert await stock_seccion(client, 1) == {material["id_lista"]: 25}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 0


@pytest.mark.critical
async def test_devol_bloqueado_por_falta_stock_400(
    client: AsyncClient,
) -> None:
    material, equipo = await _equipo_con_stock(client, cantidad=10)

    borrador = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=40,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": borrador["id"]},
    )
    assert resp.status_code == 400
    assert "stock suficiente" in resp.json()["error"]["message"]

    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 10
    assert await stock_seccion(client, 1) == {material["id_lista"]: 0}


async def test_devol_destino_inexistente_rechazado(
    client: AsyncClient,
) -> None:
    material, equipo = await _equipo_con_stock(client, cantidad=10)
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": equipo["equipo_id"],
            "destino_almacen_id": 9999,
            "detalle": [{"material_id": material["id_lista"], "cantidad": 1}],
        },
    )
    assert resp.status_code == 422


async def test_devol_multi_detalle(client: AsyncClient) -> None:
    m1 = await crear_material(client, descripcion="M1")
    m2 = await crear_material(client, descripcion="M2")
    equipo = await crear_equipo(client, nombre="Equipo Multi")
    await carga_inicial(client, material_id=m1["id_lista"], cantidad=50)
    await carga_inicial(client, material_id=m2["id_lista"], cantidad=30)

    for m, cant in ((m1, 50), (m2, 30)):
        b = await borrador_teams(
            client,
            almacen_id=1,
            equipo_id=equipo["equipo_id"],
            material_id=m["id_lista"],
            cantidad=cant,
        )
        await procesar(client, b["id"])

    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": equipo["equipo_id"],
            "destino_almacen_id": 1,
            "detalle": [
                {"material_id": m1["id_lista"], "cantidad": 20},
                {"material_id": m2["id_lista"], "cantidad": 15},
            ],
        },
    )
    assert resp.status_code == 201
    await procesar(client, resp.json()["id"])

    stock = await stock_seccion(client, 1)
    assert stock[m1["id_lista"]] == 20
    assert stock[m2["id_lista"]] == 15
