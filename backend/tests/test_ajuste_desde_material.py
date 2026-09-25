"""Edición de stock y SKU desde el formulario de material (Inventario
General) — REQ-API-002/003, REQ-UI-004, Constitution 2.4/6.2.

El stock JAMÁS se actualiza por ORM: el delta se enruta a
fn_ajustar_stock_general → fn_ajustar_stock_almacen con `motivo`
obligatorio; la atomicidad garantiza que un ajuste fallido revierte también
la edición del material. La edición aislada del SKU emite el evento
MATERIAL_MODIFICADO (migración 0013).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    carga_inicial,
    crear_material,
    patch_material,
    stock_seccion,
)


async def _material_con_stock(
    client: AsyncClient, *, cantidad: int = 100
) -> dict:
    material = await crear_material(
        client, descripcion="Material Ajustable", codigo="AJU-001"
    )
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=cantidad
    )
    return material


@pytest.mark.critical
async def test_stock_actual_sin_motivo_422(client: AsyncClient) -> None:
    """REQ-API-003: stock_actual sin motivo (o motivo vacío) es rechazado en
    el schema con 422 — jamás llega a PostgreSQL."""
    material = await _material_con_stock(client)

    for payload in (
        {"stock_actual": 80},
        {"stock_actual": 80, "motivo": ""},
        {"stock_actual": 80, "motivo": "   "},
    ):
        resp = await patch_material(client, material["id_lista"], **payload)
        assert resp.status_code == 422

    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}


@pytest.mark.critical
async def test_stock_actual_con_motivo_ajusta_por_delta(
    client: AsyncClient, session
) -> None:
    """REQ-API-002/003: PATCH con stock_actual + motivo calcula el delta en
    PostgreSQL y audita AJUSTE_INVENTARIO con el contexto completo."""
    material = await _material_con_stock(client)

    resp = await patch_material(
        client,
        material["id_lista"],
        stock_actual=60,
        motivo="Conteo físico desde material",
    )
    assert resp.status_code == 200
    assert resp.json()["id_lista"] == material["id_lista"]

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
    assert detalles["motivo"] == "Conteo físico desde material"


@pytest.mark.critical
async def test_atomicidad_ajuste_fallido_revierte_edicion(
    client: AsyncClient,
) -> None:
    """REQ-API-003 + Constitution 4.1: PATCH con descripcion válida +
    stock_actual sobre un material SIN inventario GENERAL → 400 y la
    descripción NO persiste (rollback atómico de todo el request)."""
    material = await crear_material(
        client, descripcion="Original", codigo="ATOM-001"
    )

    resp = await patch_material(
        client,
        material["id_lista"],
        descripcion="Edición que debe revertir",
        stock_actual=10,
        motivo="Ajuste sin carga inicial",
    )
    assert resp.status_code == 400
    assert "No se encontró inventario del material" in resp.json()["error"][
        "message"
    ]

    resp = await client.get(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 200
    assert resp.json()["descripcion"] == "Original"


async def test_edicion_aislada_sku_auditada(client: AsyncClient, session) -> None:
    """REQ-UI-004 + migración 0013 + Constitution 6.2: la edición aislada del
    CÓDIGO (SKU) emite el evento MATERIAL_MODIFICADO con valores_anteriores/
    valores_nuevos del SKU."""
    material = await crear_material(
        client, descripcion="SKU Editable", codigo="SKU-OLD"
    )

    resp = await patch_material(client, material["id_lista"], codigo="SKU-NEW")
    assert resp.status_code == 200
    assert resp.json()["codigo"] == "SKU-NEW"
    assert resp.json()["descripcion"] == "SKU Editable"

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MATERIAL_MODIFICADO",
                AuditoriaEvento.material_id == material["id_lista"],
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["valores_anteriores"]["codigo"] == "SKU-OLD"
    assert detalles["valores_nuevos"]["codigo"] == "SKU-NEW"


async def test_edicion_stock_no_toca_inventario_equipos_ni_fibra(
    client: AsyncClient, session
) -> None:
    """REQ-UI-004 (alcance): la edición de stock desde el material aplica
    SOLO al Inventario General; equipos y FO quedan intactos."""
    from sqlalchemy import text

    material = await _material_con_stock(client)
    resp = await patch_material(
        client,
        material["id_lista"],
        stock_actual=90,
        motivo="Ajuste de alcance",
    )
    assert resp.status_code == 200

    equipos = (
        await session.execute(text("SELECT COUNT(*) FROM inventario_equipos"))
    ).scalar_one()
    fibra = (
        await session.execute(text("SELECT COUNT(*) FROM inventario_fibra"))
    ).scalar_one()
    assert equipos == 0
    assert fibra == 0


async def test_motivo_sin_stock_actual_es_inocuo(client: AsyncClient) -> None:
    """Caracterización: `motivo` sin `stock_actual` no altera stock ni
    genera evento de ajuste (solo se exige cuando se edita stock)."""
    material = await _material_con_stock(client)
    resp = await patch_material(
        client, material["id_lista"], motivo="Motivo huérfano"
    )
    assert resp.status_code == 200
    assert await stock_seccion(client, 1) == {material["id_lista"]: 100}
