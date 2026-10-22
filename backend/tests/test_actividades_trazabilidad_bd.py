"""ACTIVIDADES por Unidad (0029) — complemento de trazabilidad HTTP + BD
(T11, Fase 8, paquete 2026-10-actividades-unidad).

`.agents.md` (@tester/@qa-agent) y `tasks.md` T11 exigen que cada REQ tenga
una prueba que aserte la respuesta HTTP **y** el estado persistido. Las
pruebas de T6 (`test_actividades.py`) cubren HTTP y relectura por API; este
archivo agrega la aserción DIRECTA sobre PostgreSQL (consultas SQL sobre
`actividades_reportes`, `auditoria_eventos`, `seguimiento_items`) para los
REQ cuyo estado no se consultaba directamente, incluidos los rechazos
(409/404/422/403 => NO se creó registro ni evento).

No modifica código de aplicación ni las pruebas de T6.
"""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import text

from tests.helpers.fabrica import crear_equipo, patch_material
from tests.test_actividades import (
    PAYLOAD_BASE,
    _material_con_stock_en_equipo,
    _post_actividad,
    _seguimiento_cerrado,
)

SQL_FILAS = "SELECT count(*) FROM actividades_reportes"
SQL_EVENTOS = (
    "SELECT count(*) FROM auditoria_eventos "
    "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA'"
)


async def _contar(session, sql: str, **params) -> int:
    async with session.begin():
        return (await session.execute(text(sql), params)).scalar_one()


async def _sin_registro_ni_evento(session) -> None:
    assert await _contar(session, SQL_FILAS) == 0
    assert await _contar(session, SQL_EVENTOS) == 0


async def test_req_act_002_pendiente_es_lectura_pura_y_coincide_con_bd(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-002: el GET pendiente refleja `seguimiento_items` en BD y no
    escribe nada (ni actividad ni evento)."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=4
    )
    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades/pendiente"
    )
    assert resp.status_code == 200, resp.text
    linea = resp.json()["seguimiento"]["materiales"][0]

    async with session.begin():
        item = (
            await session.execute(
                text(
                    "SELECT material_id, cantidad_consumida FROM seguimiento_items "
                    "WHERE seguimiento_id = :s"
                ),
                {"s": seg},
            )
        ).one()
    assert linea["material_id"] == item.material_id
    assert linea["cantidad_consumida"] == float(item.cantidad_consumida) == 4.0
    await _sin_registro_ni_evento(session)


