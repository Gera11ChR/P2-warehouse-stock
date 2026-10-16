"""Regenera y verifica `backend/db/ddl.sql` (snapshot schema-only del esquema
vigente, referencia NO ejecutable sobre bases reales).

Uso (desde `backend/`):

    uv run python scripts/generar_ddl.py            # regenera db/ddl.sql
    uv run python scripts/generar_ddl.py --verificar  # compara sin escribir

Fuente: la base de pruebas `p2_test` llevada a la cabeza de Alembic (la misma
cadena que aplica la suite). Credenciales: `P2_TEST_DATABASE_URL` o, si no
está definida, `P2_DATABASE_URL` de `backend/.env` con la base `p2_test`. La
contraseña viaja por `PGPASSWORD` (nunca en la línea de comandos) y no se
escribe en el archivo. La cabecera no contiene host, rol ni credenciales.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
DDL = BACKEND / "db" / "ddl.sql"
MARCA_FIN_CABECERA = "-- ===== FIN DE CABECERA (contenido generado por pg_dump) ====="


def _url() -> object:
    crudo = os.environ.get("P2_TEST_DATABASE_URL")
    if not crudo:
        for linea in (BACKEND / ".env").read_text().splitlines():
            linea = linea.strip()
            if linea.startswith("P2_DATABASE_URL="):
                crudo = linea.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not crudo:
        sys.exit("No hay P2_TEST_DATABASE_URL ni P2_DATABASE_URL en backend/.env")
    url = make_url(crudo)
    return url.set(database="p2_test")


def _volcar(url: object) -> tuple[str, str]:
    u = url  # type: ignore[assignment]
    env = {**os.environ, "PGPASSWORD": u.password or ""}  # type: ignore[attr-defined]
    cmd = [
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "-h", str(u.host or "127.0.0.1"),  # type: ignore[attr-defined]
        "-p", str(u.port or 5432),  # type: ignore[attr-defined]
        "-U", str(u.username),  # type: ignore[attr-defined]
        str(u.database),  # type: ignore[attr-defined]
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pg_dump falló (¿PostgreSQL disponible?): " + r.stderr.strip()[:300])
    version = subprocess.run(
        ["pg_dump", "--version"], capture_output=True, text=True
    ).stdout.strip()
    return r.stdout, version


def _revision(url: object) -> str:
    import psycopg

    u = url  # type: ignore[assignment]
    with psycopg.connect(
        host=u.host or "127.0.0.1",  # type: ignore[attr-defined]
        port=u.port or 5432,  # type: ignore[attr-defined]
        user=u.username,  # type: ignore[attr-defined]
        password=u.password,  # type: ignore[attr-defined]
        dbname=u.database,  # type: ignore[attr-defined]
    ) as c:
        return str(c.execute("SELECT version_num FROM alembic_version").fetchone()[0])  # type: ignore[index]


_RUIDO = (
    re.compile(r"^SET [a-z_.]+ = .*;$"),
    re.compile(r"^SELECT pg_catalog\.set_config\(.*\);$"),
    re.compile(r"^\\(un)?restrict\b.*$"),
    re.compile(r"^-- Dumped (from database version|by pg_dump version).*$"),
)


def _normalizar(volcado: str) -> str:
    salida: list[str] = []
    for linea in volcado.splitlines():
        if any(p.match(linea) for p in _RUIDO):
            continue
        salida.append(linea.rstrip())
    texto = "\n".join(salida)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip("\n")
    return texto + "\n"


def _cabecera(revision: str, version_pg: str) -> str:
    return f"""-- Software Design Document (SDD) - DMS - TELECOM
-- Snapshot SCHEMA-ONLY del esquema vigente (cabeza Alembic {revision}).
--
-- >>> REFERENCIA, NO EJECUTABLE sobre bases reales: la fuente de verdad del
-- >>> esquema son las migraciones Alembic (`backend/alembic/versions/`).
-- >>> Este archivo es una instantánea de lectura (tablas, restricciones,
-- >>> funciones y triggers); se regenera y se verifica con
-- >>> `backend/scripts/generar_ddl.py`.
--
-- Generado: {date.today().isoformat()} con {version_pg}
-- Comando : pg_dump --schema-only --no-owner --no-privileges  (base de pruebas
--           llevada a la cabeza {revision}; sin host, rol ni credenciales)
{MARCA_FIN_CABECERA}

"""


def main() -> None:
    verificar = "--verificar" in sys.argv[1:]
    url = _url()
    volcado, version_pg = _volcar(url)
    cuerpo = _normalizar(volcado)
    revision = _revision(url)
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cabeza = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_current_head()
    if revision != cabeza:
        sys.exit(f"La base fuente está en {revision} y la cabeza es {cabeza}; ejecuta alembic upgrade head.")

    if verificar:
        actual = DDL.read_text()
        if MARCA_FIN_CABECERA not in actual:
            sys.exit("ddl.sql no tiene la marca de cabecera: regenerar.")
        esperado = actual.split(MARCA_FIN_CABECERA, 1)[1].lstrip("\n")
        if esperado == cuerpo:
            print(f"OK: ddl.sql coincide con el esquema {revision}.")
            return
        sys.exit("DIFERENCIA: ddl.sql no coincide con el esquema vigente; regenerar.")

    DDL.write_text(_cabecera(revision, version_pg) + cuerpo)
    print(f"ddl.sql regenerado ({len(cuerpo.splitlines())} líneas, cabeza {revision}).")


if __name__ == "__main__":
    main()
