"""Zona de negocio de los reportes de actividades — `P2_REPORTES_TZ` (T4,
paquete 2026-10-actividades-reportes; plan D-2/F-13).

La zona con la que se interpretan `desde`/`hasta` (REQ-REP-004) y se
imprime la FECHA del XLSX (REQ-REP-007) se lee de `P2_REPORTES_TZ` con el
valor por defecto `America/Mexico_City` (C-1) y se valida al importar
`app.config`: una zona inválida impide el arranque del servidor. El grueso
de pruebas de la API de reportes de actividades es T6.
"""

import os
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_reporte_tz_por_defecto_es_mexico_city_y_es_valida() -> None:
    """REQ-REP-004, C-1: por defecto la zona de negocio es
    `America/Mexico_City` y es una zona válida para `zoneinfo` (si no lo
    fuera, el propio import de app.config ya habría lanzado)."""
    import app.config as cfg

    assert cfg.REPORTES_TZ == "America/Mexico_City"
    ZoneInfo(cfg.REPORTES_TZ)  # no debe lanzar


async def test_zona_configurada_existe_en_pg_timezone_names(
    session: AsyncSession,
) -> None:
    """D-2: la zona de negocio vigente existe en el catálogo IANA de
    PostgreSQL (`pg_timezone_names`), condición para que el filtro
    `timezone(zona, …)` de la consulta la resuelva."""
    import app.config as cfg

    resultado = await session.execute(
        text("SELECT count(*) FROM pg_timezone_names WHERE name = :z"),
        {"z": cfg.REPORTES_TZ},
    )
    assert resultado.scalar() == 1


def test_zona_invalida_impide_el_arranque() -> None:
    """F-13: una zona inválida en `P2_REPORTES_TZ` rompe el import de
    `app.config` (ZoneInfoNotFoundError) y, con él, el arranque del
    servidor. Se fuerza la variable en un subproceso que hereda el resto
    del entorno actual (incluido el PYTHONPATH del repo) y se ejecuta con
    `cwd=BACKEND_DIR` para que resuelva `app`."""
    env = {**os.environ, "P2_REPORTES_TZ": "Zona/Inexistente"}
    resultado = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode != 0
