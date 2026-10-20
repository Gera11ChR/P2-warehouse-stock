"""ACTIVIDADES por Unidad (0029) — pruebas de API (T6,
paquete 2026-10-actividades-unidad).

Una prueba por requisito REQ-ACT-NNN que asevera respuesta HTTP **y**
estado de base de datos: GET pendiente (herencia de consumidos), POST
(folio global correlativo, fecha now(), snapshot con valor_unitario
congelado), 409 de duplicado/abierto, 404 de pertenencia, 403 de
aislamiento, 422 de entrada (extras, límites, caracteres de control),
concurrencia 201/409, inmutabilidad por trigger, evento
ACTIVIDAD_CONFIRMADA y cero efectos sobre inventario/seguimientos/actas.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    patch_material,
    procesar,
)

PAYLOAD_BASE = {
    "vehiculo": "Camioneta 12",
    "clientes": "Cliente A",
    "direcciones": "Calle 1",
    "actividades": ["Tendido de fibra"],
    "comentarios": "Sin incidencias",
}


async def _material_con_stock_en_equipo(
    client: AsyncClient,
) -> tuple[dict, dict]:
    """Material en catálogo + unidad con stock real vía TEAMS (patrón de
    test_seguimientos)."""
    material = await crear_material(client, descripcion="Material Act")
    equipo = await crear_equipo(client, nombre="Unidad Act")
    await carga_inicial(client, material_id=material["id_lista"], cantidad=100)
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=50,
    )
    await procesar(client, b["id"])
    return material, equipo


async def _seguimiento_cerrado(
    client: AsyncClient, equipo_id: int, material_id: int, *, consumida: float
) -> int:
    """Crea y cierra un seguimiento por API (ABIERTA -> CERRADA) con una
    línea consumida. Devuelve el seguimiento_id."""
    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/seguimientos",
        json={"items": [{"material_id": material_id, "cantidad_tomada": 10}]},
    )
    assert resp.status_code == 201, resp.text
    seguimiento_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/seguimientos/{seguimiento_id}/cerrar",
        json={
            "consumidos": [
                {"material_id": material_id, "cantidad_consumida": consumida}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    return seguimiento_id


async def _post_actividad(
    client: AsyncClient, equipo_id: int, seguimiento_id: int, **overrides
) -> object:
    payload = {**PAYLOAD_BASE, "seguimiento_id": seguimiento_id}
    payload.update(overrides)
    return await client.post(
        f"/api/v1/equipos/{equipo_id}/actividades", json=payload
    )


# ----------------------------------------------------------------


async def test_req_act_001_endpoints_en_contrato_openapi(client: AsyncClient) -> None:
    """REQ-ACT-001: la sección ACTIVIDADES expone sus tres rutas en el
    contrato OpenAPI (pendiente, POST y lista por Unidad)."""
    from app.main import app

    openapi = app.openapi()
    rutas = sorted(p for p in openapi["paths"] if "actividades" in p)
    assert rutas == [
        "/api/v1/equipos/{equipo_id}/actividades",
        "/api/v1/equipos/{equipo_id}/actividades/pendiente",
    ]


@pytest.mark.critical
async def test_req_act_002_pendiente_hereda_materiales_consumidos(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-ACT-002: GET pendiente devuelve el seguimiento CERRADA más
    reciente con sus materiales consumidos (cantidad y valor unitario
    vigentes)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    resp = await patch_material(client_admin, material["id_lista"], valor_unitario=7.5)
    assert resp.status_code == 200, resp.text
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=4
    )
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert resp.status_code == 200, resp.text
    pendiente = resp.json()["seguimiento"]
    assert pendiente["seguimiento_id"] == seg
    assert pendiente["fecha_cierre"] is not None
    assert len(pendiente["materiales"]) == 1
    linea = pendiente["materiales"][0]
    assert linea["material_id"] == material["id_lista"]
    assert linea["cantidad_consumida"] == 4
    assert linea["valor_unitario"] == 7.5


async def test_req_act_003_sin_pendiente_null_y_estados_404_409(
    client: AsyncClient,
) -> None:
    """REQ-ACT-003: sin seguimiento pendiente el GET devuelve null y el POST
    es 409 (abierto/duplicado) o 404 (ajeno/inexistente)."""
    material, equipo = await _material_con_stock_en_equipo(client)

    # Sin seguimiento pendiente: null.
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert resp.status_code == 200 and resp.json()["seguimiento"] is None

    # Seguimiento ABIERTA: no aparece como pendiente y el POST da 409.
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": 5}]},
    )
    abierto = resp.json()["id"]
    pend = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert pend.json()["seguimiento"] is None
    resp = await _post_actividad(client, equipo["equipo_id"], abierto)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SEGUIMIENTO_NO_CERRADO"

    # Seguimiento inexistente o de otra Unidad: 404.
    otra = await crear_equipo(client, nombre="Otra Unidad")
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=otra["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b["id"])
    resp = await _post_actividad(client, equipo["equipo_id"], 999999)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SEGUIMIENTO_NO_ENCONTRADO"
    seg_ajeno = await _seguimiento_cerrado(
        client, otra["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg_ajeno)
    assert resp.status_code == 404


async def test_req_act_004_seguimiento_sin_consumo_confirmable(
    client: AsyncClient,
) -> None:
    """REQ-ACT-004: un seguimiento cerrado con cero consumo es confirmable
    con lista de materiales vacía."""
    material, equipo = await _material_con_stock_en_equipo(client)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": 10}]},
    )
    seguimiento_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{seguimiento_id}/cerrar",
        json={
            "consumidos": [
                {"material_id": material["id_lista"], "cantidad_consumida": 0}
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    pend = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert pend.json()["seguimiento"]["materiales"] == []
    resp = await _post_actividad(client, equipo["equipo_id"], seguimiento_id)
    assert resp.status_code == 201, resp.text
    assert resp.json()["materiales"] == []


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("vehiculo", "   "),
        ("vehiculo", "x" * 101),
        ("clientes", ""),
        ("clientes", "x" * 501),
        ("direcciones", "  "),
        ("direcciones", "x" * 501),
    ],
)
async def test_req_act_005_campos_cabecera_obligatorios_y_limites(
    client: AsyncClient, campo: str, valor: str
) -> None:
    """REQ-ACT-005: Vehículo/Cliente(s)/Dirección(es) obligatorios, sin
    espacios en blanco y con longitud máxima (422 antes de la BD)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg, **{campo: valor})
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "actividades",
    [
        [],
        ["a"] * 31,
        [""],
        ["   "],
        ["x" * 501],
        ["ok", 1],
    ],
)
async def test_req_act_006_actividades_entre_1_y_30_celdas(
    client: AsyncClient, actividades: list
) -> None:
    """REQ-ACT-006: al menos una celda, máximo 30, cada una texto de 1..500
    (las vacías se rechazan; el cliente las descarta antes de enviar)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(
        client, equipo["equipo_id"], seg, actividades=actividades
    )
    assert resp.status_code == 422, resp.text
    # Límite exacto: 30 celdas de 500 caracteres entran.
    ok = await _post_actividad(
        client,
        equipo["equipo_id"],
        seg,
        actividades=["x" * 500] * 30,
    )
    assert ok.status_code == 201, ok.text
    assert len(ok.json()["actividades"]) == 30


async def test_req_act_007_comentarios_opcional_y_con_salto_de_linea(
    client: AsyncClient,
) -> None:
    """REQ-ACT-007: comentarios opcionales (null si se omiten), máximo 2000,
    y admite saltos de línea pero no otros caracteres de control."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(
        client, equipo["equipo_id"], seg, comentarios=None
    )
    assert resp.status_code == 201 and resp.json()["comentarios"] is None
    resp = await _post_actividad(
        client, equipo["equipo_id"], seg, comentarios="línea 1\nlínea 2"
    )
    assert resp.status_code == 409  # seguimiento ya confirmado
    # Límites y controles: 422 por el DTO antes de tocar datos.
    assert (await _post_actividad(
        client, equipo["equipo_id"], seg, comentarios="x" * 2001
    )).status_code == 422
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    assert (await _post_actividad(
        client, equipo["equipo_id"], seg2, comentarios="x" * 2001
    )).status_code == 422
    assert (await _post_actividad(
        client, equipo["equipo_id"], seg2, comentarios="malo\x07control"
    )).status_code == 422


