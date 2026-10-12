"""Nomenclatura Equipo -> Unidad (paquete 2026-10-12-equipo-a-unidad).

Verifica RF-6/RF-7/RF-8 (REQ-UNI-006/007/008) del backend:

* REQ-UNI-006: el `detail`/`message` de los errores de la API dice "Unidad".
* REQ-UNI-007: los RAISE EXCEPTION de las funciones almacenadas dicen
  "unidad" y el mapeo de errores conserva los códigos HTTP (404/400/409),
  tolerando además el texto antiguo durante la transición.
* REQ-UNI-008: el contrato (rutas, métodos, campos) no cambia.

Los identificadores técnicos (`/equipos`, `equipo_id`) NO se renombran
(REQ-UNI-005).
"""

import re
from types import SimpleNamespace
from typing import Any, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.errors import BusinessRuleError
from app.services import transaccional
from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    procesar,
)

PALABRA_ANTIGUA = re.compile(r"equipo", re.IGNORECASE)


def _mensaje(resp: Any) -> str:
    return str(resp.json()["error"]["message"])


def _sin_equipo(mensaje: str) -> None:
    assert not PALABRA_ANTIGUA.search(mensaje), mensaje


# ── REQ-UNI-006: mensajes `detail` de la API ──────────────────────────────


async def test_REQ_UNI_006_get_unidad_inexistente(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/equipos/9999")
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_inventario_unidad_inexistente(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/v1/equipos/9999/inventario")
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_patch_unidad_inexistente(client: AsyncClient) -> None:
    resp = await client.patch("/api/v1/equipos/9999", json={"nombre": "X"})
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_delete_unidad_inexistente(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/equipos/9999")
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_config_local_unidad_inexistente(
    client: AsyncClient,
) -> None:
    resp = await client.patch(
        "/api/v1/equipos/9999/inventario/1", json={"stock_minimo_local": 3}
    )
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_seguimiento_unidad_inexistente(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/equipos/9999/seguimientos",
        json={"items": [{"material_id": 1, "cantidad_tomada": 1}]},
    )
    assert resp.status_code == 404
    assert _mensaje(resp) == "Unidad no encontrada"


async def test_REQ_UNI_006_transferencia_unidad_destino_inexistente(
    client: AsyncClient,
) -> None:
    material = await crear_material(client, descripcion="Mat UNI")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": 1,
            "destino_equipo_id": 9999,
            "detalle": [{"material_id": material["id_lista"], "cantidad": 1}],
        },
    )
    assert resp.status_code == 422
    assert _mensaje(resp) == "Unidad destino inexistente"


async def test_REQ_UNI_006_devolucion_unidad_origen_inexistente(
    client: AsyncClient,
) -> None:
    material = await crear_material(client, descripcion="Mat UNI 2")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": 9999,
            "destino_almacen_id": 1,
            "detalle": [{"material_id": material["id_lista"], "cantidad": 1}],
        },
    )
    assert resp.status_code == 422
    assert _mensaje(resp) == "Unidad origen inexistente"


async def test_REQ_UNI_006_acceso_denegado_a_unidad_403(
    client: AsyncClient, client_factory
) -> None:
    equipo = await crear_equipo(client, nombre="Unidad ajena", integrantes=["otro"])
    ajeno = client_factory("ajeno")
    async with ajeno:
        resp = await ajeno.get(f"/api/v1/equipos/{equipo['equipo_id']}/inventario")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    assert _mensaje(resp) == "El actor no tiene acceso a esta unidad"


# ── REQ-UNI-007: errores de funciones almacenadas (end-to-end) ────────────


async def _unidad_con_stock(client: AsyncClient, cantidad: int) -> tuple[dict, dict]:
    material = await crear_material(client, descripcion="Mat stock UNI")
    equipo = await crear_equipo(client, nombre="Unidad stock")
    await carga_inicial(client, material_id=material["id_lista"], cantidad=100)
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=cantidad,
    )
    await procesar(client, b["id"])
    return material, equipo


async def test_REQ_UNI_007_cierre_stock_insuficiente_400(
    client: AsyncClient,
) -> None:
    material, equipo = await _unidad_con_stock(client, 30)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": 50}]},
    )
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{sid}/cerrar",
        json={"consumidos": [{"material_id": material["id_lista"], "cantidad_consumida": 50}]},
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en la Unidad" in _mensaje(resp)
    _sin_equipo(_mensaje(resp))


async def test_REQ_UNI_007_seguimiento_abierto_duplicado_409(
    client: AsyncClient,
) -> None:
    material, equipo = await _unidad_con_stock(client, 30)
    payload = {"items": [{"material_id": material["id_lista"], "cantidad_tomada": 1}]}
    url = f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos"
    assert (await client.post(url, json=payload)).status_code == 201
    resp = await client.post(url, json=payload)
    assert resp.status_code == 409
    assert "La unidad ID" in _mensaje(resp)
    assert "ya posee un seguimiento abierto" in _mensaje(resp)


async def test_REQ_UNI_007_devolucion_sin_stock_400(client: AsyncClient) -> None:
    material, equipo = await _unidad_con_stock(client, 10)
    b1 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=1,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b2["id"]}
    )
    assert resp.status_code == 400
    assert "La unidad ID" in _mensaje(resp)
    assert "no cuenta con stock suficiente" in _mensaje(resp)
    _sin_equipo(_mensaje(resp))


