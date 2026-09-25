"""Buscador a granel — posicionamiento ordinal determinista y rangos por
descripción (REQ-UI-007, REQ-API-006/007).

El backend resuelve 100 % el posicionamiento: ORDER BY descripcion ASC,
id_lista ASC, OFFSET = X - 1, LIMIT = Y - X + 1 y start_index = X.
Los filtros (descripción incluida) aplican ANTES del OFFSET/LIMIT.
"""

import pytest
from httpx import AsyncClient

from tests.helpers.fabrica import crear_material

# Descripciones ordenables: el orden determinista ASC esperado es:
# Alfa, Beta, Delta, Epsilon, Gamma
DESCRIPCIONES = ["Gamma", "Alfa", "Epsilon", "Beta", "Delta"]


async def _poblar_catalogo(client: AsyncClient) -> list[dict]:
    materiales = []
    for desc in DESCRIPCIONES:
        materiales.append(
            await crear_material(client, descripcion=desc, codigo=f"BK-{desc}")
        )
    return materiales


async def _listar(client: AsyncClient, **params) -> dict:
    resp = await client.get("/api/v1/catalogo", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_rango_ordinal_determinista(
    client: AsyncClient,
) -> None:
    """REQ-API-006: desde_numero_lista=2 & hasta_numero_lista=3 →
    start_index=2, len=2 y orden determinista (descripcion ASC, id_lista ASC)."""
    await _poblar_catalogo(client)

    payload = await _listar(
        client, desde_numero_lista=2, hasta_numero_lista=3
    )
    assert payload["start_index"] == 2
    descripciones = [m["descripcion"] for m in payload["materiales"]]
    assert descripciones == ["Beta", "Delta"]
    assert len(payload["materiales"]) == 2


async def test_solo_hasta_numero_lista_limita(client: AsyncClient) -> None:
    """REQ-API-006: solo hasta_numero_lista=2 → las 2 primeras filas
    (desde implícito = 1: OFFSET 0, LIMIT 2)."""
    await _poblar_catalogo(client)

    payload = await _listar(client, hasta_numero_lista=2)
    descripciones = [m["descripcion"] for m in payload["materiales"]]
    assert len(descripciones) == 2
    assert descripciones == ["Alfa", "Beta"]
    assert payload["start_index"] == 1


async def test_solo_desde_numero_lista_desplaza(client: AsyncClient) -> None:
    """REQ-API-006: solo desde_numero_lista=4 → OFFSET 3 desde el orden
    determinista y start_index=4."""
    await _poblar_catalogo(client)

    payload = await _listar(client, desde_numero_lista=4)
    descripciones = [m["descripcion"] for m in payload["materiales"]]
    assert descripciones == ["Epsilon", "Gamma"]
    assert payload["start_index"] == 4


async def test_rango_invertido_422(client: AsyncClient) -> None:
    await _poblar_catalogo(client)
    resp = await client.get(
        "/api/v1/catalogo",
        params={"desde_numero_lista": 4, "hasta_numero_lista": 2},
    )
    assert resp.status_code == 422


async def test_desde_numero_lista_cero_422(client: AsyncClient) -> None:
    await _poblar_catalogo(client)
    resp = await client.get(
        "/api/v1/catalogo", params={"desde_numero_lista": 0}
    )
    assert resp.status_code == 422


async def test_rango_descripcion_lexicografico(client: AsyncClient) -> None:
    """REQ-API-007: desde_descripcion/hasta_descripcion aplican un rango
    lexicográfico determinista sobre la descripción (inclusivo; "Gamma" >
    "G", por lo que queda fuera del rango [B, G])."""
    await _poblar_catalogo(client)

    payload = await _listar(
        client, desde_descripcion="B", hasta_descripcion="G"
    )
    descripciones = {m["descripcion"] for m in payload["materiales"]}
    assert descripciones == {"Beta", "Delta", "Epsilon"}
    assert "Alfa" not in descripciones
    assert "Gamma" not in descripciones


async def test_filtro_descripcion_antes_de_offset(
    client: AsyncClient,
) -> None:
    """REQ-API-006/007: el filtro por descripción aplica ANTES del
    OFFSET/LIMIT ordinal (el paginado opera sobre el subconjunto filtrado)."""
    await _poblar_catalogo(client)

    # Subconjunto filtrado (orden ASC): Beta, Delta, Epsilon, Gamma
    payload = await _listar(
        client,
        desde_descripcion="B",
        hasta_descripcion="G",
        desde_numero_lista=2,
        hasta_numero_lista=3,
    )
    descripciones = [m["descripcion"] for m in payload["materiales"]]
    assert descripciones == ["Delta", "Epsilon"]
    assert payload["start_index"] == 2


async def test_sin_rangos_ordinales_comportamiento_historico(
    client: AsyncClient,
) -> None:
    """Sin parámetros ordinales se conserva el orden por id_lista ASC y
    start_index=1 (comportamiento histórico del listado)."""
    materiales = await _poblar_catalogo(client)
    payload = await _listar(client)
    assert payload["start_index"] == 1
    ids = [m["id_lista"] for m in payload["materiales"]]
    assert ids == sorted(m["id_lista"] for m in materiales)
    assert len(ids) == 5