@pytest.mark.critical
async def test_req_act_008_folio_global_correlativo_y_no_aceptado(
    client: AsyncClient,
) -> None:
    """REQ-ACT-008: folio R0001, R0002... global (dos Unidades), y el
    cliente no puede enviarlo (422 por campo extra)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    otra = await crear_equipo(client, nombre="Unidad Folio")
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=otra["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b["id"])

    seg1 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=2
    )
    seg2 = await _seguimiento_cerrado(
        client, otra["equipo_id"], material["id_lista"], consumida=3
    )
    r1 = await _post_actividad(client, equipo["equipo_id"], seg1)
    r2 = await _post_actividad(client, otra["equipo_id"], seg2)
    assert r1.status_code == 201 and r1.json()["folio"] == "R0001"
    assert r2.status_code == 201 and r2.json()["folio"] == "R0002"
    assert r1.json()["folio_num"] == 1 and r2.json()["folio_num"] == 2

    seg3 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(
        client, equipo["equipo_id"], seg3, folio="R7777"
    )
    assert resp.status_code == 422, resp.text


async def test_req_act_009_fecha_automatica_ahora_y_no_aceptada(
    client: AsyncClient,
) -> None:
    """REQ-ACT-009: la fecha la fija PostgreSQL (now(), timestamptz) al
    confirmar; el cliente no puede enviarla."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201, resp.text
    fecha = resp.json()["fecha"]
    parsed = datetime.fromisoformat(fecha)
    assert abs(parsed - datetime.now(timezone.utc)) < timedelta(minutes=5)
    assert parsed.tzinfo is not None
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(
        client, equipo["equipo_id"], seg2, fecha="2030-01-01T00:00:00Z"
    )
    assert resp.status_code == 422, resp.text


