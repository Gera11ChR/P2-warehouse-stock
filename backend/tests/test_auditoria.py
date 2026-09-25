"""Ledger de auditoría append-only — solo lectura, filtros y trazabilidad."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    procesar,
)


@pytest.mark.critical
async def test_auditoria_sin_endpoint_de_mutacion(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/v1/auditoria", json={"tipo": "X"})
    assert resp.status_code == 405
    resp = await client.delete("/api/v1/auditoria")
    assert resp.status_code == 405


async def test_filtros(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Audit Filtros")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=50
    )

    resp = await client.get(
        "/api/v1/auditoria",
        params={"material_id": material["id_lista"]},
    )
    assert resp.status_code == 200
    eventos = resp.json()["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["tipo_accion"] == "STOCK_INICIAL"

    resp = await client.get(
        "/api/v1/auditoria", params={"tipo_accion": "STOCK_INICIAL"}
    )
    assert len(resp.json()["eventos"]) == 1

    resp = await client.get(
        "/api/v1/auditoria", params={"tipo_accion": "INEXISTENTE"}
    )
    assert resp.json()["eventos"] == []


async def test_limit_maximo_500(client: AsyncClient, session) -> None:
    material = await crear_material(client, descripcion="Audit Limit")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=10
    )

    resp = await client.get("/api/v1/auditoria", params={"limit": 9999})
    assert resp.status_code == 200
    eventos = resp.json()["eventos"]
    assert 1 <= len(eventos) <= 500


async def test_evento_teams_con_metadatos(client: AsyncClient, session) -> None:
    material = await crear_material(client, descripcion="Audit TEAMS")
    equipo = await crear_equipo(client, nombre="Equipo Audit")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
        observaciones="Con auditoría",
    )
    await procesar(client, b["id"])

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["movimiento_id"] == b["id"]
    assert detalles["observaciones"] == "Con auditoría"
    assert detalles["stock_remanente_origen"] == 70
    assert evento.cantidad == 30
    assert evento.resultado == "EXITO"


async def test_payload_evento_con_datos_legibles_material(
    client: AsyncClient,
) -> None:
    """REQ-API-008: el payload del evento resuelve via LEFT JOIN la
    `descripcion`, `codigo`, `categoria` y `estado_activo` del material
    (sin depender del ID Lista visible)."""
    material = await crear_material(
        client, descripcion="Legible", codigo="LEG-001", nueva_categoria="Redes"
    )
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=10
    )

    resp = await client.get(
        "/api/v1/auditoria",
        params={"material_id": material["id_lista"]},
    )
    assert resp.status_code == 200
    eventos = resp.json()["eventos"]
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento["descripcion"] == "Legible"
    assert evento["codigo"] == "LEG-001"
    assert evento["categoria"] == "Redes"
    assert evento["estado_activo"] is True


async def test_filtro_descripcion_ilike(client: AsyncClient) -> None:
    """REQ-UI-006: el filtro ?descripcion= aplica ILIKE sobre la descripción
    del material (parámetro legible en lugar del deprecado ID Lista)."""
    m1 = await crear_material(
        client, descripcion="Switch Industrial", codigo="F-1"
    )
    m2 = await crear_material(client, descripcion="Patchcord", codigo="F-2")
    await carga_inicial(client, material_id=m1["id_lista"], cantidad=10)
    await carga_inicial(client, material_id=m2["id_lista"], cantidad=10)

    resp = await client.get(
        "/api/v1/auditoria", params={"descripcion": "switch"}
    )
    assert resp.status_code == 200
    eventos = resp.json()["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["descripcion"] == "Switch Industrial"

    resp = await client.get(
        "/api/v1/auditoria", params={"descripcion": "INEXISTENTE-QA"}
    )
    assert resp.json()["eventos"] == []


async def test_material_soft_deleted_sigue_visible_en_auditoria(
    client: AsyncClient,
) -> None:
    """REQ-API-008 + Constitution 2.4 (ledger inmutable): tras el soft-delete
    del material, sus eventos históricos permanecen visibles y legibles con
    `estado_activo=false` (etiqueta [Inactivo] del frontend)."""
    material = await crear_material(
        client, descripcion="Eliminado después", codigo="DEL-001"
    )
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=10
    )

    resp = await client.delete(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 204

    resp = await client.get(
        "/api/v1/auditoria",
        params={"material_id": material["id_lista"]},
    )
    assert resp.status_code == 200
    eventos = resp.json()["eventos"]
    assert len(eventos) >= 1
    assert eventos[0]["descripcion"] == "Eliminado después"
    assert eventos[0]["codigo"] == "DEL-001"
    assert eventos[0]["estado_activo"] is False
