from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from app.config import DATABASE_URL

SYNC_URL = DATABASE_URL.replace("+psycopg://", "://", 1)


def _cfg() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _upgrade(revision: str) -> None:
    command.upgrade(_cfg(), revision)


def _downgrade(revision: str) -> None:
    command.downgrade(_cfg(), revision)


def _rows(query: str, params: tuple = ()) -> list:
    with psycopg.connect(SYNC_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def test_expand_backfill_quarantine_and_rollback() -> None:
    _downgrade("base")
    _upgrade("0001")

    with psycopg.connect(SYNC_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE skus DROP CONSTRAINT ck_skus_current_stock_non_negative"
            )
            for sku, stock in [("A-100", 10), ("B-200", 0), ("C-300", -5), ("D-400", 3)]:
                cur.execute(
                    "INSERT INTO skus (sku, current_stock) VALUES (%s, %s)",
                    (sku, stock),
                )

    _upgrade("0002")

    assert _rows(
        "SELECT sku, on_hand_quantity FROM warehouse_inventory ORDER BY sku"
    ) == [("A-100", 10), ("B-200", 0), ("D-400", 3)]
    assert _rows(
        "SELECT sku, current_stock, reason FROM legacy_stock_quarantine"
    ) == [("C-300", -5, "NEGATIVE_LEGACY_STOCK")]
    assert sorted(r[0] for r in _rows("SELECT sku FROM skus")) == [
        "A-100",
        "B-200",
        "C-300",
        "D-400",
    ]
    assert _rows("SELECT warehouse_id, name FROM warehouses") == [
        ("CENTRAL", "Central Warehouse")
    ]

    _downgrade("0001")

    assert _rows("SELECT sku FROM warehouse_inventory") == []
    assert _rows("SELECT warehouse_id FROM warehouses") == []
    assert sorted(r[0] for r in _rows("SELECT sku FROM skus")) == [
        "A-100",
        "B-200",
        "C-300",
        "D-400",
    ]
    with pytest.raises(psycopg.errors.UndefinedTable):
        _rows("SELECT 1 FROM legacy_stock_quarantine LIMIT 1")

    _upgrade("0002")

    assert _rows(
        "SELECT sku, on_hand_quantity FROM warehouse_inventory ORDER BY sku"
    ) == [("A-100", 10), ("B-200", 0), ("D-400", 3)]
    assert _rows(
        "SELECT sku, current_stock, reason FROM legacy_stock_quarantine"
    ) == [("C-300", -5, "NEGATIVE_LEGACY_STOCK")]
    assert _rows("SELECT warehouse_id, name FROM warehouses") == [
        ("CENTRAL", "Central Warehouse")
    ]
