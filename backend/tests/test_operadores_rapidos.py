"""Operadores rápidos de inventario y "Agregar todo" — REQ-P2-INV-001..007,
REQ-P2-CON-003/004.

  * POST /api/v1/inventario/sumar-cantidad  -> fn_sumar_cantidad
  * POST /api/v1/inventario/mover           -> fn_mover_material
  * POST /api/v1/equipos/{id}/seguimientos/{id}/agregar-todo
                                            -> fn_agregar_todo_seguimiento

La suma, el descuento/acreditación y la auditoría inmutable viven en
PostgreSQL; Python solo delega (cero aritmética de stock).
"""

import ast
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.helpers.fabrica import (
    ALMACEN_GENERAL,
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    fibra_carga_inicial,
    procesar,
    stock_seccion,
)

SUMAR = "/api/v1/inventario/sumar-cantidad"
MOVER = "/api/v1/inventario/mover"


async def _stock_fibra(client: AsyncClient, modulo: str) -> dict[int, int]:
    resp = await client.get(f"/api/v1/fibra/{modulo}")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f["stock_actual"] for f in resp.json()}


async def _eventos(session, tipo: str) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT usuario, material_id, cantidad, resultado, detalles "
                "FROM auditoria_eventos WHERE tipo_accion = :t ORDER BY id"
            ),
            {"t": tipo},
        )
    ).mappings()
    return [dict(r) for r in rows]


# ── +Cantidad ──────────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_REQ_P2_INV_001_sumar_cantidad_general_3_mas_50_igual_53(
    client: AsyncClient, session
) -> None:
    m = await crear_material(client, descripcion="CAJAS NAP SANDWICH 1 X 16")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=3)

    resp = await client.post(
        SUMAR,
        json={"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": 50},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stock_nuevo"] == 53
    assert body["reenvio_idempotente"] is False
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 53

    # Evento inmutable propio, distinto de AJUSTE_*.
    eventos = await _eventos(session, "SUMA_CANTIDAD")
    assert len(eventos) == 1
    assert eventos[0]["usuario"] == "qa"
    assert eventos[0]["cantidad"] == 50
    assert eventos[0]["detalles"]["stock_anterior"] == 3
    assert eventos[0]["detalles"]["stock_nuevo"] == 53
    assert await _eventos(session, "AJUSTE_INVENTARIO") == []


@pytest.mark.parametrize("modulo", ["PAQUETE", "EN_USO"])
async def test_sumar_cantidad_fibra_optica(
    client: AsyncClient, session, modulo: str
) -> None:
    m = await crear_material(client, descripcion=f"FO {modulo}")
    await fibra_carga_inicial(client, modulo=modulo, material_id=m["id_lista"], cantidad=3)

    resp = await client.post(
        SUMAR,
        json={
            "destino": "FO",
            "modulo": modulo,
            "material_id": m["id_lista"],
            "cantidad": 50,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_nuevo"] == 53
    assert (await _stock_fibra(client, modulo))[m["id_lista"]] == 53
    assert len(await _eventos(session, "SUMA_CANTIDAD")) == 1


@pytest.mark.parametrize("cantidad", [0, -5])
async def test_sumar_cantidad_cero_o_negativa_400_sin_efectos(
    client: AsyncClient, session, cantidad: int
) -> None:
    m = await crear_material(client, descripcion="Cantidad invalida")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)

    resp = await client.post(
        SUMAR,
        json={"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": cantidad},
    )
    assert resp.status_code == 400, resp.text
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 10
    assert await _eventos(session, "SUMA_CANTIDAD") == []


async def test_sumar_cantidad_material_inexistente_404(client: AsyncClient) -> None:
    resp = await client.post(
        SUMAR, json={"destino": "GENERAL", "material_id": 99999, "cantidad": 1}
    )
    assert resp.status_code == 404, resp.text


async def test_sumar_cantidad_sin_registro_de_inventario_404(
    client: AsyncClient,
) -> None:
    """Sin carga inicial no hay fila de inventario: se exige primero la
    carga inicial (modelo disperso)."""
    m = await crear_material(client, descripcion="Sin inventario")
    resp = await client.post(
        SUMAR, json={"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": 1}
    )
    assert resp.status_code == 404, resp.text
    resp = await client.post(
        SUMAR,
        json={"destino": "FO", "modulo": "PAQUETE", "material_id": m["id_lista"], "cantidad": 1},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    "payload",
    [
        {"destino": "FO", "material_id": 1, "cantidad": 1},  # FO sin módulo
        {"destino": "GENERAL", "modulo": "PAQUETE", "material_id": 1, "cantidad": 1},
        {"destino": "OTRO", "material_id": 1, "cantidad": 1},
        {"destino": "GENERAL", "material_id": 1, "cantidad": 1, "stock": 9},
    ],
)
async def test_sumar_cantidad_payload_invalido_422(
    client: AsyncClient, payload: dict
) -> None:
    assert (await client.post(SUMAR, json=payload)).status_code == 422


async def test_sumar_cantidad_actor_sin_alcance_403(
    client: AsyncClient, client_sin_scope: AsyncClient
) -> None:
    m = await crear_material(client, descripcion="Sin alcance")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=1)
    resp = await client_sin_scope.post(
        SUMAR, json={"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": 1}
    )
    assert resp.status_code == 403


@pytest.mark.critical
async def test_REQ_P2_INV_007_sumar_cantidad_reenvio_idempotente(
    client: AsyncClient, session
) -> None:
    """Doble submit con la misma clave: 200 con el resultado ORIGINAL y sin
    duplicar stock ni auditoría."""
    m = await crear_material(client, descripcion="Idempotencia suma")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=3)
    payload = {
        "destino": "GENERAL",
        "material_id": m["id_lista"],
        "cantidad": 50,
        "clave_idempotencia": "suma-001",
    }
    primera = await client.post(SUMAR, json=payload)
    segunda = await client.post(SUMAR, json=payload)

    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["stock_nuevo"] == segunda.json()["stock_nuevo"] == 53
    assert primera.json()["reenvio_idempotente"] is False
    assert segunda.json()["reenvio_idempotente"] is True
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 53
    assert len(await _eventos(session, "SUMA_CANTIDAD")) == 1


