from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.db import engine
from app.main import app
from app.models import AuditLog, Sku, StockMovement, StockTransfer, TransferLineItem
from app.seed import OFFICIAL_CATALOG, OFFICIAL_SKUS, seed

HEAD_CFG = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="module", autouse=True)
def _schema_at_head() -> None:
    command.upgrade(HEAD_CFG, "head")


@pytest.fixture(scope="module")
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


LEGACY_SKU = "LEGACY-TEST-001"


async def _history_counts() -> tuple[int, int, int, int]:
    async with engine.begin() as conn:
        transfers = (
            await conn.execute(select(func.count()).select_from(StockTransfer))
        ).scalar_one()
        lines = (
            await conn.execute(select(func.count()).select_from(TransferLineItem))
        ).scalar_one()
        audits = (
            await conn.execute(select(func.count()).select_from(AuditLog))
        ).scalar_one()
        movements = (
            await conn.execute(select(func.count()).select_from(StockMovement))
        ).scalar_one()
        return transfers, lines, audits, movements


async def _insert_legacy_with_history() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO skus (sku, description, tipo, is_active) "
                "VALUES (:sku, 'Legacy demo', 'GENERAL', true) "
                "ON CONFLICT (sku) DO UPDATE SET is_active = true"
            ),
            {"sku": LEGACY_SKU},
        )
        await conn.execute(
            text(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('CENTRAL', 'Almacén Central') ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('CENTRAL', :sku, 25) "
                "ON CONFLICT (warehouse_id, sku) DO UPDATE SET on_hand_quantity = 25"
            ),
            {"sku": LEGACY_SKU},
        )
        await conn.execute(
            text(
                "INSERT INTO stock_movements "
                "(warehouse_id, sku, quantity_change, movement_type, actor_id) "
                "VALUES ('CENTRAL', :sku, 25, 'RECEIPT', 'seed') "
                "ON CONFLICT DO NOTHING"
            ),
            {"sku": LEGACY_SKU},
        )


async def _active_skus() -> set[str]:
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text("SELECT sku FROM skus WHERE is_active = true ORDER BY sku")
            )
        ).all()
        return {row[0] for row in rows}


async def _orphan_counts() -> tuple[int, int, int]:
    async with engine.begin() as conn:
        orphan_inventory = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM warehouse_inventory wi "
                    "LEFT JOIN skus s ON s.sku = wi.sku WHERE s.sku IS NULL"
                )
            )
        ).scalar_one()
        orphan_movements = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM stock_movements sm "
                    "LEFT JOIN skus s ON s.sku = sm.sku WHERE s.sku IS NULL"
                )
            )
        ).scalar_one()
        orphan_lines = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM transfer_line_items li "
                    "LEFT JOIN skus s ON s.sku = li.sku WHERE s.sku IS NULL"
                )
            )
        ).scalar_one()
        return orphan_inventory, orphan_movements, orphan_lines


@pytest.mark.asyncio
async def test_seed_twice_yields_exactly_53_active_official_skus() -> None:
    await _insert_legacy_with_history()
    before = await _history_counts()

    await seed()
    first = await _active_skus()
    counts_after_first = await _history_counts()

    assert first == set(OFFICIAL_SKUS)
    assert len(first) == 53
    assert len(OFFICIAL_CATALOG) == 53
    assert len(set(OFFICIAL_SKUS)) == 53
    assert counts_after_first == before

    await seed()
    second = await _active_skus()
    assert second == set(OFFICIAL_SKUS)
    assert await _history_counts() == before

    async with engine.begin() as conn:
        legacy_active = (
            await conn.execute(
                text("SELECT is_active FROM skus WHERE sku = :sku"),
                {"sku": LEGACY_SKU},
            )
        ).scalar_one()
    assert legacy_active is False


@pytest.mark.asyncio
async def test_fiber_module_flags_and_referential_integrity() -> None:
    await seed()
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT sku, tipo FROM skus "
                    "WHERE sku LIKE 'CF-%' AND is_active = true"
                )
            )
        ).all()
        fiber_skus = {sku for sku, _ in rows}
        assert fiber_skus == {"CF-DROP", "CF-6H-BRND", "CF-12H-BRND", "CF-24H-BRND", "CF-48H-BRND"}
        for _, tipo in rows:
            assert tipo == "FIBRA"

        general = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM skus "
                    "WHERE is_active = true AND tipo = 'GENERAL'"
                )
            )
        ).scalar_one()
        assert general == 48

        custody = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM warehouse_inventory wi "
                    "JOIN skus s ON s.sku = wi.sku "
                    "WHERE s.is_active = true AND wi.warehouse_id = 'CENTRAL'"
                )
            )
        ).scalar_one()
        assert custody == 53

    assert await _orphan_counts() == (0, 0, 0)


@pytest.mark.asyncio
async def test_inventory_endpoint_returns_only_official_rows(
    client: httpx.AsyncClient,
) -> None:
    await seed()
    response = await client.get(
        "/api/v1/inventory", headers={"X-Actor": "actor-x"}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert {row["codigo"] for row in items} == set(OFFICIAL_SKUS)
    assert len(items) == 53
    assert all(row["almacen_id"] == "CENTRAL" for row in items)


@pytest.mark.asyncio
async def test_search_finds_official_skus(client: httpx.AsyncClient) -> None:
    await seed()
    for codigo in ("SP-PLC-1X8-SCAPC", "CF-24H-BRND", "HR-MLC", "RT-67-AM"):
        response = await client.get(
            "/api/v1/materials", params={"buscar": codigo}, headers={"X-Actor": "actor-x"}
        )
        assert response.status_code == 200
        assert any(m["codigo"] == codigo for m in response.json()["materiales"])

    hidden = await client.get(
        "/api/v1/materials", params={"buscar": LEGACY_SKU}, headers={"X-Actor": "actor-x"}
    )
    assert hidden.status_code == 200
    assert hidden.json()["materiales"] == []


@pytest.mark.asyncio
async def test_kpis_count_only_active_catalog(client: httpx.AsyncClient) -> None:
    await seed()
    response = await client.get("/api/v1/kpis", headers={"X-Actor": "actor-x"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_materiales"] == 53
    assert body["stock_total"] == 0
