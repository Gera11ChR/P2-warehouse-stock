"""Transferencias TEAMS — éxito, alerta de stock mínimo, fallos y concurrencia.

Cubre el mapeo SQLSTATE P0001 -> HTTP 400, la clasificación 404/409 por
pre-chequeo y la serialización por bloqueos FOR UPDATE (TMS-12).
"""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    catalogo_equipo,
    crear_equipo,
    crear_material,
    procesar,
    stock_seccion,
)


async def _setup_stock(
    client: AsyncClient,
    *,
    cantidad: int = 100,
    stock_minimo: int | None = None,
) -> tuple[dict, dict]:
    material = await crear_material(
        client,
        descripcion="Material TEAMS",
        stock_minimo=stock_minimo,
    )
    equipo = await crear_equipo(client, nombre="Equipo TEAMS")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=cantidad
    )
    return material, equipo


@pytest.mark.critical
async def test_teams_exitoso_descuenta_y_suma(
    client: AsyncClient,
) -> None:
    material, equipo = await _setup_stock(client, cantidad=100)

    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    assert borrador["estado"] == "BORRADOR"

    resultado = await procesar(client, borrador["id"])
    assert resultado["estado"] == "CONFIRMADO"

    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 40


@pytest.mark.critical
async def test_alerta_stock_minimo_auditada(client: AsyncClient, session) -> None:
    material, equipo = await _setup_stock(
        client, cantidad=100, stock_minimo=70
    )

    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, borrador["id"])

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().one()
    assert (evento.detalles or {})["alerta_stock_minimo"] is True
    assert (evento.detalles or {})["stock_remanente_origen"] == 60


@pytest.mark.critical
async def test_stock_insuficiente_400_con_mensaje_pg(
    client: AsyncClient,
) -> None:
    material, equipo = await _setup_stock(client, cantidad=10)

    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": borrador["id"]},
    )
    assert resp.status_code == 400
    body = resp.json()["error"]
    assert "Stock insuficiente" in body["message"]
    assert await stock_seccion(client, 1) == {material["id_lista"]: 10}


async def test_procesar_inexistente_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": 9999}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "MOVIMIENTO_NOT_FOUND"


@pytest.mark.critical
async def test_procesar_no_borrador_409(client: AsyncClient) -> None:
    material, equipo = await _setup_stock(client, cantidad=100)
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, borrador["id"])

    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": borrador["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MOVIMIENTO_STATE_CONFLICT"


async def test_borrador_material_inexistente_rechazado(
    client: AsyncClient,
) -> None:
    equipo = await crear_equipo(client, nombre="EQ")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": 1,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": 9999, "cantidad": 1}],
        },
    )
    assert resp.status_code == 422


async def test_borrador_seccion_inexistente_rechazado(
    client: AsyncClient,
) -> None:
    material, equipo = await _setup_stock(client, cantidad=10)
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": 9999,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 1}],
        },
    )
    assert resp.status_code == 422


async def test_patch_borrador(client: AsyncClient) -> None:
    material, equipo = await _setup_stock(client, cantidad=100)
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    resp = await client.patch(
        f"/api/v1/movimientos/{borrador['id']}",
        json={
            "observaciones": "Actualizado",
            "detalle": [{"material_id": material["id_lista"], "cantidad": 25}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["observaciones"] == "Actualizado"
    assert resp.json()["detalle"][0]["cantidad"] == 25


@pytest.mark.critical
async def test_delete_borrador_y_procesar_despues_404(
    client: AsyncClient,
) -> None:
    material, equipo = await _setup_stock(client, cantidad=100)
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    resp = await client.delete(f"/api/v1/movimientos/{borrador['id']}")
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": borrador["id"]},
    )
    assert resp.status_code == 404


async def test_patch_confirmado_409(client: AsyncClient) -> None:
    material, equipo = await _setup_stock(client, cantidad=100)
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, borrador["id"])
    resp = await client.patch(
        f"/api/v1/movimientos/{borrador['id']}",
        json={"observaciones": "X"},
    )
    assert resp.status_code == 409


@pytest.mark.critical
async def test_teams_cantidad_exacta_deja_fila_viva_con_cero(
    client: AsyncClient,
) -> None:
    material, equipo = await _setup_stock(client, cantidad=40)

    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, borrador["id"])

    assert await stock_seccion(client, 1) == {material["id_lista"]: 0}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 40


@pytest.mark.critical
async def test_concurrencia_dos_teams_serializados(
    client: AsyncClient, client_factory
) -> None:
    """TMS-12: 2 borradores TEAMS simultáneos (60 c/u) sobre stock 100.
    La serialización por FOR UPDATE garantiza exactamente un éxito."""
    material, equipo = await _setup_stock(client, cantidad=100)

    b1 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=60,
    )
    b2 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=60,
    )

    c1 = client_factory()
    c2 = client_factory()

    async def disparar(mov_id: int) -> int:
        resp = await (
            c1 if mov_id == b1["id"] else c2
        ).post(
            "/api/v1/movimientos/procesar",
            json={"movimiento_id": mov_id},
        )
        return resp.status_code

    try:
        resultados = await asyncio.gather(
            disparar(b1["id"]), disparar(b2["id"])
        )
    finally:
        await c1.aclose()
        await c2.aclose()

    assert sorted(resultados) == [200, 400]
    assert await stock_seccion(client, 1) == {material["id_lista"]: 40}