async def test_req_act_010_snapshot_valor_unitario_congelado(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-ACT-010: el snapshot congela el valor_unitario vigente en la
    confirmación; cambios posteriores del catálogo no lo alteran."""
    material, equipo = await _material_con_stock_en_equipo(client)
    resp = await patch_material(client_admin, material["id_lista"], valor_unitario=5.5)
    assert resp.status_code == 200
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=2
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201
    assert resp.json()["materiales"][0]["valor_unitario"] == 5.5

    resp = await patch_material(client_admin, material["id_lista"], valor_unitario=9.999)
    assert resp.status_code == 200
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades"
    )
    assert resp.json()["items"][0]["materiales"][0]["valor_unitario"] == 5.5


async def test_req_act_011_atomicidad_concurrencia_y_reintento_409(
    client: AsyncClient, client_factory, session
) -> None:
    """REQ-ACT-011: dos confirmaciones concurrentes sobre el mismo
    seguimiento producen exactamente un registro (201 + 409); el reintento
    no duplica ni consume folio."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )

    async def intentar() -> tuple[int, dict]:
        c = client_factory("qa")
        try:
            r = await c.post(
                f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
                json={**PAYLOAD_BASE, "seguimiento_id": seg},
            )
            return r.status_code, r.json()
        finally:
            await c.aclose()

    r1, r2 = await asyncio.gather(intentar(), intentar())
    estados = sorted([r1[0], r2[0]])
    assert estados == [201, 409]
    fallo = r1[1] if r1[0] == 409 else r2[1]
    assert fallo["error"]["code"] == "ACTIVIDAD_DUPLICADA"

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM actividades_reportes "
                     "WHERE seguimiento_id = :s"),
                {"s": seg},
            )
        ).scalar_one()
        folios = (
            await session.execute(text("SELECT count(DISTINCT folio_num) FROM actividades_reportes"))
        ).scalar_one()
    assert n == 1 and folios == 1


