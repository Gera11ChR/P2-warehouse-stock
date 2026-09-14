"""CRUD de catálogo y categorías vía API — DMS - TELECOM.

Incluye inmutabilidad de id_lista a nivel HTTP, soft-delete y auditoría
automática por trigger (fn_auditar_modificacion_material).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import AuditoriaEvento
from tests.helpers.fabrica import crear_material


@pytest.mark.critical
async def test_crear_material_genera_id_lista(
    client: AsyncClient,
) -> None:
    material = await crear_material(
        client, descripcion="Fibra 12F", codigo="F12-001"
    )
    assert material["id_lista"] >= 1
    assert material["descripcion"] == "Fibra 12F"
    assert material["is_active"] is True


async def test_crear_con_nueva_categoria(client: AsyncClient) -> None:
    material = await crear_material(
        client, descripcion="Splitter", nueva_categoria="Pasivos"
    )
    assert material["categoria"] == "Pasivos"
    assert material["categoria_id"] is not None


async def test_categoria_id_inexistente_rechazado(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/catalogo",
        json={"descripcion": "X", "categoria_id": 9999},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_listar_con_filtros(client: AsyncClient) -> None:
    await crear_material(client, descripcion="AAA", codigo="A-001")
    await crear_material(client, descripcion="BBB", codigo="B-002")
    await crear_material(client, descripcion="CCC", codigo="C-003")

    resp = await client.get("/api/v1/catalogo", params={"buscar": "BBB"})
    assert resp.status_code == 200
    assert [m["codigo"] for m in resp.json()["materiales"]] == ["B-002"]

    resp = await client.get(
        "/api/v1/catalogo", params={"desde_sku": "B", "hasta_sku": "CZZ"}
    )
    assert resp.status_code == 200
    codigos = {m["codigo"] for m in resp.json()["materiales"]}
    assert codigos == {"B-002", "C-003"}


async def test_obtener_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/catalogo/9999")
    assert resp.status_code == 404


@pytest.mark.critical
async def test_patch_con_id_lista_en_body_422(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="Original")
    resp = await client.patch(
        f"/api/v1/catalogo/{material['id_lista']}",
        json={"id_lista": 999},
    )
    assert resp.status_code == 422


async def test_patch_actualiza_descripcion(client: AsyncClient) -> None:
    material = await crear_material(client, descripcion="V1")
    resp = await client.patch(
        f"/api/v1/catalogo/{material['id_lista']}",
        json={"descripcion": "V2"},
    )
    assert resp.status_code == 200
    assert resp.json()["descripcion"] == "V2"


@pytest.mark.critical
async def test_delete_soft_delete_y_no_reutilizacion(
    client: AsyncClient, session
) -> None:
    material = await crear_material(client, descripcion="Eliminable")
    id_lista = material["id_lista"]

    resp = await client.delete(f"/api/v1/catalogo/{id_lista}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/catalogo/{id_lista}")
    assert resp.status_code == 404

    resp = await client.get("/api/v1/catalogo")
    assert all(m["id_lista"] != id_lista for m in resp.json()["materiales"])

    nuevo = await crear_material(client, descripcion="Siguiente")
    assert nuevo["id_lista"] > id_lista


async def test_categoria_duplicada_409(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/catalogo/categorias", json={"nombre": "Activos"}
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/catalogo/categorias", json={"nombre": "Activos"}
    )
    assert resp.status_code == 409


async def test_patch_catalogo_genera_auditoria_trigger(
    client: AsyncClient, session
) -> None:
    material = await crear_material(
        client, descripcion="Auditable", codigo="AUD-1"
    )
    resp = await client.patch(
        f"/api/v1/catalogo/{material['id_lista']}",
        json={"descripcion": "Auditable v2"},
    )
    assert resp.status_code == 200

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.material_id == material["id_lista"]
            )
        )
    ).scalars().all()
    modificaciones = [
        e for e in eventos if e.tipo_accion == "MATERIAL_MODIFICADO"
    ]
    assert len(modificaciones) == 1
    detalles = modificaciones[0].detalles or {}
    assert detalles["valores_anteriores"]["descripcion"] == "Auditable"
    assert detalles["valores_nuevos"]["descripcion"] == "Auditable v2"
