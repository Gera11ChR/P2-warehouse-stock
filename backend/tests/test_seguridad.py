"""RBAC — X-Actor obligatorio, scopes de sección y rechazos 403."""

import pytest
from httpx import AsyncClient


async def test_sin_header_actor_422(client_factory) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    c = AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )
    try:
        resp = await c.get("/api/v1/catalogo")
        assert resp.status_code == 422
    finally:
        await c.aclose()


@pytest.mark.critical
async def test_actor_sin_scope_403_escritura(
    client_sin_scope: AsyncClient,
) -> None:
    resp = await client_sin_scope.post(
        "/api/v1/catalogo", json={"descripcion": "Intruso"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    assert resp.json()["error"]["actor"] == "intruso"


async def test_actor_sin_scope_403_ajustes(
    client_sin_scope: AsyncClient,
) -> None:
    resp = await client_sin_scope.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 1, "material_id": 1, "cantidad": 1},
    )
    assert resp.status_code == 403


async def test_actor_con_scope_crea(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/catalogo", json={"descripcion": "Autorizado"}
    )
    assert resp.status_code == 201


async def test_listado_lectura_publica_sin_assert_scope(
    client: AsyncClient,
) -> None:
    """Caracterización: los GET de listado no exigen scope (solo header)."""
    resp = await client.get("/api/v1/catalogo")
    assert resp.status_code == 200


async def test_admin_registrado_pase_directo_sin_scope(
    client_factory, session
) -> None:
    """RBAC admin (migración 0012, tabla `administradores`): un actor listado
    como administrador opera SIN filas de scope — crea material y ejecuta
    carga inicial y ajuste administrativo (pase directo de sec-ops)."""
    from sqlalchemy import text

    await session.execute(
        text("INSERT INTO administradores (actor_id) VALUES ('admin-qa')")
    )
    await session.commit()

    admin = client_factory("admin-qa")
    try:
        resp = await admin.post(
            "/api/v1/catalogo", json={"descripcion": "Material Admin QA"}
        )
        assert resp.status_code == 201
        material_id = resp.json()["id_lista"]

        resp = await admin.post(
            "/api/v1/ajustes/carga-inicial",
            json={"almacen_id": 1, "material_id": material_id, "cantidad": 10},
        )
        assert resp.status_code == 200

        resp = await admin.post(
            "/api/v1/ajustes/stock-almacen",
            json={
                "almacen_id": 1,
                "material_id": material_id,
                "nuevo_stock": 8,
                "motivo": "Conteo físico admin",
            },
        )
        assert resp.status_code == 200
    finally:
        await admin.aclose()


async def test_actor_sin_scope_sin_admin_sigue_403(
    client_factory,
) -> None:
    """Un actor SIN filas de scope y SIN registro en administradores sigue
    recibiendo 403 en escrituras (default-deny, Constitution 3.1)."""
    c = client_factory("intruso")
    try:
        resp = await c.post(
            "/api/v1/catalogo", json={"descripcion": "Intruso otra vez"}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    finally:
        await c.aclose()
