"""RF-2 (saneamiento-2): IDs fuera del rango INT4 responden 400, nunca 500.

PostgreSQL rechaza el valor en el servidor con SQLSTATE `22003`
(`NumericValueOutOfRange`); un handler global lo mapea a HTTP 400 con el
cuerpo de error canónico. Cualquier otro SQLSTATE NO se enmascara.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.helpers.fabrica import (
    carga_inicial,
    crear_equipo,
    crear_material,
)

ID_GRANDE = 10**12
ID_ENORME = 10**30
IDS = [ID_GRANDE, ID_ENORME]

RUTAS_GET = [
    "/api/v1/equipos/{id}/inventario",
    "/api/v1/equipos/{id}",
    "/api/v1/equipos/{id}/seguimientos",
    "/api/v1/movimientos/{id}",
    "/api/v1/catalogo/{id}",
    "/api/v1/inventario/secciones/{id}",
]

PROHIBIDOS_EN_CUERPO = ("integer", "psycopg", "select ", "where ", "sqlstate")


def _assert_400_canonico(resp: Any) -> None:
    assert resp.status_code == 400, resp.text
    cuerpo = resp.json()
    assert set(cuerpo) == {"error"}
    error = cuerpo["error"]
    assert error["code"] == "NUMERIC_OUT_OF_RANGE"
    assert isinstance(error["message"], str) and error["message"]
    assert error["coordinates"] == []
    bajo = resp.text.lower()
    for prohibido in PROHIBIDOS_EN_CUERPO:
        assert prohibido not in bajo, prohibido


@pytest.mark.parametrize("valor", IDS)
@pytest.mark.parametrize("ruta", RUTAS_GET)
async def test_RF_2_get_id_fuera_de_rango_400(
    client_admin: AsyncClient, ruta: str, valor: int
) -> None:
    resp = await client_admin.get(ruta.format(id=valor))
    _assert_400_canonico(resp)


@pytest.mark.parametrize("valor", IDS)
async def test_RF_2_get_id_fuera_de_rango_actor_regular_400(
    client: AsyncClient, valor: int
) -> None:
    """El actor regular pasa por el chequeo de integrante (consulta con el
    ID): también debe responder 400."""
    resp = await client.get(f"/api/v1/equipos/{valor}/inventario")
    _assert_400_canonico(resp)


@pytest.mark.parametrize("valor", IDS)
async def test_RF_2_seguimiento_detalle_id_fuera_de_rango_400(
    client_admin: AsyncClient, valor: int
) -> None:
    resp = await client_admin.get(
        f"/api/v1/equipos/{valor}/seguimientos/{valor}"
    )
    _assert_400_canonico(resp)


@pytest.mark.parametrize("valor", IDS)
async def test_RF_2_auditoria_material_id_fuera_de_rango_400(
    client_admin: AsyncClient, valor: int
) -> None:
    resp = await client_admin.get(
        "/api/v1/auditoria", params={"material_id": valor}
    )
    _assert_400_canonico(resp)


@pytest.mark.parametrize("valor", IDS)
async def test_RF_2_post_movimiento_origen_fuera_de_rango_400_sin_persistir(
    client_admin: AsyncClient, session: Any, valor: int
) -> None:
    equipo = await crear_equipo(client_admin, integrantes=["admin-qa"])
    material = await crear_material(client_admin, descripcion="Mat RF2")
    resp = await client_admin.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": valor,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 1}],
        },
    )
    _assert_400_canonico(resp)
    n = (
        await session.execute(text("SELECT count(*) FROM movimientos_cabecera"))
    ).scalar()
    assert n == 0


async def test_RF_2_patch_fibra_material_fuera_de_rango_400(
    client_admin: AsyncClient,
) -> None:
    resp = await client_admin.patch(
        f"/api/v1/fibra/materiales/{ID_GRANDE}", json={"stock_minimo": 1}
    )
    _assert_400_canonico(resp)


async def test_RF_2_E3_la_solicitud_siguiente_funciona(
    client_admin: AsyncClient,
) -> None:
    """E3: tras el 400 la sesión no queda corrupta (rollback) y la siguiente
    solicitud sobre el mismo cliente responde con normalidad."""
    resp = await client_admin.get(f"/api/v1/equipos/{ID_GRANDE}/inventario")
    assert resp.status_code == 400
    material = await crear_material(client_admin, descripcion="Post-400")
    resp = await client_admin.get("/api/v1/catalogo")
    assert resp.status_code == 200
    assert [m["id_lista"] for m in resp.json()["materiales"]] == [
        material["id_lista"]
    ]
    resp = await client_admin.get(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 200


async def test_RF_2_dominio_transaccional_conserva_su_mensaje(
    client: AsyncClient,
) -> None:
    """El mapeo 22003 propio de `services/transaccional.py` (desborde de
    NUMERIC dentro de una stored function) conserva su código y mensaje de
    dominio: `BusinessRuleError` se lanza antes que el handler global."""
    material = await crear_material(client, descripcion="Mat dominio")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=999999999.999
    )
    resp = await client.post(
        "/api/v1/inventario/sumar-cantidad",
        json={
            "destino": "GENERAL",
            "material_id": material["id_lista"],
            "cantidad": 0.001,
        },
    )
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert error["code"] == "BUSINESS_RULE_VIOLATION"
    assert "excede el rango soportado" in error["message"]


async def test_RF_2_23505_conserva_409_por_ruta_real(
    client_admin: AsyncClient,
) -> None:
    """R3: una violación UNIQUE no pasa por el handler de 22003."""
    await client_admin.post("/api/v1/catalogo/categorias", json={"nombre": "Dup"})
    resp = await client_admin.post(
        "/api/v1/catalogo/categorias", json={"nombre": "Dup"}
    )
    assert resp.status_code == 409, resp.text


# ── Unidad del handler: el predicado es EXCLUSIVO por SQLSTATE ──────────


def _dbapi(sqlstate: str | None, cls: type[DBAPIError] = DBAPIError) -> DBAPIError:
    orig = SimpleNamespace(sqlstate=sqlstate) if sqlstate is not None else None
    return cls("SELECT secreto", {}, orig)  # type: ignore[arg-type]


async def test_RF_2_handler_22003_responde_400_fijo() -> None:
    from app.main import dbapi_error_handler

    exc = _dbapi("22003")
    resp = await dbapi_error_handler(None, exc)  # type: ignore[arg-type]
    assert resp.status_code == 400
    assert b"secreto" not in resp.body and b"SELECT" not in resp.body


@pytest.mark.parametrize("sqlstate", ["23505", "23503", "22P02", "P0001", None])
async def test_RF_2_handler_otro_sqlstate_se_relanza(
    sqlstate: str | None,
) -> None:
    from app.main import dbapi_error_handler

    exc = _dbapi(sqlstate)
    with pytest.raises(DBAPIError) as info:
        await dbapi_error_handler(None, exc)  # type: ignore[arg-type]
    assert info.value is exc


async def test_RF_2_handler_integrity_error_23505_se_relanza() -> None:
    from app.main import dbapi_error_handler

    exc = _dbapi("23505", IntegrityError)
    with pytest.raises(IntegrityError):
        await dbapi_error_handler(None, exc)  # type: ignore[arg-type]