async def test_clave_distinta_si_aplica_nueva_suma(client: AsyncClient) -> None:
    m = await crear_material(client, descripcion="Claves distintas")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=3)
    base = {"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": 10}
    await client.post(SUMAR, json={**base, "clave_idempotencia": "k1"})
    resp = await client.post(SUMAR, json={**base, "clave_idempotencia": "k2"})
    assert resp.json()["stock_nuevo"] == 23


# ── Mover ──────────────────────────────────────────────────────────────────


@pytest.mark.critical
async def test_REQ_P2_INV_003_mover_general_a_fo_cantidad_parcial(
    client: AsyncClient, session
) -> None:
    m = await crear_material(client, descripcion="Mover parcial")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)

    resp = await client.post(
        MOVER,
        json={
            "origen": "GENERAL",
            "destino": "FO",
            "destino_modulo": "PAQUETE",
            "material_id": m["id_lista"],
            "cantidad": 4,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["stock_origen"], body["stock_destino"]) == (6, 4)
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 6
    assert (await _stock_fibra(client, "PAQUETE"))[m["id_lista"]] == 4

    eventos = await _eventos(session, "MOVIMIENTO_INVENTARIO")
    assert len(eventos) == 1
    assert eventos[0]["cantidad"] == 4
    assert eventos[0]["detalles"]["stock_origen_despues"] == 6
    assert eventos[0]["detalles"]["stock_destino_despues"] == 4


async def test_mover_fo_a_general_y_entre_modulos_fo(client: AsyncClient) -> None:
    m = await crear_material(client, descripcion="Mover FO")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=2)
    await fibra_carga_inicial(client, modulo="PAQUETE", material_id=m["id_lista"], cantidad=9)

    # FO PAQUETE -> GENERAL (acumula sobre la fila existente).
    resp = await client.post(
        MOVER,
        json={
            "origen": "FO",
            "origen_modulo": "PAQUETE",
            "destino": "GENERAL",
            "material_id": m["id_lista"],
            "cantidad": 5,
        },
    )
    assert resp.status_code == 200, resp.text
    assert (resp.json()["stock_origen"], resp.json()["stock_destino"]) == (4, 7)

    # FO PAQUETE -> FO EN_USO (la fila destino se crea con stock > 0).
    resp = await client.post(
        MOVER,
        json={
            "origen": "FO",
            "origen_modulo": "PAQUETE",
            "destino": "FO",
            "destino_modulo": "EN_USO",
            "material_id": m["id_lista"],
            "cantidad": 4,
        },
    )
    assert resp.status_code == 200, resp.text
    assert (await _stock_fibra(client, "EN_USO"))[m["id_lista"]] == 4
    # Semántica dispersa: la fila origen llegó a 0 y se CONSERVA.
    assert (await _stock_fibra(client, "PAQUETE"))[m["id_lista"]] == 0


