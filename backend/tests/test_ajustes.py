"""Ajustes de inventario — carga inicial (idempotencia estricta) y ajuste
administrativo con diferencial auditado (fn_cargar_stock_inicial y
fn_ajustar_stock_almacen)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    ajustar_stock,
    carga_inicial,
    crear_material,
    stock_seccion,
)


@pytest.mark.critical
async def test_carga_inicial_unica(client: AsyncClient, session) -> None:
    material = await crear_material(client, descripcion="Carga 1")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )

    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "STOCK_INICIAL"
            )
        )
    ).scalars().one()
    assert evento.cantidad == 100


@pytest.mark.critical
async def test_carga_inicial_duplicada_400(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Carga 2")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )

    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={
            "almacen_id": 1,
            "material_id": material["id_lista"],
            "cantidad": 50,
        },
    )
    assert resp.status_code == 400
    assert "ya posee un registro de inventario activo" in resp.json()["error"][
        "message"
    ]
    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}


async def test_carga_inicial_almacen_inexistente_404(
    client: AsyncClient,
) -> None:
    """AJU-04: pre-validación de sección evita FK 23503 y clasifica 404."""
    material = await crear_material(client, descripcion="Carga 3")
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 9999, "material_id": material["id_lista"], "cantidad": 10},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["coordinates"][0]["almacen_id"] == 9999


async def test_carga_inicial_material_inexistente_404(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 1, "material_id": 9999, "cantidad": 10},
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_ajuste_con_diferencial_auditado(
    client: AsyncClient, session
) -> None:
    material = await crear_material(client, descripcion="Ajuste 1")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )

    await ajustar_stock(
        client,
        almacen_id=1,
        material_id=material["id_lista"],
        nuevo_stock=60,
        motivo="Conteo físico",
    )

    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["stock_anterior"] == 100
    assert detalles["stock_nuevo"] == 60
    assert detalles["diferencial"] == -40
    assert detalles["motivo"] == "Conteo físico"


@pytest.mark.critical
async def test_ajuste_sin_registro_previo_404(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Ajuste 2")
    resp = await client.post(
        "/api/v1/ajustes/stock-almacen",
        json={
            "almacen_id": 1,
            "material_id": material["id_lista"],
            "nuevo_stock": 10,
            "motivo": "X",
        },
    )
    assert resp.status_code == 404
    assert "Realice primero la carga inicial" in resp.json()["error"][
        "message"
    ]


async def test_ajuste_motivo_vacio_422(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Ajuste 3")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=10
    )
    resp = await client.post(
        "/api/v1/ajustes/stock-almacen",
        json={
            "almacen_id": 1,
            "material_id": material["id_lista"],
            "nuevo_stock": 5,
            "motivo": "",
        },
    )
    assert resp.status_code == 422


async def test_ajuste_no_muta_inventario_equipos(
    client: AsyncClient, session
) -> None:
    from sqlalchemy import text

    material = await crear_material(client, descripcion="Ajuste 4")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    await ajustar_stock(
        client,
        almacen_id=1,
        material_id=material["id_lista"],
        nuevo_stock=80,
    )
    total = (
        await session.execute(
            text("SELECT COUNT(*) FROM inventario_equipos")
        )
    ).scalar_one()
    assert total == 0