async def test_req_act_003_rechazos_no_crean_registro_ni_evento_en_bd(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-003: 409 (abierto) y 404 (inexistente/ajeno) NO crean fila en
    `actividades_reportes` ni evento en `auditoria_eventos`."""
    material, equipo = await _material_con_stock_en_equipo(client)
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={"items": [{"material_id": material["id_lista"], "cantidad_tomada": 5}]},
    )
    abierto = resp.json()["id"]
    r = await _post_actividad(client, equipo["equipo_id"], abierto)
    assert r.status_code == 409

    r = await _post_actividad(client, equipo["equipo_id"], 999999)
    assert r.status_code == 404

    otra = await crear_equipo(client, nombre="Unidad Ajena BD")
    seg_ajeno = await _seguimiento_cerrado_otra_unidad(client, otra, material)
    r = await _post_actividad(client, equipo["equipo_id"], seg_ajeno)
    assert r.status_code == 404

    await _sin_registro_ni_evento(session)


async def _seguimiento_cerrado_otra_unidad(
    client: AsyncClient, otra: dict, material: dict
) -> int:
    from tests.helpers.fabrica import borrador_teams, procesar

    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=otra["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b["id"])
    return await _seguimiento_cerrado(
        client, otra["equipo_id"], material["id_lista"], consumida=1
    )


async def test_req_act_004_cero_consumo_persiste_materiales_vacios_en_bd(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-004: un seguimiento con consumo 0 se confirma (201) y la fila
    queda con `materiales = []` en BD."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=0
    )
    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201, resp.text

    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT materiales FROM actividades_reportes "
                    "WHERE seguimiento_id = :s"
                ),
                {"s": seg},
            )
        ).one()
    assert fila.materiales == []


async def test_req_act_005_006_013_entrada_invalida_422_no_crea_registro_en_bd(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-005/006/013: cabecera vacía, límites, celdas inválidas, campos
    extra y caracteres de control => 422 sin fila ni evento en BD."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    invalidos: list[dict[str, object]] = [
        {"vehiculo": "   "},
        {"vehiculo": "x" * 101},
        {"clientes": ""},
        {"clientes": "x" * 501},
        {"direcciones": "  "},
        {"direcciones": "x" * 501},
        {"actividades": []},
        {"actividades": ["a"] * 31},
        {"actividades": ["   "]},
        {"actividades": ["x" * 501]},
        {"comentarios": "x" * 2001},
        {"comentarios": "malo\x07control"},
        {"folio": "R7777"},
        {"fecha": "2030-01-01T00:00:00Z"},
        {"usuario": "hacker"},
        {"materiales": []},
    ]
    for extra in invalidos:
        r = await _post_actividad(client, equipo["equipo_id"], seg, **extra)
        assert r.status_code == 422, (extra, r.text)

    await _sin_registro_ni_evento(session)

    # Límite exacto válido: 30 celdas de 500 caracteres => 1 fila con 30 celdas.
    ok = await _post_actividad(
        client, equipo["equipo_id"], seg, actividades=["x" * 500] * 30
    )
    assert ok.status_code == 201, ok.text
    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT jsonb_array_length(actividades) AS n "
                    "FROM actividades_reportes WHERE seguimiento_id = :s"
                ),
                {"s": seg},
            )
        ).one()
    assert fila.n == 30


async def test_req_act_007_comentarios_null_y_salto_de_linea_persisten_en_bd(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-007: comentarios omitidos => NULL en BD; con salto de línea se
    guardan literalmente."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg1 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    payload = {k: v for k, v in PAYLOAD_BASE.items() if k != "comentarios"}
    r1 = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**payload, "seguimiento_id": seg1},
    )
    assert r1.status_code == 201, r1.text
    r2 = await _post_actividad(
        client, equipo["equipo_id"], seg2, comentarios="línea 1\nlínea 2"
    )
    assert r2.status_code == 201, r2.text

    async with session.begin():
        filas = {
            f.seguimiento_id: f.comentarios
            for f in (
                await session.execute(
                    text("SELECT seguimiento_id, comentarios FROM actividades_reportes")
                )
            ).all()
        }
    assert filas[seg1] is None
    assert filas[seg2] == "línea 1\nlínea 2"


async def test_req_act_008_folio_correlativo_en_bd_y_folio_cliente_rechazado(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-008: `folio_num` 1..n sin huecos en BD, folio del evento con
    formato R0001; un folio enviado por el cliente (422) no crea fila."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg1 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    seg3 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    assert (await _post_actividad(client, equipo["equipo_id"], seg1)).status_code == 201
    assert (await _post_actividad(client, equipo["equipo_id"], seg2)).status_code == 201
    r = await _post_actividad(client, equipo["equipo_id"], seg3, folio="R7777")
    assert r.status_code == 422

    async with session.begin():
        folios = (
            await session.execute(
                text("SELECT folio_num FROM actividades_reportes ORDER BY folio_num")
            )
        ).scalars().all()
        eventos = (
            await session.execute(
                text(
                    "SELECT detalles->>'folio' FROM auditoria_eventos "
                    "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA' ORDER BY id"
                )
            )
        ).scalars().all()
    assert folios == [1, 2]
    assert eventos == ["R0001", "R0002"]


async def test_req_act_009_fecha_en_bd_es_now_timestamptz_y_coincide_con_respuesta(
    client: AsyncClient, session
) -> None:
    """REQ-ACT-009: `created_at` (timestamptz) lo fija PostgreSQL y es el
    mismo instante que devuelve la API; una fecha enviada por el cliente
    (422) no crea fila."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    seg2 = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    r = await _post_actividad(client, equipo["equipo_id"], seg2, fecha="2030-01-01T00:00:00Z")
    assert r.status_code == 422
    assert await _contar(session, SQL_FILAS) == 0

    resp = await _post_actividad(client, equipo["equipo_id"], seg)
    assert resp.status_code == 201, resp.text
    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT created_at, pg_typeof(created_at)::text AS tipo, now() AS ahora "
                    "FROM actividades_reportes WHERE seguimiento_id = :s"
                ),
                {"s": seg},
            )
        ).one()
    assert fila.tipo == "timestamp with time zone"
    assert datetime.fromisoformat(resp.json()["fecha"]) == fila.created_at
    assert timedelta(0) <= fila.ahora - fila.created_at < timedelta(minutes=5)
    assert fila.created_at.astimezone(timezone.utc).year < 2030