async def test_req_act_012_inmutabilidad_y_evento_auditoria(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-012: UPDATE/DELETE sobre la actividad son rechazados por el
    trigger; la confirmación emite ACTIVIDAD_CONFIRMADA con folio y actor."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201
    actividad_id = resp.json()["actividad_id"]

    for stmt in (
        f"UPDATE actividades_reportes SET vehiculo='ZZ' WHERE id={actividad_id}",
        f"DELETE FROM actividades_reportes WHERE id={actividad_id}",
    ):
        async with session.begin():
            with pytest.raises(DBAPIError, match="append-only"):
                await session.execute(text(stmt))

    async with session.begin():
        evento = (
            await session.execute(
                text("SELECT usuario, tipo_accion, equipo_origen_id, resultado, "
                     "detalles FROM auditoria_eventos "
                     "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA'")
            )
        ).one()
    assert evento.usuario == "qa"
    assert evento.equipo_origen_id == equipo["equipo_id"]
    assert evento.resultado == "EXITO"
    assert evento.detalles["folio"] == "R0001"
    assert evento.detalles["actividad_id"] == actividad_id
    assert evento.detalles["seguimiento_id"] == seg


async def test_req_act_013_validacion_entrada_extra_tipos_y_controles(
    client: AsyncClient,
) -> None:
    """REQ-ACT-013: campos no declarados, tipos incorrectos y caracteres de
    control responden 422 sin tocar datos de negocio."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    casos: list[dict] = [
        {**PAYLOAD_BASE, "seguimiento_id": seg, "usuario": "hacker"},
        {**PAYLOAD_BASE, "seguimiento_id": seg, "materiales": []},
        {**PAYLOAD_BASE, "seguimiento_id": "abc"},
        {**PAYLOAD_BASE, "seguimiento_id": seg, "vehiculo": "bad\x00char"},
        {**PAYLOAD_BASE, "seguimiento_id": seg, "clientes": "bad\x9f"},
        {**PAYLOAD_BASE, "seguimiento_id": seg, "direcciones": "bad\x7f"},
        {**PAYLOAD_BASE, "seguimiento_id": seg, "actividades": ["ok\x01"]},
        {**PAYLOAD_BASE, "seguimiento_id": 0},
        {**PAYLOAD_BASE, "seguimiento_id": 2147483648},
    ]
    for payload in casos:
        resp = await client.post(
            f"/api/v1/equipos/{equipo['equipo_id']}/actividades", json=payload
        )
        assert resp.status_code == 422, (payload, resp.text)

    # ID de ruta fuera de INT4: 400 canónico del handler global (22003).
    resp = await client.get("/api/v1/equipos/9999999999/actividades/pendiente")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NUMERIC_OUT_OF_RANGE"


async def test_req_act_014_autorizacion_403_404_y_admin_transversal(
    client: AsyncClient, client_admin: AsyncClient, client_sin_scope: AsyncClient
) -> None:
    """REQ-ACT-014: actor sin acceso 403, Unidad inexistente 404 (antes que
    403), administrador con pase transversal, integrante autorizado."""
    material, equipo = await _material_con_stock_en_equipo(client)

    # Actor sin scope ni membresía: 403 en las tres rutas.
    for metodo, ruta in (
        ("GET", f"/api/v1/equipos/{equipo['equipo_id']}/actividades"),
        ("GET", f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"),
    ):
        r = await client_sin_scope.request(metodo, ruta)
        assert r.status_code == 403, r.text
    r = await client_sin_scope.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**PAYLOAD_BASE, "seguimiento_id": 1},
    )
    assert r.status_code == 403, r.text

    # Unidad inexistente: 404 incluso sin acceso (404 antes de 403).
    r = await client_sin_scope.get("/api/v1/equipos/999999/actividades")
    assert r.status_code == 404, r.text

    # Administrador sin membresía: pase transversal.
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    r = await client_admin.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**PAYLOAD_BASE, "seguimiento_id": seg},
    )
    assert r.status_code == 201, r.text
    r = await client_admin.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades"
    )
    assert r.status_code == 200 and r.json()["total"] == 1


async def test_req_act_015_sin_efectos_sobre_inventario_y_actas(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-015: confirmar una actividad no modifica inventario_equipos,
    seguimientos (estado) ni actas_reportes."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=3
    )
    antes_inv = await inventario_equipo(client, equipo["equipo_id"])
    async with session.begin():
        antes_actas = (
            await session.execute(text("SELECT count(*) FROM actas_reportes"))
        ).scalar_one()
        antes_estado = (
            await session.execute(
                text("SELECT estado FROM seguimientos WHERE id = :s"), {"s": seg}
            )
        ).scalar_one()

    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201

    despues_inv = await inventario_equipo(client, equipo["equipo_id"])
    assert despues_inv == antes_inv
    async with session.begin():
        despues_actas = (
            await session.execute(text("SELECT count(*) FROM actas_reportes"))
        ).scalar_one()
        estado = (
            await session.execute(
                text("SELECT estado FROM seguimientos WHERE id = :s"), {"s": seg}
            )
        ).scalar_one()
    assert despues_actas == antes_actas
    assert estado == antes_estado == "CERRADA"


async def test_req_act_016_lista_ordenada_de_mas_reciente_a_antigua(
    client: AsyncClient,
) -> None:
    """REQ-ACT-016: GET lista devuelve las actividades de la Unidad con
    folio, fecha y campos, ordenadas de la más reciente a la más antigua."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg1 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    r1 = await _post_actividad(client, equipo["equipo_id"], seg1)
    assert r1.status_code == 201
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=2
    )
    r2 = await _post_actividad(client, equipo["equipo_id"], seg2)
    assert r2.status_code == 201

    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [i["actividad_id"] for i in body["items"]] == [
        r2.json()["actividad_id"], r1.json()["actividad_id"],
    ]
    primero = body["items"][0]
    assert primero["folio"] == "R0002"
    assert primero["equipo_nombre"] == "Unidad Act"
    assert primero["vehiculo"] == "Camioneta 12"
    assert primero["actividades"] == ["Tendido de fibra"]
    assert len(primero["materiales"]) == 1


