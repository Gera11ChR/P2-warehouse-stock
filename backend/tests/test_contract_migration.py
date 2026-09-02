from pathlib import Path

import psycopg
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


def test_contract_drop_and_downgrade_reconstruction() -> None:
    _downgrade("base")
    _upgrade("0002")

    with psycopg.connect(SYNC_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO skus (sku, current_stock) "
                "VALUES ('A-100', 10), ('B-200', 5), ('C-300', 0)"
            )
            cur.execute(
                "INSERT INTO warehouses (warehouse_id, name) "
                "VALUES ('WH-1', 'Warehouse One'), ('WH-2', 'Warehouse Two')"
            )
            cur.execute(
                "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
                "VALUES ('WH-1', 'A-100', 7), ('WH-2', 'A-100', 3), ('WH-1', 'B-200', 5)"
            )

    _upgrade("head")

    assert _rows(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'skus' AND column_name = 'current_stock'"
    ) == [(0,)]

    _downgrade("0002")

    assert _rows("SELECT sku, current_stock FROM skus ORDER BY sku") == [
        ("A-100", 10),
        ("B-200", 5),
        ("C-300", 0),
    ]
    assert _rows(
        "SELECT count(*) FROM pg_constraint "
        "WHERE conname = 'ck_skus_current_stock_non_negative'"
    ) == [(1,)]