async def test_req_act_010_snapshot_en_bd_conserva_valor_unitario_tras_cambio_de_catalogo(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """REQ-ACT-010: el jsonb `materiales` persistido congela el
    valor_unitario vigente al confirmar; el catálogo cambia después y la fila
    NO se altera."""
    material, equipo = await _material_con_stock_en_equipo(client)
    r = await patch_material(client_admin, material["id_lista"], valor_unitario=5.5)
    assert r.status_code == 200
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=2
    )
    assert (await _post_actividad(client, equipo["equipo_id"], seg)).status_code == 201
    r = await patch_material(client_admin, material["id_lista"], valor_unitario=9.999)
    assert r.status_code == 200

    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT materiales FROM actividades_reportes WHERE seguimiento_id = :s"
                ),
                {"s": seg},
            )
        ).one()
        vigente = (
            await session.execute(
                text("SELECT valor_unitario FROM catalogo_materiales WHERE id_lista = :m"),
                {"m": material["id_lista"]},
            )
        ).scalar_one()
    assert float(vigente) == 9.999
    assert len(fila.materiales) == 1
    assert fila.materiales[0]["material_id"] == material["id_lista"]
    assert fila.materiales[0]["valor_unitario"] == 5.5
    assert fila.materiales[0]["cantidad_consumida"] == 2


async def test_req_act_014_019_403_no_crea_registro_y_actor_queda_en_bd(
    client: AsyncClient,
    client_admin: AsyncClient,
    client_sin_scope: AsyncClient,
    session,
) -> None:
    """REQ-ACT-014/019: 403 sin acceso NO crea fila; el administrador crea y
    su actor queda en `usuario` y en el evento; el duplicado (409 canónico)
    no agrega fila ni evento."""
    material, equipo = await _material_con_stock_en_equipo(client)
    seg = await _seguimiento_cerrado(
        client, equipo["equipo_id"], material["id_lista"], consumida=1
    )
    r = await client_sin_scope.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**PAYLOAD_BASE, "seguimiento_id": seg},
    )
    assert r.status_code == 403, r.text
    await _sin_registro_ni_evento(session)

    r = await client_admin.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**PAYLOAD_BASE, "seguimiento_id": seg},
    )
    assert r.status_code == 201, r.text
    dup = await client_admin.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/actividades",
        json={**PAYLOAD_BASE, "seguimiento_id": seg},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "ACTIVIDAD_DUPLICADA"

    async with session.begin():
        usuario = (
            await session.execute(
                text("SELECT usuario FROM actividades_reportes WHERE seguimiento_id = :s"),
                {"s": seg},
            )
        ).scalar_one()
        evento_usuario = (
            await session.execute(
                text(
                    "SELECT usuario FROM auditoria_eventos "
                    "WHERE tipo_accion = 'ACTIVIDAD_CONFIRMADA'"
                )
            )
        ).scalar_one()
    assert usuario == evento_usuario == "admin-qa"
    assert await _contar(session, SQL_FILAS) == 1
    assert await _contar(session, SQL_EVENTOS) == 1
