"""Flujo DESPLIEGUE de campo (0014) — REQ-DEPLOY-001..006.

Cubre el ciclo ABIERTA -> CERRADA delegado íntegramente a las stored
functions fn_crear_despliegue / fn_cerrar_despliegue: apertura con ítems y
cantidades tomadas, registro de observaciones, cierre con sobrantes, ajuste
atómico del stock del equipo, auditoría inmutable (DESPLIEGUE_CREADO /
DESPLIEGUE_CERRADO), rollback total ante stock insuficiente, máquina de
estados 404/409, aislamiento por integrante de equipo y serialización de
cierres concurrentes por bloqueos FOR UPDATE.
"""

import asyncio
from datetime import date

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text

from app.models import AuditoriaEvento, InventarioEquipo
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    procesar,
)


async def _setup_equipo_stock(
    client: AsyncClient,
    *,
    cantidad: int = 50,
    stock_minimo: int | None = None,
) -> tuple[dict, dict]:
    """Equipo con stock real vía TEAMS desde el Inventario General."""
    material = await crear_material(
        client,
        descripcion="Material Despliegue",
        stock_minimo=stock_minimo,
    )
    equipo = await crear_equipo(client, nombre="Equipo Despliegue")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=cantidad,
    )
    await procesar(client, b["id"])
    return material, equipo


async def _crear_despliegue(
    client: AsyncClient,
    equipo_id: int,
    items: list[dict],
    observaciones: str | None = None,
    expect: int = 201,
) -> Response:
    payload: dict = {"items": items}
    if observaciones is not None:
        payload["observaciones"] = observaciones
    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/despliegues", json=payload
    )
    assert resp.status_code == expect, resp.text
    return resp


async def _cerrar_despliegue(
    client: AsyncClient,
    equipo_id: int,
    despliegue_id: int,
    sobrantes: list[dict] | None = None,
    expect: int = 200,
) -> Response:
    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/despliegues/{despliegue_id}/cerrar",
        json={"sobrantes": sobrantes or []},
    )
    assert resp.status_code == expect, resp.text
    return resp


@pytest.mark.critical
async def test_REQ_DEPLOY_001_002_crear_despliegue_201_estado_abierta_con_items(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-001/002: la apertura devuelve 201 con estado ABIERTA,
    fecha del día, usuario del actor y las líneas con su cantidad_tomada
    registrada (sobrante/consumida aún NULL)."""
    material, equipo = await _setup_equipo_stock(client)

    resp = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    body = resp.json()
    assert body["estado"] == "ABIERTA"
    assert body["fecha"] == date.today().isoformat()
    assert body["usuario"] == "qa"
    assert body["closed_at"] is None
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["material_id"] == material["id_lista"]
    assert item["cantidad_tomada"] == 20
    assert item["cantidad_sobrante"] is None
    assert item["cantidad_consumida"] is None


@pytest.mark.critical
async def test_REQ_DEPLOY_003_observaciones_registradas_y_devueltas(
    client: AsyncClient, session
) -> None:
    """REQ-DEPLOY-003: las observaciones operativas del despliegue se
    registran en la cabecera, se devuelven en el payload y quedan
    inmutables en el evento DESPLIEGUE_CREADO."""
    material, equipo = await _setup_equipo_stock(client)

    resp = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 5}],
        observaciones="Corte en Av. Central — 3 cuadrillas",
    )
    body = resp.json()
    assert body["observaciones"] == "Corte en Av. Central — 3 cuadrillas"

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "DESPLIEGUE_CREADO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["despliegue_id"] == body["id"]
    assert detalles["observaciones"] == "Corte en Av. Central — 3 cuadrillas"
    assert detalles["cantidad_items"] == 1
    assert evento.usuario == "qa"


async def test_REQ_DEPLOY_001_segundo_despliegue_abierto_mismo_equipo_409(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-001: UN SOLO despliegue abierto por equipo — la segunda
    apertura es rechazada con 409 por fn_crear_despliegue (índice único
    parcial como red de seguridad)."""
    material, equipo = await _setup_equipo_stock(client)
    await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 5}],
    )

    resp = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 3}],
        expect=409,
    )
    assert "ya posee un despliegue abierto" in resp.json()["error"]["message"]


