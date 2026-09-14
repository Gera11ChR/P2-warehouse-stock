"""E2E-01 — Flujo integrado completo: formalización del script de
verificación de FASE 2 dentro de pytest (11 pasos de dominio).

Alta catálogo -> alta equipo -> carga inicial -> TEAMS -> DEVOL ->
cancelación DEVOL -> cancelación TEAMS -> vista sparse -> 400 stock ->
409 estado -> 404 -> auditoría completa.
"""

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


@pytest.mark.critical
async def test_flujo_completo_11_pasos(
    client: AsyncClient, session
) -> None:
    # 1. Catálogo + equipo
    material = await crear_material(
        client, descripcion="E2E Material", codigo="E2E-001"
    )
    equipo = await crear_equipo(
        client, nombre="E2E Equipo", integrantes=["qa"]
    )
    assert material["id_lista"] >= 1 and equipo["equipo_id"] >= 1

    # 2. Carga inicial 100
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}

    # 3. TEAMS 40
    b_teams = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=40,
    )
    await procesar(client, b_teams["id"])
    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 40

    # 4. DEVOL 15
    b_devol = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=15,
    )
    await procesar(client, b_devol["id"])
    assert await stock_seccion(client, 1) == {material["id_lista"]: 75}

    # 5. Cancelar DEVOL
    await cancelar(client, b_devol["id"], motivo="E2E")
    assert await stock_seccion(client, 1) == {material["id_lista"]: 60}

    # 6. Cancelar TEAMS (sparse: fila viva con 0)
    await cancelar(client, b_teams["id"], motivo="E2E")
    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 0

    # 7. Sparse: material sin registro renderiza stock 0
    material2 = await crear_material(client, descripcion="E2E Sin Stock")
    filas = await catalogo_equipo(client, equipo["equipo_id"])
    assert filas[material2["id_lista"]]["stock_actual"] == 0

    # 8. Stock insuficiente -> 400 (P0001)
    b_insuf = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=9999,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": b_insuf["id"]},
    )
    assert resp.status_code == 400

    # 9. Estado no procesable -> 409
    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": b_teams["id"]},
    )
    assert resp.status_code == 409

    # 10. Inexistente -> 404
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": 9999}
    )
    assert resp.status_code == 404

    # 11. Auditoría completa (4+ eventos del material)
    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.material_id == material["id_lista"]
            )
        )
    ).scalars().all()
    tipos = {e.tipo_accion for e in eventos}
    assert "STOCK_INICIAL" in tipos
    assert "TEAMS_TRANSFERENCIA" in tipos
    assert "DEVOL_DEVOLUCION" in tipos
    assert "MOVIMIENTO_CANCELADO" in tipos
    assert len(eventos) >= 4
