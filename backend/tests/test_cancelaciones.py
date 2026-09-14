"""Reversión forense fn_cancelar_movimiento — restitución exacta, motivo
auditado y transiciones de estado irreversibles."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    cancelar,
    carga_inicial,
    catalogo_equipo,
    crear_equipo,
    crear_material,
    procesar,
    stock_seccion,
)


async def _teams_confirmado(
    client: AsyncClient, *, cantidad: int = 40
) -> tuple[dict, dict, dict]:
    material = await crear_material(client, descripcion="Cancel TEAMS")
    equipo = await crear_equipo(client, nombre="Equipo Cancel")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    borrador = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=cantidad,
    )
    await procesar(client, borrador["id"])
    return material, equipo, borrador


@pytest.mark.critical
async def test_cancelar_teams_restituye_exacto(
    client: AsyncClient,
) -> None:
    material, equipo, borrador = await _teams_confirmado(client, cantidad=40)
    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}

    resultado = await cancelar(
        client, borrador["id"], motivo="Entrega incorrecta"
    )
    assert resultado["estado"] == "CANCELADO"

    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 0


@pytest.mark.critical
async def test_cancelacion_audita_motivo_y_usuario(
    client: AsyncClient, session
) -> None:
    _, _, borrador = await _teams_confirmado(client, cantidad=40)
    await cancelar(client, borrador["id"], motivo="Motivo QA")

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MOVIMIENTO_CANCELADO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["motivo_cancelacion"] == "Motivo QA"
    assert detalles["movimiento_id"] == borrador["id"]


async def test_cancelar_borrador_409(client: AsyncClient) -> None:
    material2 = await crear_material(client, descripcion="Cancel B2")
    equipo2 = await crear_equipo(client, nombre="Equipo B2")
    await carga_inicial(
        client, material_id=material2["id_lista"], cantidad=50
    )
    borrador2 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo2["equipo_id"],
        material_id=material2["id_lista"],
        cantidad=10,
    )
    resp = await client.post(
        f"/api/v1/movimientos/{borrador2['id']}/cancelar", json={}
    )
    assert resp.status_code == 409


async def test_cancelar_cancelado_409(client: AsyncClient) -> None:
    _, _, borrador = await _teams_confirmado(client, cantidad=10)
    await cancelar(client, borrador["id"])

    resp = await client.post(
        f"/api/v1/movimientos/{borrador['id']}/cancelar", json={}
    )
    assert resp.status_code == 409


async def test_cancelar_inexistente_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/movimientos/9999/cancelar", json={}
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_cancelar_devol_restituye_inverso(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Cancel DEVOL")
    equipo = await crear_equipo(client, nombre="Equipo DEVOL C")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b1 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=15,
    )
    await procesar(client, b2["id"])
    assert await stock_seccion(client, 1) == {material["id_lista"]: 75}

    await cancelar(client, b2["id"], motivo="DEVOL errónea")

    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 40


async def test_procesar_tras_cancelar_409(client: AsyncClient) -> None:
    _, _, borrador = await _teams_confirmado(client, cantidad=10)
    await cancelar(client, borrador["id"])

    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": borrador["id"]},
    )
    assert resp.status_code == 409