async def test_mover_stock_insuficiente_400_atomico(
    client: AsyncClient, session
) -> None:
    m = await crear_material(client, descripcion="Mover insuficiente")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=3)

    resp = await client.post(
        MOVER,
        json={
            "origen": "GENERAL",
            "destino": "FO",
            "destino_modulo": "PAQUETE",
            "material_id": m["id_lista"],
            "cantidad": 4,
        },
    )
    assert resp.status_code == 400, resp.text
    # Ningún inventario (origen ni destino) queda modificado.
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 3
    assert m["id_lista"] not in await _stock_fibra(client, "PAQUETE")
    assert await _eventos(session, "MOVIMIENTO_INVENTARIO") == []


@pytest.mark.parametrize("cantidad", [0, -1])
async def test_mover_cantidad_cero_o_negativa_400(
    client: AsyncClient, cantidad: int
) -> None:
    m = await crear_material(client, descripcion="Mover cantidad invalida")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=3)
    resp = await client.post(
        MOVER,
        json={
            "origen": "GENERAL",
            "destino": "FO",
            "destino_modulo": "PAQUETE",
            "material_id": m["id_lista"],
            "cantidad": cantidad,
        },
    )
    assert resp.status_code == 400, resp.text
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 3


async def test_mover_destino_igual_al_origen_422_sin_efectos(
    client: AsyncClient, session
) -> None:
    m = await crear_material(client, descripcion="Mover igual")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=5)
    await fibra_carga_inicial(client, modulo="PAQUETE", material_id=m["id_lista"], cantidad=5)

    for payload in (
        {"origen": "GENERAL", "destino": "GENERAL"},
        {
            "origen": "FO",
            "origen_modulo": "PAQUETE",
            "destino": "FO",
            "destino_modulo": "PAQUETE",
        },
    ):
        resp = await client.post(
            MOVER, json={**payload, "material_id": m["id_lista"], "cantidad": 1}
        )
        assert resp.status_code == 422, resp.text
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 5
    assert (await _stock_fibra(client, "PAQUETE"))[m["id_lista"]] == 5
    assert await _eventos(session, "MOVIMIENTO_INVENTARIO") == []


async def test_mover_origen_sin_registro_404(client: AsyncClient) -> None:
    m = await crear_material(client, descripcion="Mover sin registro")
    resp = await client.post(
        MOVER,
        json={
            "origen": "GENERAL",
            "destino": "FO",
            "destino_modulo": "PAQUETE",
            "material_id": m["id_lista"],
            "cantidad": 1,
        },
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    "payload",
    [
        {"origen": "FO", "destino": "GENERAL"},  # origen FO sin módulo
        {"origen": "GENERAL", "destino": "FO"},  # destino FO sin módulo
        {"origen": "GENERAL", "origen_modulo": "PAQUETE", "destino": "FO", "destino_modulo": "EN_USO"},
    ],
)
async def test_mover_payload_invalido_422(client: AsyncClient, payload: dict) -> None:
    resp = await client.post(MOVER, json={**payload, "material_id": 1, "cantidad": 1})
    assert resp.status_code == 422