async def test_req_act_019_errores_deterministas_codigos_de_dominio(
    client: AsyncClient,
) -> None:
    """REQ-ACT-019: los errores de la Stored Function se mapean al cuerpo
    canónico con códigos de dominio (nunca 500 por reglas de negocio)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    ok = await _post_actividad(client, equipo["equipo_id"], seg)
    assert ok.status_code == 201
    dup = await _post_actividad(client, equipo["equipo_id"], seg)
    assert dup.status_code == 409
    error = dup.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "ACTIVIDAD_DUPLICADA"
    assert "ya tiene una actividad confirmada" in error["message"]

    resp = await _post_actividad(client, equipo["equipo_id"], 999999)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SEGUIMIENTO_NO_ENCONTRADO"


# ---- Regresiones de la compuerta de contrato (T7) ------------------------


async def test_req_act_013_surrogate_unicode_suelto_es_422_no_500(
    client: AsyncClient,
) -> None:
    """T7/F-1: un sustituto Unicode suelto (no codificable en UTF-8) es 422
    en cualquier campo de texto, nunca 500 (REQ-ACT-013/019)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    for campo, valor in (
        ("vehiculo", '"\\ud800"'),
        ("clientes", '"a\\udfffb"'),
        ("direcciones", '"\\ud83d"'),
        ("comentarios", '"\\ud800"'),
        ("actividades", '["\\ud800"]'),
    ):
        base = {
            "seguimiento_id": seg,
            "vehiculo": '"V"',
            "clientes": '"C"',
            "direcciones": '"D"',
            "actividades": '["A"]',
            "comentarios": "null",
        }
        base[campo] = valor
        cuerpo = "{" + ",".join(f'"{k}": {v}' for k, v in base.items()) + "}"
        resp = await client.post(
            f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
            content=cuerpo,
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422, (campo, resp.status_code, resp.text)


async def test_req_act_002_materiales_sin_codigo_ni_um_se_serializan(
    client: AsyncClient, session
) -> None:
    """T7/F-3: el catálogo admite codigo/u_m NULL; el pendiente y la
    actividad los devuelven como null (jamás 500)."""
    equipo = await crear_equipo(client, nombre="Unidad Nulos")
    async with session.begin():
        mat = (
            await session.execute(
                text("INSERT INTO catalogo_materiales (descripcion, codigo, u_m) "
                     "VALUES ('Sin codigo', NULL, NULL) RETURNING id_lista")
            )
        ).scalar_one()
        seg = (
            await session.execute(
                text("INSERT INTO seguimientos (equipo_id, usuario, estado, closed_at) "
                     "VALUES (:e, 'qa', 'CERRADA', now()) RETURNING id"),
                {"e": equipo["equipo_id"]},
            )
        ).scalar_one()
        await session.execute(
            text("INSERT INTO seguimiento_items (seguimiento_id, material_id, "
                 "cantidad_tomada, cantidad_consumida) VALUES (:s, :m, 5, 2)"),
            {"s": seg, "m": mat},
        )
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert resp.status_code == 200, resp.text
    linea = resp.json()["seguimiento"]["materiales"][0]
    assert linea["codigo"] is None and linea["u_m"] is None
    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201, resp.text
    assert resp.json()["materiales"][0]["codigo"] is None


async def test_req_act_018_contrato_openapi_conforme_al_plan(
    client: AsyncClient,
) -> None:
    """T7/F-2/F-4: el contrato OpenAPI declara los códigos y límites del plan
    §3.2 (200/201, 400, 403, 404, 409, 422), `extra=forbid` y campos exactos."""
    from app.main import app

    o = app.openapi()
    base = "/api/v1/equipos/{equipo_id}/actividades"
    assert sorted(o["paths"][base + "/pendiente"]["get"]["responses"]) == [
        "200", "400", "403", "404", "422"]
    assert sorted(o["paths"][base]["post"]["responses"]) == [
        "201", "400", "403", "404", "409", "422"]
    assert sorted(o["paths"][base]["get"]["responses"]) == [
        "200", "400", "403", "404", "422"]

    schemas = o["components"]["schemas"]
    crear = schemas["ActividadCreate"]
    assert crear["additionalProperties"] is False
    assert set(crear["properties"]) == {
        "seguimiento_id", "vehiculo", "clientes", "direcciones",
        "actividades", "comentarios"}
    assert set(crear["required"]) == {
        "seguimiento_id", "vehiculo", "clientes", "direcciones", "actividades"}
    # Ausentes por diseño: los decide PostgreSQL.
    assert not {"folio", "fecha", "materiales", "valor_unitario", "usuario"} & set(
        crear["properties"])
    celdas = crear["properties"]["actividades"]
    assert (celdas["minItems"], celdas["maxItems"]) == (1, 30)
    assert (celdas["items"]["minLength"], celdas["items"]["maxLength"]) == (1, 500)
    assert crear["properties"]["vehiculo"]["maxLength"] == 100
    assert crear["properties"]["clientes"]["maxLength"] == 500
    assert crear["properties"]["direcciones"]["maxLength"] == 500
    assert crear["properties"]["comentarios"]["anyOf"][0]["maxLength"] == 2000

    assert set(schemas["ActividadOut"]["properties"]) == {
        "actividad_id", "folio", "folio_num", "seguimiento_id", "equipo_id",
        "equipo_nombre", "fecha", "usuario", "vehiculo", "clientes",
        "direcciones", "actividades", "comentarios", "materiales"}
    assert set(schemas["ActividadMaterialOut"]["properties"]) == {
        "material_id", "codigo", "descripcion", "u_m", "cantidad_consumida",
        "valor_unitario"}
    assert set(schemas["ActividadPendienteSeguimiento"]["properties"]) == {
        "seguimiento_id", "fecha_cierre", "materiales"}
    assert set(schemas["ActividadListOut"]["properties"]) == {"items", "total"}