@pytest.mark.critical
async def test_REQ_DEPLOY_004_005_cierre_con_sobrantes_200_estado_cerrada(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004/005: el cierre con sobrantes devuelve 200, transiciona
    a CERRADA con closed_at y materializa cantidad_consumida = tomada -
    sobrante en cada línea del ledger."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    despliegue_id = creado.json()["id"]

    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        despliegue_id,
        [{"material_id": material["id_lista"], "cantidad_sobrante": 5}],
    )
    body = resp.json()
    assert body["estado"] == "CERRADA"
    assert body["closed_at"] is not None
    item = next(
        i for i in body["items"] if i["material_id"] == material["id_lista"]
    )
    assert item["cantidad_sobrante"] == 5
    assert item["cantidad_consumida"] == 15


@pytest.mark.critical
async def test_REQ_DEPLOY_005_stock_equipo_ajustado_y_auditoria_por_linea(
    client: AsyncClient, session
) -> None:
    """REQ-DEPLOY-005: el cierre descuenta el consumido del inventario del
    equipo (50 - 15 = 35) y audita DESPLIEGUE_CERRADO por línea con
    tomada/sobrante/consumida/stock_remanente y el actor del header."""
    material, equipo = await _setup_equipo_stock(client, cantidad=50)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": 5}],
    )

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 35

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "DESPLIEGUE_CERRADO"
            )
        )
    ).scalars().one()
    assert evento.usuario == "qa"
    assert evento.material_id == material["id_lista"]
    assert evento.cantidad == 15
    detalles = evento.detalles or {}
    assert detalles["despliegue_id"] == creado.json()["id"]
    assert detalles["cantidad_tomada"] == 20
    assert detalles["cantidad_sobrante"] == 5
    assert detalles["cantidad_consumida"] == 15
    assert detalles["stock_remanente_equipo"] == 35


async def test_REQ_DEPLOY_006_despliegue_creado_auditado(
    client: AsyncClient, session
) -> None:
    """REQ-DEPLOY-006: la apertura emite el evento inmutable
    DESPLIEGUE_CREADO capturando actor, equipo, materiales y cantidades."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 8}],
    )

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "DESPLIEGUE_CREADO"
            )
        )
    ).scalars().one()
    assert evento.usuario == "qa"
    assert evento.resultado == "EXITO"
    assert evento.equipo_destino_id == equipo["equipo_id"]
    detalles = evento.detalles or {}
    assert detalles["despliegue_id"] == creado.json()["id"]
    assert detalles["cantidad_items"] == 1


async def test_REQ_DEPLOY_005_doble_cierre_409_sin_doble_ajuste(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-005 (máquina de estados): el segundo cierre es 409 y el
    stock NO se descuenta dos veces."""
    material, equipo = await _setup_equipo_stock(client, cantidad=50)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": 5}],
    )

    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": 0}],
        expect=409,
    )
    assert "no se encuentra en estado ABIERTA" in resp.json()["error"]["message"]

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 35


async def test_REQ_DEPLOY_004_cierre_despliegue_inexistente_404(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004: cerrar un despliegue inexistente clasifica 404 antes
    de tocar la stored function."""
    _, equipo = await _setup_equipo_stock(client)
    resp = await _cerrar_despliegue(
        client, equipo["equipo_id"], 9999, expect=404
    )
    assert resp.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_REQ_DEPLOY_004_sobrante_mayor_tomada_400(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004: sobrante > cantidad tomada es rechazado por
    fn_cerrar_despliegue con 400 (validación autoritativa en PostgreSQL)."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": 21}],
        expect=400,
    )
    assert "Sobrante inválido" in resp.json()["error"]["message"]


async def test_REQ_DEPLOY_004_sobrante_negativo_422(client: AsyncClient) -> None:
    """REQ-DEPLOY-004: sobrante negativo viola el esquema (ge=0) → 422."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": -1}],
        expect=422,
    )