@pytest.mark.critical
async def test_REQ_P2_INV_007_mover_reenvio_idempotente(
    client: AsyncClient, session
) -> None:
    m = await crear_material(client, descripcion="Idempotencia mover")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)
    payload = {
        "origen": "GENERAL",
        "destino": "FO",
        "destino_modulo": "EN_USO",
        "material_id": m["id_lista"],
        "cantidad": 4,
        "clave_idempotencia": "mover-001",
    }
    primera = await client.post(MOVER, json=payload)
    segunda = await client.post(MOVER, json=payload)

    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["reenvio_idempotente"] is False
    assert segunda.json()["reenvio_idempotente"] is True
    for r in (primera, segunda):
        assert (r.json()["stock_origen"], r.json()["stock_destino"]) == (6, 4)
    assert (await stock_seccion(client, ALMACEN_GENERAL))[m["id_lista"]] == 6
    assert (await _stock_fibra(client, "EN_USO"))[m["id_lista"]] == 4
    assert len(await _eventos(session, "MOVIMIENTO_INVENTARIO")) == 1


# ── "Agregar todo" ─────────────────────────────────────────────────────────


async def _equipo_con_stock(client: AsyncClient) -> tuple[dict, list[dict]]:
    """Equipo con dos materiales (50 y 30 u.) confirmados por TEAMS."""
    equipo = await crear_equipo(client, nombre="Equipo Agregar Todo")
    materiales = []
    for i, cantidad in enumerate((50, 30)):
        m = await crear_material(client, descripcion=f"Material AT {i}")
        await carga_inicial(client, material_id=m["id_lista"], cantidad=100)
        b = await borrador_teams(
            client,
            almacen_id=1,
            equipo_id=equipo["equipo_id"],
            material_id=m["id_lista"],
            cantidad=cantidad,
        )
        await procesar(client, b["id"])
        materiales.append(m)
    return equipo, materiales


async def _abrir_seguimiento(client, equipo, material, tomada=10) -> dict:
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": tomada}]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _agregar_todo(equipo: dict, seguimiento: dict) -> str:
    return (
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/"
        f"{seguimiento['id']}/agregar-todo"
    )


@pytest.mark.critical
async def test_REQ_P2_CON_003_agregar_todo_carga_todo_el_inventario_del_equipo(
    client: AsyncClient, session
) -> None:
    equipo, (m1, m2) = await _equipo_con_stock(client)
    seg = await _abrir_seguimiento(client, equipo, m1, tomada=10)

    resp = await client.post(_agregar_todo(equipo, seg))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # m1 ya estaba (10 u.): solo se agrega m2 (idempotente, no duplica ni pisa).
    assert body["lineas_agregadas"] == 1
    items = {i["material_id"]: i["cantidad_tomada"] for i in body["seguimiento"]["items"]}
    assert items == {m1["id_lista"]: 10, m2["id_lista"]: 30}
    assert body["seguimiento"]["estado"] == "ABIERTA"

    eventos = await _eventos(session, "AGREGAR_TODO")
    assert len(eventos) == 1


async def test_agregar_todo_segunda_invocacion_no_duplica_lineas(
    client: AsyncClient, session
) -> None:
    equipo, (m1, _m2) = await _equipo_con_stock(client)
    seg = await _abrir_seguimiento(client, equipo, m1)

    await client.post(_agregar_todo(equipo, seg))
    resp = await client.post(_agregar_todo(equipo, seg))
    assert resp.status_code == 200, resp.text
    assert resp.json()["lineas_agregadas"] == 0
    assert len(resp.json()["seguimiento"]["items"]) == 2
    # Sin líneas nuevas, el ledger no emite un segundo evento.
    assert len(await _eventos(session, "AGREGAR_TODO")) == 1


