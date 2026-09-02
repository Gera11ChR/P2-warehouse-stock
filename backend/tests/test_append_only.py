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


def test_ledger_append_only_enforcement_and_derived_view() -> None:
    _downgrade("base")
    _upgrade("head")

    with psycopg.connect(SYNC_URL, autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'p2_app') THEN "
            "CREATE ROLE p2_app; "
            "END IF; END $$;"
        )
        cur.execute("GRANT ALL ON SCHEMA public TO p2_app")
        cur.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO p2_app"
        )
        cur.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO p2_app")
        cur.execute("GRANT SELECT ON current_stock_view TO p2_app")
        cur.execute("REVOKE UPDATE, DELETE ON stock_movements, audit_logs FROM p2_app")

        cur.execute("SET ROLE p2_app")
        cur.execute("INSERT INTO skus (sku) VALUES ('X-1')")
        cur.execute(
            "INSERT INTO warehouses (warehouse_id, name) VALUES ('WH-9', 'WH Nine')"
        )
        cur.execute(
            "INSERT INTO warehouse_inventory (warehouse_id, sku, on_hand_quantity) "
            "VALUES ('WH-9', 'X-1', 5)"
        )
        cur.execute(
            "INSERT INTO stock_movements "
            "(warehouse_id, sku, quantity_change, movement_type, actor_id) "
            "VALUES ('WH-9', 'X-1', 5, 'RECEIPT', 'actor-1')"
        )
        cur.execute(
            "INSERT INTO audit_logs (action, actor, details) "
            "VALUES ('STOCK_ADJUST', 'actor-1', '{}')"
        )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE stock_movements SET quantity_change = 999")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM stock_movements")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("UPDATE audit_logs SET action = 'MUTATED'")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM audit_logs")

        cur.execute("RESET ROLE")
        assert conn.execute(
            "SELECT count(*) FROM pg_class c, aclexplode(c.relacl) a "
            "WHERE c.relname IN ('stock_movements', 'audit_logs') "
            "AND a.grantee = 0 AND a.privilege_type IN ('UPDATE', 'DELETE')"
        ).fetchone() == (0,)

        assert conn.execute(
            "SELECT sku, current_stock FROM current_stock_view ORDER BY sku"
        ).fetchall() == [("X-1", 5)]