async def test_REQ_DEPLOY_004_sobrante_material_ajeno_400(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004: un sobrante de un material que no pertenece al
    despliegue es rechazado con 400."""
    material, equipo = await _setup_equipo_stock(client)
    ajeno = await crear_material(client, descripcion="Material ajeno")
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": ajeno["id_lista"], "cantidad_sobrante": 1}],
        expect=400,
    )
    assert "no pertenece a este despliegue" in resp.json()["error"]["message"]


async def test_REQ_DEPLOY_004_sobrante_duplicado_422(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004: líneas de sobrante duplicadas violan el validator del
    esquema → 422."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues/"
        f"{creado.json()['id']}/cerrar",
        json={
            "sobrantes": [
                {"material_id": material["id_lista"], "cantidad_sobrante": 2},
                {"material_id": material["id_lista"], "cantidad_sobrante": 3},
            ]
        },
    )
    assert resp.status_code == 422


async def test_REQ_DEPLOY_002_items_duplicados_422(client: AsyncClient) -> None:
    """REQ-DEPLOY-002: duplicar un material en la lista de despliegue viola
    el validator del esquema → 422."""
    material, equipo = await _setup_equipo_stock(client)
    resp = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [
            {"material_id": material["id_lista"], "cantidad_tomada": 5},
            {"material_id": material["id_lista"], "cantidad_tomada": 7},
        ],
        expect=422,
    )


async def test_REQ_DEPLOY_005_cierre_stock_insuficiente_400_rollback_total(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-005 + Constitución 4.1: si el consumido supera el stock
    del equipo, fn_cerrar_despliegue hace RAISE y la transacción completa
    revierte — estado sigue ABIERTA, stock intacto y sobrantes en NULL."""
    material, equipo = await _setup_equipo_stock(client, cantidad=30)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 50}],
    )
    despliegue_id = creado.json()["id"]

    resp = await _cerrar_despliegue(
        client, equipo["equipo_id"], despliegue_id, expect=400
    )
    assert "Stock insuficiente en el Equipo" in resp.json()["error"]["message"]

    detalle = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues/{despliegue_id}"
    )
    assert detalle.status_code == 200
    body = detalle.json()
    assert body["estado"] == "ABIERTA"
    assert body["closed_at"] is None
    item = next(
        i for i in body["items"] if i["material_id"] == material["id_lista"]
    )
    assert item["cantidad_sobrante"] is None

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 30


async def test_REQ_DEPLOY_004_linea_omitida_sobrante_cero(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-004: las líneas omitidas en el cierre se cierran con
    sobrante 0 (consumida = tomada)."""
    material, equipo = await _setup_equipo_stock(client)
    extra = await crear_material(client, descripcion="Material extra")
    await carga_inicial(
        client, material_id=extra["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=extra["id_lista"],
        cantidad=40,
    )
    await procesar(client, b["id"])

    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [
            {"material_id": material["id_lista"], "cantidad_tomada": 10},
            {"material_id": extra["id_lista"], "cantidad_tomada": 10},
        ],
    )
    resp = await _cerrar_despliegue(
        client,
        equipo["equipo_id"],
        creado.json()["id"],
        [{"material_id": material["id_lista"], "cantidad_sobrante": 3}],
    )
    items = {i["material_id"]: i for i in resp.json()["items"]}
    assert items[material["id_lista"]]["cantidad_sobrante"] == 3
    assert items[material["id_lista"]]["cantidad_consumida"] == 7
    assert items[extra["id_lista"]]["cantidad_sobrante"] == 0
    assert items[extra["id_lista"]]["cantidad_consumida"] == 10


async def test_REQ_DEPLOY_001_aislamiento_no_integrante_403(
    client: AsyncClient, client_factory, session
) -> None:
    """REQ-DEPLOY-001 + SEC-003: un actor con scope pero SIN membresía en el
    equipo recibe 403 en crear, listar y cerrar despliegues."""
    material, equipo = await _setup_equipo_stock(client)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 5}],
    )
    await session.execute(
        text(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('extrano', 1)"
        )
    )
    await session.commit()

    ext = client_factory("extrano")
    try:
        resp = await ext.post(
            f"/api/v1/equipos/{equipo['equipo_id']}/despliegues",
            json={
                "items": [
                    {"material_id": material["id_lista"], "cantidad_tomada": 3}
                ]
            },
        )
        assert resp.status_code == 403

        resp = await ext.get(f"/api/v1/equipos/{equipo['equipo_id']}/despliegues")
        assert resp.status_code == 403

        resp = await ext.post(
            f"/api/v1/equipos/{equipo['equipo_id']}/despliegues/"
            f"{creado.json()['id']}/cerrar",
            json={"sobrantes": []},
        )
        assert resp.status_code == 403
    finally:
        await ext.aclose()


async def test_REQ_DEPLOY_001_admin_pase_transversal(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-DEPLOY-001: el administrador opera despliegues de cualquier
    equipo sin ser integrante (pase transversal, Constitution 3.1)."""
    material, equipo = await _setup_equipo_stock(client)

    resp = await _crear_despliegue(
        client_admin,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 10}],
    )
    assert resp.status_code == 201
    despliegue_id = resp.json()["id"]

    resp = await client_admin.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues"
    )
    assert resp.status_code == 200
    assert resp.json()["despliegues"][0]["id"] == despliegue_id

    resp = await _cerrar_despliegue(
        client_admin,
        equipo["equipo_id"],
        despliegue_id,
        [{"material_id": material["id_lista"], "cantidad_sobrante": 2}],
    )
    assert resp.json()["estado"] == "CERRADA"