async def test_agregar_todo_reenvio_con_clave_devuelve_resultado_original(
    client: AsyncClient,
) -> None:
    equipo, (m1, _m2) = await _equipo_con_stock(client)
    seg = await _abrir_seguimiento(client, equipo, m1)
    cuerpo = {"clave_idempotencia": "at-001"}

    primera = await client.post(_agregar_todo(equipo, seg), json=cuerpo)
    segunda = await client.post(_agregar_todo(equipo, seg), json=cuerpo)
    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["lineas_agregadas"] == 1
    assert segunda.json()["lineas_agregadas"] == 1  # resultado original
    assert len(segunda.json()["seguimiento"]["items"]) == 2


async def test_REQ_P2_CON_004_agregar_todo_en_seguimiento_cerrado_409(
    client: AsyncClient,
) -> None:
    equipo, (m1, _m2) = await _equipo_con_stock(client)
    seg = await _abrir_seguimiento(client, equipo, m1)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{seg['id']}/cerrar",
        json={"sobrantes": []},
    )
    assert resp.status_code == 200
    resp = await client.post(_agregar_todo(equipo, seg))
    assert resp.status_code == 409, resp.text


async def test_agregar_todo_seguimiento_de_otro_equipo_404(
    client: AsyncClient,
) -> None:
    equipo, (m1, _m2) = await _equipo_con_stock(client)
    otro = await crear_equipo(client, nombre="Otro equipo")
    seg = await _abrir_seguimiento(client, equipo, m1)
    resp = await client.post(
        f"/api/v1/equipos/{otro['equipo_id']}/seguimientos/{seg['id']}/agregar-todo"
    )
    assert resp.status_code == 404, resp.text


async def test_agregar_todo_seguimiento_inexistente_404(client: AsyncClient) -> None:
    equipo, _ = await _equipo_con_stock(client)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/99999/agregar-todo"
    )
    assert resp.status_code == 404, resp.text


async def test_agregar_todo_actor_no_integrante_403(
    client: AsyncClient, client_factory
) -> None:
    equipo, (m1, _m2) = await _equipo_con_stock(client)
    seg = await _abrir_seguimiento(client, equipo, m1)
    ajeno = client_factory("intruso")
    try:
        resp = await ajeno.post(_agregar_todo(equipo, seg))
        assert resp.status_code == 403
    finally:
        await ajeno.aclose()


# ── Invariante constitucional: cero aritmética de stock en Python ──────────


def test_cero_aritmetica_de_stock_en_la_capa_de_aplicacion() -> None:
    """Guarda estática por AST (REQ-P2-INV-002): ningún módulo de `app/`
    realiza operaciones aritméticas (+, -, *, /, //, %) ni asignaciones
    aumentadas sobre variables/atributos de stock o cantidades."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    sensibles = ("stock", "cantidad", "sobrante", "consumid")
    ops = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)

    def _nombre(nodo: ast.AST) -> str:
        if isinstance(nodo, ast.Name):
            return nodo.id.lower()
        if isinstance(nodo, ast.Attribute):
            return nodo.attr.lower()
        if isinstance(nodo, ast.Subscript):
            clave = nodo.slice
            if isinstance(clave, ast.Constant) and isinstance(clave.value, str):
                return clave.value.lower()  # p. ej. fila["stock_actual"]
            return _nombre(nodo.value)
        return ""

    def _sensible(nodo: ast.AST) -> bool:
        return any(t in _nombre(nodo) for t in sensibles)

    ofensores = []
    for archivo in app_dir.rglob("*.py"):
        arbol = ast.parse(archivo.read_text())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ops):
                if _sensible(nodo.left) or _sensible(nodo.right):
                    ofensores.append(f"{archivo.relative_to(app_dir)}:{nodo.lineno}")
            elif isinstance(nodo, ast.AugAssign) and isinstance(nodo.op, ops):
                if _sensible(nodo.target) or _sensible(nodo.value):
                    ofensores.append(f"{archivo.relative_to(app_dir)}:{nodo.lineno}")
    assert ofensores == []
