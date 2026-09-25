"""Inventario autónomo de equipos (REQ-DOMAIN-001/002) — contrato canónico
GET /api/v1/equipos/{equipo_id}/inventario (clave `material_id`).

Reemplaza al extinto modelo sparse (`vw_inventario_equipo_completo`):
el equipo nace con inventario VACÍO, solo registra stock físico originado
en movimientos TEAMS/DEVOL auditados, no renderiza filas fantasma (stock 0)
ni materiales inactivos (REQ-API-001) y cada fila traza su movimiento de
origen vía `ultimo_movimiento_id`.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Seccion
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    procesar,
)


@pytest.mark.critical
async def test_sin_registro_fisico_no_aparece(
    client: AsyncClient,
) -> None:
    """REQ-DOMAIN-002: un material sin movimiento NO aparece en el inventario
    del equipo (cero herencia del catálogo global, cero fantasmas)."""
    material = await crear_material(client, descripcion="Equipo 1")
    equipo = await crear_equipo(client, nombre="Equipo Autonomo")

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in filas


async def test_equipo_nuevo_inventario_vacio_200(
    client: AsyncClient,
) -> None:
    """REQ-DOMAIN-002: un equipo nuevo devuelve [] (200) — inventario
    autónomo vacío, jamás 404 por catálogo vacío ni herencia global."""
    await crear_material(client, descripcion="Material huérfano")
    equipo = await crear_equipo(client, nombre="Equipo Nuevo")

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas == {}


async def test_con_stock_real(client: AsyncClient) -> None:
    """TEAMS 40 → fila física con stock 40, alerta correcta y trazabilidad
    al movimiento de origen (`ultimo_movimiento_id`)."""
    material = await crear_material(client, descripcion="Equipo 2")
    equipo = await crear_equipo(client, nombre="Equipo Stock Real")
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

    filas = await inventario_equipo(client, equipo["equipo_id"])
    fila = filas[material["id_lista"]]
    assert fila["stock_actual"] == 40
    assert fila["alerta_stock"] is False
    assert fila["ultimo_movimiento_id"] == b["id"]
    assert fila["material_id"] == material["id_lista"]


async def test_secciones_solo_general_activa(
    client: AsyncClient, session
) -> None:
    """REQ-DOMAIN-003/006 (diseño 0012): solo "Inventario General" queda
    como sección activa; las secciones FO están soft-inactivas."""
    resp = await client.get("/api/v1/inventario/secciones")
    assert resp.status_code == 200
    secciones = resp.json()
    assert len(secciones) == 1
    assert secciones[0]["nombre"] == "Inventario General"
    assert secciones[0]["tipo"] == "GENERAL"
    assert secciones[0]["is_active"] is True
    total = len((await session.execute(select(Seccion))).scalars().all())
    activas = [
        s
        for s in (await session.execute(select(Seccion))).scalars().all()
        if s.is_active
    ]
    assert total >= 1
    assert len(activas) == 1


async def test_stock_seccion_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/inventario/secciones/9999")
    assert resp.status_code == 404


async def test_alerta_stock_bandera(client: AsyncClient) -> None:
    """La bandera `alerta_stock` se calcula con la clave nueva
    (`stock_actual <= stock_minimo`) tanto en sección como en equipo."""
    material = await crear_material(
        client, descripcion="Equipo 3", stock_minimo=70
    )
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    equipo = await crear_equipo(client, nombre="Eq A3")
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
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

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["alerta_stock"] is True


async def test_material_inactivo_no_aparece_en_inventario_equipo(
    client: AsyncClient,
) -> None:
    """REQ-API-001: el soft-delete del material lo retira del inventario del
    equipo aunque la fila física conserve stock registrado (cero fantasmas
    de materiales inactivos en lecturas operativas)."""
    material = await crear_material(client, descripcion="Equipo 4")
    equipo = await crear_equipo(client, nombre="Equipo SoftDelete")
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

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] in filas

    resp = await client.delete(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 204

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in filas