@pytest.mark.critical
async def test_REQ_DEPLOY_005_concurrencia_dos_cierres_serializados(
    client: AsyncClient, client_factory, session
) -> None:
    """REQ-DEPLOY-005 + Constitución 2.3: dos cierres simultáneos del mismo
    despliegue — el bloqueo FOR UPDATE sobre la cabecera otorga el cierre a
    UN solo request (200) y rechaza limpio al otro (409) con un ÚNICO ajuste
    de stock y una sola línea de auditoría DESPLIEGUE_CERRADO."""
    material, equipo = await _setup_equipo_stock(client, cantidad=50)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 20}],
    )
    despliegue_id = creado.json()["id"]

    c1 = client_factory()
    c2 = client_factory()

    async def disparar(c: AsyncClient) -> int:
        resp = await c.post(
            f"/api/v1/equipos/{equipo['equipo_id']}/despliegues/"
            f"{despliegue_id}/cerrar",
            json={
                "sobrantes": [
                    {
                        "material_id": material["id_lista"],
                        "cantidad_sobrante": 5,
                    }
                ]
            },
        )
        return resp.status_code

    try:
        resultados = await asyncio.gather(disparar(c1), disparar(c2))
    finally:
        await c1.aclose()
        await c2.aclose()

    assert sorted(resultados) == [200, 409]

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert filas[material["id_lista"]]["stock_actual"] == 35

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "DESPLIEGUE_CERRADO"
            )
        )
    ).scalars().all()
    assert len(eventos) == 1


async def test_REQ_DEPLOY_001_listado_ordenado_y_detalle_equipo_equivocado_404(
    client: AsyncClient,
) -> None:
    """REQ-DEPLOY-001: el listado devuelve el historial más reciente primero
    y el detalle consultado bajo un equipo ajeno clasifica 404."""
    material, equipo = await _setup_equipo_stock(client)
    otro_equipo = await crear_equipo(client, nombre="Equipo Vecino")
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 5}],
    )

    resp = await client.get(
        f"/api/v1/equipos/{equipo['equipo_id']}/despliegues"
    )
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()["despliegues"]]
    assert ids == [creado.json()["id"]]

    resp = await client.get(
        f"/api/v1/equipos/{otro_equipo['equipo_id']}/despliegues/"
        f"{creado.json()['id']}"
    )
    assert resp.status_code == 404


async def test_REQ_DEPLOY_005_fila_stock_cero_conservada_y_oculta_en_lectura(
    client: AsyncClient, session
) -> None:
    """REQ-DEPLOY-005: el consumo total (sobrante 0) NO elimina la fila
    física de inventario_equipos (queda en stock 0), pero GET inventario la
    oculta (filtro stock_actual > 0, cero fantasmas)."""
    material, equipo = await _setup_equipo_stock(client, cantidad=50)
    creado = await _crear_despliegue(
        client,
        equipo["equipo_id"],
        [{"material_id": material["id_lista"], "cantidad_tomada": 50}],
    )
    await _cerrar_despliegue(
        client, equipo["equipo_id"], creado.json()["id"], expect=200
    )

    fila = (
        await session.execute(
            select(InventarioEquipo).where(
                InventarioEquipo.equipo_id == equipo["equipo_id"],
                InventarioEquipo.material_id == material["id_lista"],
            )
        )
    ).scalar_one()
    assert fila.stock_actual == 0

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in filas
