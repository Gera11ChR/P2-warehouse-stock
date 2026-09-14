"""Bootstrap de la suite de QA — DMS - TELECOM.

Estrategia de aislamiento (FASE 5, decisión D3): TRUNCATE + resiembra.
La suite opera EXCLUSIVAMENTE sobre la base de datos `p2_test`; la BD de
desarrollo `p2` jamás es tocada. El esquema se migra con `alembic upgrade
head` (cadena completa 0001 -> 0011, idéntica a producción).

Regla crítica: P2_DATABASE_URL se fija ANTES de importar `app.*`
(app.config lee la variable en tiempo de importación).
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

ADMIN_DB_URL = os.environ.get(
    "P2_ADMIN_DATABASE_URL", "postgresql://p2admin@127.0.0.1:5432/p2"
)
TEST_DB_URL = os.environ.get(
    "P2_TEST_DATABASE_URL",
    "postgresql+psycopg://p2admin@127.0.0.1:5432/p2_test",
)

os.environ["P2_DATABASE_URL"] = TEST_DB_URL

ACTOR_QA = "qa"
ACTOR_SIN_SCOPE = "intruso"

SECCIONES_SEMILLA = [
    ("Inventario General", "GENERAL"),
    ("Fibra Optica - Paquete", "FO_PAQUETE"),
    ("Fibra Optica - En Uso", "FO_EN_USO"),
]

TABLAS_DOMINIO = [
    "inventario_equipos",
    "inventario_almacen",
    "movimientos_detalle",
    "movimientos_cabecera",
    "equipos_integrantes",
    "equipos",
    "auditoria_eventos",
    "catalogo_materiales",
    "categorias",
    "actor_almacen_scopes",
]


def _ensure_test_database() -> None:
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'p2_test'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE p2_test")
    with psycopg.connect(ADMIN_DB_URL.replace("/p2", "/p2_test"),
                         autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("GRANT ALL ON SCHEMA public TO p2admin")
            cur.execute("GRANT ALL ON DATABASE p2_test TO p2admin")


def pytest_configure(config: object) -> None:
    os.environ["P2_DATABASE_URL"] = TEST_DB_URL
    _ensure_test_database()
    env = {**os.environ, "P2_DATABASE_URL": TEST_DB_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head falló sobre p2_test:\n{result.stderr}"
        )


@pytest.fixture(autouse=True)
async def clean_db():
    """Aislamiento determinista por test: truncado de dominio + resiembra."""
    from sqlalchemy import text

    from app.db import SessionLocal

    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(
                text(
                    "TRUNCATE TABLE "
                    + ", ".join(TABLAS_DOMINIO)
                    + " RESTART IDENTITY CASCADE"
                )
            )
            for nombre, tipo in SECCIONES_SEMILLA:
                await session.execute(
                    text(
                        "INSERT INTO secciones (nombre, tipo) "
                        "VALUES (:n, :t) ON CONFLICT (nombre) DO NOTHING"
                    ),
                    {"n": nombre, "t": tipo},
                )
            await session.execute(
                text(
                    "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
                    "VALUES (:a, 1)"
                ),
                {"a": ACTOR_QA},
            )
    yield


@pytest.fixture
async def session():
    """Sesión SQLAlchemy directa para aserciones profundas (vista sparse,
    auditoría y tablas sin endpoint de escritura)."""
    from app.db import SessionLocal

    async with SessionLocal() as s:
        yield s


@pytest.fixture
async def client():
    """Cliente HTTP ASGI autenticado como actor `qa` (scope: almacén 1)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Actor": ACTOR_QA},
    ) as c:
        yield c


@pytest.fixture
async def client_sin_scope():
    """Cliente con actor SIN filas de scope (casos 403)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Actor": ACTOR_SIN_SCOPE},
    ) as c:
        yield c


@pytest.fixture
def client_factory():
    """Fábrica de clientes independientes (tests de concurrencia)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    def make(actor: str = ACTOR_QA) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Actor": actor},
        )

    return make
