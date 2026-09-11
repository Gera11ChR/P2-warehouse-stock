import os

import psycopg

ADMIN_DB_URL = os.environ.get(
    "P2_ADMIN_DATABASE_URL", "postgresql://p2admin@127.0.0.1:5432/p2"
)
TEST_DB_URL = os.environ.get(
    "P2_TEST_DATABASE_URL", "postgresql+psycopg://p2admin@127.0.0.1:5432/p2_test"
)


def _ensure_test_database() -> None:
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'p2_test'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE p2_test")


def pytest_configure(config: object) -> None:
    os.environ["P2_DATABASE_URL"] = TEST_DB_URL
    _ensure_test_database()
