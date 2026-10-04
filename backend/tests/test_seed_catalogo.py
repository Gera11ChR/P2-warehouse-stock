"""Cobertura automatizada del seed del catálogo oficial (REQ-SANE-007/008).

El script `scripts/seed_catalogo_oficial.py` NO se modifica: los casos
ejercitan su `main()` real contra la base aislada `p2_test` (conftest fija
`P2_DATABASE_URL` antes de cualquier import de `app.*`) y verifican:

  * Idempotencia: dos corridas consecutivas dejan 53 filas de inventario
    intactas (stock 5), exactamente 53 eventos `STOCK_INICIAL` y cero
    cargas nuevas en la segunda corrida (REQ-SANE-007).
  * Aserción final `== 53`: con un catálogo que no suma 53, `main()`
    levanta `RuntimeError` (REQ-SANE-008). El listado se altera vía
    monkeypatch; la lógica interna del script queda intacta.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import AuditoriaEvento, CatalogoMaterial, InventarioAlmacen

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import seed_catalogo_oficial as seed  # type: ignore[import-not-found]  # noqa: E402


async def test_seed_es_idempotente_dos_corridas(session) -> None:
    """REQ-SANE-007: la segunda corrida no duplica cargas ni eventos."""
    await seed.main()
    await seed.main()

    filas = (await session.execute(select(InventarioAlmacen))).scalars().all()
    assert len(filas) == 53
    assert {f.stock_actual for f in filas} == {5}

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "STOCK_INICIAL"
            )
        )
    ).scalars().all()
    assert len(eventos) == 53

    activos = (
        await session.execute(
            select(func.count())
            .select_from(CatalogoMaterial)
            .where(CatalogoMaterial.is_active.is_(True))
        )
    ).scalar_one()
    assert activos == 53


async def test_seed_assert_53_falla_con_catalogo_incompleto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-SANE-008: el conteo final distinto de 53 levanta RuntimeError."""
    monkeypatch.setattr(seed, "MATERIALES", seed.MATERIALES[:-1])
    with pytest.raises(RuntimeError, match="!= 53"):
        await seed.main()
