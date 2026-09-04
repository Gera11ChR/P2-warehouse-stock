import uuid
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.schemas.material import MaterialCreate, SUPPORTED_UNITS

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


@pytest.fixture(scope="module")
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _headers() -> dict:
    return {"X-Actor": "actor-x"}


def _sku() -> str:
    return f"T-{uuid.uuid4().hex[:10]}"


async def _ensure_scope() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('DW-1', 'W1-dash'), ('DW-2', 'W2-dash') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO user_warehouse_scopes (actor_id, warehouse_id, granted_by) "
                "VALUES ('actor-x', 'DW-1', 'admin'), ('actor-x', 'DW-2', 'admin') "
                "ON CONFLICT DO NOTHING"
            )
        )


async def _seed_material(
    sku: str, *, warehouse_id: str = "DW-1", on_hand: int = 50, **extra
) -> None:
    await _ensure_scope()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO skus (sku, description, unit_of_measure, min_stock, categoria, tipo) "
                "VALUES (:sku, :description, :um, :min_stock, :categoria, :tipo) "
                "ON CONFLICT (sku) DO NOTHING"
            ),
            {
                "sku": sku,
                "description": extra.get("description", "Material de prueba"),
                "um": extra.get("um", "PZ"),
                "min_stock": extra.get("min_stock", 5),
                "categoria": extra.get("categoria", "Cables"),
                "tipo": extra.get("tipo", "GENERAL"),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES (:warehouse_id, :sku, :on_hand) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = EXCLUDED.on_hand_quantity"
            ),
            {"warehouse_id": warehouse_id, "sku": sku, "on_hand": on_hand},
        )


def test_supported_units_vocabulary() -> None:
    assert set(SUPPORTED_UNITS) == {
        "PZ",
        "LT",
        "CARRETE (1 KM)",
        "METRO (M)",
        "CARRETE (5 KM)",
        "BOLSA (500 PZ)",
        "PAQUETE (100 PZ)",
        "ROLLO",
        "EQUIPO",
        "UNIDAD",
    }


def test_material_unit_vocab_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        MaterialCreate.model_validate({"codigo": "X-1", "um": "GALON"})
    assert MaterialCreate.model_validate({"codigo": "X-1", "um": "PZ"}).um == "PZ"
    with pytest.raises(ValidationError):
        MaterialCreate.model_validate({"codigo": "X-1", "tipo": "RARO"})


@pytest.mark.asyncio
async def test_material_crud_round_trip(client: httpx.AsyncClient) -> None:
    await _ensure_scope()
    sku = _sku()
    created = await client.post(
        "/api/v1/materials",
        json={"codigo": sku, "descripcion": "Cable de prueba", "um": "PZ", "stock_minimo": 10},
        headers=_headers(),
    )
    assert created.status_code == 201
    assert created.json()["codigo"] == sku
    assert created.json()["stock_minimo"] == 10

    read = await client.get(f"/api/v1/materials/{sku}", headers=_headers())
    assert read.status_code == 200
    assert read.json()["descripcion"] == "Cable de prueba"

    updated = await client.patch(
        f"/api/v1/materials/{sku}",
        json={"stock_minimo": 20, "categoria": "Conectores"},
        headers=_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["stock_minimo"] == 20
    assert updated.json()["categoria"] == "Conectores"

    deleted = await client.delete(f"/api/v1/materials/{sku}", headers=_headers())
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/materials/{sku}", headers=_headers())).status_code == 422


@pytest.mark.asyncio
async def test_material_create_rejects_unscoped_actor(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/materials",
        json={"codigo": _sku(), "descripcion": "X", "um": "PZ"},
        headers={"X-Actor": "sin-scope"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_material_delete_blocked_with_stock(client: httpx.AsyncClient) -> None:
    sku = _sku()
    await _seed_material(sku, on_hand=10)
    response = await client.delete(f"/api/v1/materials/{sku}", headers=_headers())
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_inventory_one_row_per_warehouse(client: httpx.AsyncClient) -> None:
    sku = _sku()
    await _seed_material(sku, warehouse_id="DW-1", on_hand=30)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('DW-2', :sku, 70) ON CONFLICT (warehouse_id, sku) DO NOTHING"
            ),
            {"sku": sku},
        )

    response = await client.get(
        "/api/v1/inventory", params={"buscar": sku}, headers=_headers()
    )
    assert response.status_code == 200
    rows = [r for r in response.json()["items"] if r["codigo"] == sku]
    assert len(rows) == 2
    assert {r["almacen_id"] for r in rows} == {"DW-1", "DW-2"}
    assert {r["stock_actual"] for r in rows} == {30, 70}


@pytest.mark.asyncio
async def test_team_inventory_create_update_timestamp(
    client: httpx.AsyncClient,
) -> None:
    sku = _sku()
    await _seed_material(sku, description="Cable asignable")

    created = await client.post(
        "/api/v1/team-inventory",
        json={"equipo": "Cuadrilla Norte", "usuario": "juan.perez", "codigo": sku, "cantidad": 3},
        headers=_headers(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["descripcion"] == "Cable asignable"
    assert body["cantidad"] == 3
    original_ts = body["ultima_modificacion"]

    updated = await client.patch(
        f"/api/v1/team-inventory/{body['id']}",
        json={"cantidad": 5},
        headers=_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["cantidad"] == 5
    assert updated.json()["ultima_modificacion"] >= original_ts


@pytest.mark.asyncio
async def test_fiber_variant_round_trip(client: httpx.AsyncClient) -> None:
    sku = _sku()
    await _seed_material(sku, tipo="FIBRA", description="Fibra de prueba")

    created = await client.post(
        "/api/v1/fiber-optics",
        json={"codigo": sku, "variante": "Rollo 500m", "metros_restantes": 320, "cantidad": 2},
        headers=_headers(),
    )
    assert created.status_code == 201
    assert created.json()["metros_restantes"] == 320
    assert created.json()["stock_actual"] == 2

    listed = await client.get("/api/v1/fiber-optics", headers=_headers())
    assert listed.status_code == 200
    assert any(v["codigo"] == sku for v in listed.json()["items"])


@pytest.mark.asyncio
async def test_kpis_aggregate(client: httpx.AsyncClient) -> None:
    sku = _sku()
    await _seed_material(sku, on_hand=4, min_stock=5)
    response = await client.get("/api/v1/kpis", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total_materiales"] >= 1
    assert body["stock_total"] >= 4
    assert body["alertas_stock"] >= 1
    assert "transferencias_hoy" in body


@pytest.mark.asyncio
async def test_audit_list(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/audit", headers=_headers())
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)
