"""Bootstrap de la suite SQL de la Fase 1 (T1.7) — cambio
2026-10-01-reportes-consumo-management.

Suite 100 % SQL (psycopg directo a PostgreSQL 18.6) sobre `p2_test`:
valida las migraciones 0016-0020 y los Stored Procedures nuevos
(fn_sumar_cantidad, fn_mover_material, fn_agregar_todo_seguimiento,
fn_cerrar_seguimiento extendido y el trigger tg_acta_entrega).

INDEPENDIENTE de tests/conftest.py (la suite de la app FastAPI queda a
cargo de la Fase 2, que renombra la capa API). Las pruebas se ejecutan
estrictamente SECUENCIALES (sin pytest-xdist): el único paralelismo es el
INDUCIDO dentro de los tests de concurrencia FOR UPDATE, por diseño.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Sin credenciales hardcodeadas (A-1, dictamen sec-ops): las URLs las
# provee el entorno (runner) y su ausencia ABORTA la suite.
try:
    ADMIN_DB_URL = os.environ["P2_ADMIN_DATABASE_URL"]
    TEST_DB_URL = os.environ["P2_TEST_DATABASE_URL"]
except KeyError as exc:
    raise RuntimeError(
        f"Variable de entorno obligatoria ausente: {exc}. "
        "Ejecuta la suite vía el runner que exporta las URLs derivadas de "
        "backend/.env (nunca las hardcodees aquí)."
    ) from exc

# URL nativa psycopg (sin el driver "+psycopg" de SQLAlchemy).
PSYCOPG_TEST_URL = TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://")

ACTOR_QA = "qa"

SECCIONES_SEMILLA = [
    ("Inventario General", "GENERAL", True),
    # Sección única de ruteo FO.
    ("Inventario FO", "FO", False),
]

UMS_SEMILLA = [
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
]

TABLAS_DOMINIO = [
    "actas_reportes",
    "actividades_reportes",
    "operaciones_idempotencia",
    "seguimiento_items",
    "seguimientos",
    "equipo_material_config",
    "referencia_materiales",
    "ums",
    "inventario_equipos",
    "inventario_almacen",
    "inventario_fibra",
    "movimientos_detalle",
    "movimientos_cabecera",
    "equipos_integrantes",
    "equipos",
    "auditoria_eventos",
    "catalogo_materiales",
    "categorias",
    "actor_almacen_scopes",
    "administradores",
]


def pytest_configure(config: object) -> None:
    """Aplica la cadena de migraciones completa (0001 -> head, incl. 0027) sobre
    p2_test antes de recolectar las pruebas — valida las migraciones de la
    Fase 1 en cada ejecución."""
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


@pytest.fixture
def conn():
    """Conexión psycopg en autocommit: cada sentencia (y cada invocación de
    SP) transacciona de forma independiente, por lo que un RAISE EXCEPTION
    de un SP nunca deja la sesión abortada para el siguiente assert."""
    with psycopg.connect(PSYCOPG_TEST_URL, autocommit=True) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_dominio(conn):
    """Aislamiento determinista por test: truncado del dominio +
    resiembra (secciones y U.M. maestras)."""
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE TABLE " + ", ".join(TABLAS_DOMINIO) + " RESTART IDENTITY CASCADE"
        )
        for nombre, tipo, activa in SECCIONES_SEMILLA:
            cur.execute(
                "INSERT INTO secciones (nombre, tipo, is_active) "
                "VALUES (%s, %s, %s) ON CONFLICT (nombre) DO NOTHING",
                (nombre, tipo, activa),
            )
        for nombre in UMS_SEMILLA:
            cur.execute(
                "INSERT INTO ums (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
                (nombre,),
            )
    yield
