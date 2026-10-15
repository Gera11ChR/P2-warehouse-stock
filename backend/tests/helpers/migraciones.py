"""Infraestructura para pruebas de migración Alembic IN-PLACE sobre `p2_test`.

Contexto: el rol `p2admin` de QA no posee CREATEDB en el clúster del
proyecto, por lo que las pruebas de migración NO pueden crear bases
temporales (el patrón anterior de BD aparte fallaba con
"InsufficientPrivilege: permission denied to create database"). Esta
infraestructura opera sobre la BD compartida `p2_test` (la única que el
conftest crea/migra) con la siguiente disciplina:

  1. `migrar_hasta(revision)` ejecuta `alembic downgrade/upgrade` contra
     `p2_test` vía subprocess (patrón de `tests/conftest.py`).
  2. La siembra/verificación usa `psycopg` síncrono directo sobre `p2_test`.
  3. El context manager `esquema_en(revision)` GARANTIZA en `finally` la
     restauración de la cabeza (`alembic upgrade head`) aunque la prueba
     falle: la suite jamás queda con el esquema degradado.

Las pruebas de migración son funciones síncronas (`def`, no `async def`)
— no tocan el event loop de pytest-asyncio — y el fixture autouse
`clean_db` de conftest les garantiza el truncado de las tablas de dominio
antes de empezar (estado vacío determinista).
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from sqlalchemy.engine import make_url

from tests.conftest import ADMIN_DB_URL

BACKEND_DIR = Path(__file__).resolve().parents[2]

# URL de p2_test derivada de P2_ADMIN_DATABASE_URL (nunca hardcodeada):
# misma BD que crea/migra `_ensure_test_database` de conftest.
PSY_TEST_URL = make_url(ADMIN_DB_URL).set(
    database="p2_test"
).render_as_string(hide_password=False)
SA_TEST_URL = make_url(ADMIN_DB_URL).set(
    drivername="postgresql+psycopg", database="p2_test"
).render_as_string(hide_password=False)


def alembic(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    """Ejecuta `python -m alembic <args>` contra p2_test (env P2_DATABASE_URL).

    Con `ok=True` asevera returncode == 0; con `ok=False` devuelve el
    resultado crudo para aseverar ABORTOS controlados (E14 / mixtos 0026).
    """
    env = {**os.environ, "P2_DATABASE_URL": SA_TEST_URL}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if ok:
        assert r.returncode == 0, r.stderr[-2000:]
    return r


def sql(query: str, params: tuple | None = None) -> list[tuple]:
    """Consulta síncrona sobre p2_test (siembra y aserciones de migración)."""
    with psycopg.connect(PSY_TEST_URL, autocommit=True) as c:
        with c.cursor() as cur:
            cur.execute(query, params)
            if cur.description is not None:
                return cur.fetchall()
            return []


@contextmanager
def esquema_en(revision: str) -> Iterator[None]:
    """Lleva p2_test a `revision` y GARANTIZA la restauración a `head` al
    salir (éxito, fallo o aborto de la prueba)."""
    try:
        if revision != "head":
            alembic("downgrade", revision)
        yield
    finally:
        # Restauración determinista de la cabeza de la cadena; si el
        # downgrade abortó a mitad, upgrade head re-aplica desde la
        # revisión viva de alembic_version (idempotente).
        alembic("upgrade", "head")