async def test_REQ_UNI_007_cancelacion_revertir_sin_stock_400(
    client: AsyncClient,
) -> None:
    material = await crear_material(client, descripcion="Mat cancel UNI")
    equipo = await crear_equipo(client, nombre="Unidad cancel")
    await carga_inicial(client, material_id=material["id_lista"], cantidad=50)
    b1 = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=1,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])
    resp = await client.post(
        f"/api/v1/movimientos/{b1['id']}/cancelar", json={"motivo": "Revertir"}
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en la Unidad destino" in _mensaje(resp)
    _sin_equipo(_mensaje(resp))


# ── REQ-UNI-007: texto de los RAISE en la BD ──────────────────────────────

_RAISE = re.compile(r"RAISE\s+EXCEPTION\s+'((?:[^']|'')*)'", re.IGNORECASE)


async def test_REQ_UNI_007_funciones_almacenadas_sin_literal_equipo(session) -> None:
    filas = (
        await session.execute(
            text(
                "SELECT p.proname, pg_get_functiondef(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.prokind = 'f' "
                "AND p.proname LIKE 'fn\\_%'"
            )
        )
    ).all()
    nombres = {f[0] for f in filas}
    for requerida in (
        "fn_procesar_movimiento",
        "fn_cancelar_movimiento",
        "fn_crear_seguimiento",
        "fn_cerrar_seguimiento",
        "fn_agregar_todo_seguimiento",
    ):
        assert requerida in nombres, requerida

    ofensores = [
        (nombre, literal)
        for nombre, definicion in filas
        for literal in _RAISE.findall(definicion)
        if PALABRA_ANTIGUA.search(literal)
    ]
    assert ofensores == []


# ── REQ-UNI-007: mapeo de errores (404/400/409) con ambas variantes ───────


def _error_pg(mensaje: str) -> DBAPIError:
    orig = SimpleNamespace(diag=SimpleNamespace(message_primary=mensaje))
    return cast(DBAPIError, SimpleNamespace(orig=orig))


@pytest.mark.parametrize(
    ("mensaje", "status"),
    [
        ("El seguimiento ID 1 no pertenece a la unidad ID 2.", 404),
        ("El seguimiento ID 1 no pertenece al equipo ID 2.", 404),
        ("La unidad ID 5 no existe o se encuentra inactiva.", 404),
        ("El equipo ID 5 no existe o se encuentra inactivo.", 404),
        ("La unidad ID 5 ya posee un seguimiento abierto.", 409),
        ("El equipo ID 5 ya posee un seguimiento abierto.", 409),
        (
            "Stock insuficiente en la Unidad ID 1 para el material ID LISTA 2. "
            "Disponible: 1, Consumido: 5",
            400,
        ),
        (
            "Stock insuficiente en el Equipo ID 1 para el material ID LISTA 2. "
            "Disponible: 1, Consumido: 5",
            400,
        ),
        (
            "Stock insuficiente en la Unidad destino (ID 1) para revertir el "
            "material ID LISTA 2. Disponible: 0, A revertir: 5",
            400,
        ),
        (
            "La unidad ID 1 no cuenta con stock suficiente del material ID "
            "LISTA 2 para devolver.",
            400,
        ),
    ],
)
async def test_REQ_UNI_007_mapeo_conserva_codigo_http(
    mensaje: str, status: int
) -> None:
    error = await transaccional._mapear_raise_exception(_error_pg(mensaje))
    assert isinstance(error, BusinessRuleError)
    assert error.status_code == status, mensaje


# ── REQ-UNI-008: el contrato no cambia ────────────────────────────────────


async def test_REQ_UNI_008_get_unidad_devuelve_descripcion_e_integrantes(
    client: AsyncClient,
) -> None:
    sin_desc = await crear_equipo(client, nombre="Sin descripcion")
    resp = await client.get(f"/api/v1/equipos/{sin_desc['equipo_id']}")
    assert resp.status_code == 200
    assert resp.json()["descripcion"] is None
    assert resp.json()["integrantes"] == ["qa"]

    creado = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Con descripcion", "descripcion": "Notas", "integrantes": ["a", "b"]},
    )
    assert creado.status_code == 201
    resp = await client.get(f"/api/v1/equipos/{creado.json()['equipo_id']}")
    assert resp.json()["descripcion"] == "Notas"
    assert set(resp.json()["integrantes"]) == {"a", "b"}


async def test_REQ_UNI_008_openapi_rutas_y_campos_sin_cambio(
    client: AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    paths = schema["paths"]
    esperadas = {
        "/api/v1/equipos": {"get", "post"},
        "/api/v1/equipos/{equipo_id}": {"get", "patch", "delete"},
        "/api/v1/equipos/{equipo_id}/inventario": {"get"},
        "/api/v1/equipos/{equipo_id}/inventario/{material_id}": {"patch"},
    }
    for ruta, metodos in esperadas.items():
        assert ruta in paths, ruta
        assert metodos <= set(paths[ruta]), ruta
    assert not [p for p in paths if "unidad" in p.lower()]
    props = schema["components"]["schemas"]["EquipoOut"]["properties"]
    assert {"equipo_id", "nombre", "descripcion", "is_active", "integrantes"} <= set(props)
