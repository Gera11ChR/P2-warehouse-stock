"""Transferencias TEAMS/DEVOL hacia y desde el Inventario FO unificado —
RF-1/RF-9 (cambio 2026-10-fo-unificado-valor-unitario).

La sección de ruteo única 'FO' (y las secciones legacy FO_PAQUETE/
FO_EN_USO, conservadas como valores históricos) enrutan hacia el MISMO
`inventario_fibra` unificado por `material_id` (RF-1/RF-9): validación de
stock, cancelaciones simétricas y aislamiento por scope/sección (SEC-002)
y por integrante de la unidad (V3). Los eventos TEAMS_TRANSFERENCIA /
DEVOL_DEVOLUCION / MOVIMIENTO_CANCELADO ya no registran `modulo_fo`.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    cancelar,
    crear_equipo,
    crear_material,
    fibra_carga_inicial,
    inventario_equipo,
    inventario_fo,
    procesar,
    seccion_fo,
)

ALMACEN_PAQUETE = 2  # sección legacy FO_PAQUETE (valor histórico, RF-9)
ALMACEN_EN_USO = 3   # sección legacy FO_EN_USO (valor histórico, RF-9)


async def _scopes_fo(session, *ids: int) -> None:
    """Scope de sección para los almacenes FO (SEC-002)."""
    for i in ids:
        await session.execute(
            text(
                "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
                "VALUES ('qa', :i) ON CONFLICT DO NOTHING"
            ),
            {"i": i},
        )
    await session.commit()


async def _setup_fo(
    client: AsyncClient,
    session,
    *,
    cantidad: int | float = 50,
    seccion_id: int | None = None,
) -> tuple[dict, dict, int]:
    """Material + Inventario FO unificado sembrado + unidad (integrante qa).
    Devuelve (material, unidad, almacen_id_de_origen)."""
    fo = await seccion_fo(client)
    origen = seccion_id if seccion_id is not None else fo["almacen_id"]
    await _scopes_fo(session, origen)
    material = await crear_material(client, descripcion="Cable FO QA")
    await fibra_carga_inicial(
        client, material_id=material["id_lista"], cantidad=cantidad
    )
    equipo = await crear_equipo(client, nombre="Equipo FO")
    return material, equipo, origen


@pytest.mark.critical
async def test_REQ_FO_001_002_teams_desde_fo_200_ajuste_y_auditoria(
    client: AsyncClient, session
) -> None:
    """RF-1: TEAMS desde "Inventario FO" (sección de ruteo única) descuenta
    `inventario_fibra` unificado, acredita la unidad y audita
    TEAMS_TRANSFERENCIA con stock_remanente_origen (sin modulo_fo)."""
    material, equipo, origen = await _setup_fo(client, session)

    b = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 20

    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 30

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo_fo" not in detalles
    assert detalles["stock_remanente_origen"] == 20
    assert evento.almacen_origen_id == origen
    assert evento.cantidad == 30


async def test_RF_9_teams_desde_origen_legacy_en_uso_enruta_fo_unificado(
    client: AsyncClient, session
) -> None:
    """RF-9: un TRANSF cuyo origen es la sección legacy FO_EN_USO (almacén 3)
    descuenta el Inventario FO UNIFICADO — los orígenes antiguos enrutan al
    mismo inventario (compatibilidad con movimientos históricos)."""
    material, equipo, _ = await _setup_fo(client, session, seccion_id=ALMACEN_EN_USO)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_EN_USO,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 20
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 30

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "TEAMS_TRANSFERENCIA"
            )
        )
    ).scalars().one()
    assert evento.almacen_origen_id == ALMACEN_EN_USO
    assert (evento.detalles or {}).get("stock_remanente_origen") == 20


async def test_REQ_FO_002_teams_fo_stock_insuficiente_400(
    client: AsyncClient, session
) -> None:
    """RF-1/RF-6: comportamiento uniforme — stock insuficiente en el
    Inventario FO hace RAISE y mapea a 400 sin alterar inventarios."""
    material, equipo, origen = await _setup_fo(client, session)

    b = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=60,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en Origen (Inventario FO)" in resp.json()["error"][
        "message"
    ]

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 50
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in equipo_filas


async def test_REQ_FO_002_devol_hacia_fo_200_ajuste(
    client: AsyncClient, session
) -> None:
    """RF-1: DEVOL desde la unidad hacia el Inventario FO incrementa
    `inventario_fibra` unificado y descuenta la unidad."""
    material, equipo, origen = await _setup_fo(client, session)

    b1 = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])

    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=origen,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 30
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 20

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "DEVOL_DEVOLUCION"
            )
        )
    ).scalars().one()
    assert "modulo_fo" not in (evento.detalles or {})
    assert evento.almacen_destino_id == origen


async def test_REQ_FO_002_cancelar_teams_fo_restituye_inventario_fibra(
    client: AsyncClient, session
) -> None:
    """RF-1/RF-6: cancelar un TEAMS-FO restituye el Inventario FO unificado
    y descuenta la unidad (reversión simétrica auditada)."""
    material, equipo, origen = await _setup_fo(client, session)

    b = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])
    await cancelar(client, b["id"], motivo="FO errónea")

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 50
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in equipo_filas

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MOVIMIENTO_CANCELADO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo_fo" not in detalles
    assert detalles["motivo_cancelacion"] == "FO errónea"


async def test_RF_9_cancelar_teams_legacy_restituye_fo_unificado(
    client: AsyncClient, session
) -> None:
    """RF-9: cancelar un TRANSF CONFIRMADO cuyo origen era la sección legacy
    FO_PAQUETE revierte EXACTAMENTE contra el Inventario FO unificado
    (restauración simétrica, cero pérdida)."""
    material, equipo, _ = await _setup_fo(client, session, seccion_id=ALMACEN_PAQUETE)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])
    await cancelar(client, b["id"], motivo="FO errónea")

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 50
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in equipo_filas

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MOVIMIENTO_CANCELADO"
            )
        )
    ).scalars().one()
    assert evento.almacen_origen_id == ALMACEN_PAQUETE
    assert (evento.detalles or {})["motivo_cancelacion"] == "FO errónea"


async def test_REQ_FO_002_cancelar_devol_fo_restituye_equipo(
    client: AsyncClient, session
) -> None:
    """RF-1: cancelar una DEVOL-FO restituye la unidad y descuenta el
    Inventario FO destino (simetría exacta del procesamiento)."""
    material, equipo, origen = await _setup_fo(client, session)

    b1 = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=origen,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])
    await cancelar(client, b2["id"], motivo="DEVOL FO errónea")

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 20
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 30


async def test_RF_9_secciones_transferibles_incluyen_fo_excluyen_legacy(
    client: AsyncClient,
) -> None:
    """RF-1/RF-9: las secciones transferibles emiten la sección única FO
    (transferible=true aunque is_active=false) y EXCLUYEN las secciones
    legacy FO_PAQUETE/FO_EN_USO (no seleccionables en el dominio vivo),
    sin alterar el contrato de GET /secciones."""
    fo = await seccion_fo(client)
    resp = await client.get("/api/v1/inventario/secciones/transferibles")
    assert resp.status_code == 200
    por_id = {s["almacen_id"]: s for s in resp.json()}
    assert fo["almacen_id"] in por_id
    tipos = {s["tipo"] for s in resp.json()}
    assert tipos == {"GENERAL", "FO"}
    # Legacy excluidos (RF-9: los orígenes antiguos no se ofrecen).
    assert ALMACEN_PAQUETE not in por_id
    assert ALMACEN_EN_USO not in por_id
    assert por_id[fo["almacen_id"]]["nombre"] == "Inventario FO"
    assert all(s["transferible"] is True for s in resp.json())

    resp = await client.get("/api/v1/inventario/secciones")
    assert [s["almacen_id"] for s in resp.json()] == [1]


async def test_REQ_FO_002_borrador_fo_seccion_inactiva_permitido(
    client: AsyncClient, session
) -> None:
    """RF-1: el borrador TEAMS contra la sección FO se acepta aunque la
    sección esté is_active=false (manejador de ruteo, no inventario)."""
    material, equipo, origen = await _setup_fo(client, session)

    b = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=5,
    )
    assert b["estado"] == "BORRADOR"


async def test_REQ_FO_002_sin_scope_fo_403(client: AsyncClient) -> None:
    """RF-1 + SEC-002: sin scope sobre la sección FO, la creación del
    borrador TEAMS es rechazada con 403 (default-deny)."""
    fo = await seccion_fo(client)
    material = await crear_material(client, descripcion="FO sin scope")
    equipo = await crear_equipo(client, nombre="Equipo sin scope")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": fo["almacen_id"],
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 5}],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"


async def test_REQ_FO_002_no_integrante_destino_403(
    client: AsyncClient, session
) -> None:
    """RF-1 + V3: un actor con scope FO pero SIN membresía en la unidad
    destino recibe 403 al crear el borrador TEAMS."""
    fo = await seccion_fo(client)
    await _scopes_fo(session, fo["almacen_id"])
    material = await crear_material(client, descripcion="FO ajeno")
    equipo = await crear_equipo(
        client, nombre="Equipo ajeno", integrantes=["otro"]
    )
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": fo["almacen_id"],
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 5}],
        },
    )
    assert resp.status_code == 403


async def test_REQ_FO_002_cancelacion_revertir_sin_stock_equipo_400(
    client: AsyncClient, session
) -> None:
    """RF-1: reversión no-negativa — si la unidad ya no dispone del stock a
    revertir, fn_cancelar_movimiento hace RAISE y mapea a 400 dejando el
    movimiento CONFIRMADO."""
    material, equipo, origen = await _setup_fo(client, session)

    b1 = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=origen,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    resp = await client.post(
        f"/api/v1/movimientos/{b1['id']}/cancelar",
        json={"motivo": "Revertir sin stock"},
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en la Unidad destino" in resp.json()["error"][
        "message"
    ]

    detalle = await client.get(f"/api/v1/movimientos/{b1['id']}")
    assert detalle.json()["estado"] == "CONFIRMADO"


@pytest.mark.critical
async def test_REQ_TRF_INV_003_devol_post_eliminacion_recrea_fila_upsert(
    client: AsyncClient, session
) -> None:
    """REQ-TRF-INV-003: tras eliminar la fila FO (DELETE con motivo), una
    devolución DEVOL posterior hacia la raíz FO recrea la fila vía el UPSERT
    de fn_procesar_movimiento — traza auditable ELIMINACION_FO →
    DEVOL_DEVOLUCION sin corrupción de stock."""
    material, equipo, origen = await _setup_fo(client, session)

    b1 = await borrador_teams(
        client,
        almacen_id=origen,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])

    # Eliminación FÍSICA de la fila del Inventario FO (REQ-DEL-001):
    # el stock eliminado (20) queda registrado en el ledger.
    resp = await client.delete(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        params={"motivo": "Depuración previa a devolución"},
    )
    assert resp.status_code == 204
    filas = await inventario_fo(client)
    assert material["id_lista"] not in filas

    # DEVOL desde la unidad hacia el Inventario FO: el UPSERT
    # INSERT ... ON CONFLICT (material_id) DO UPDATE recrea la fila.
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=origen,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 10
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 20

    # Traza auditable ELIMINACION_FO → DEVOL_DEVOLUCION, en ese orden exacto.
    eventos = (
        await session.execute(
            select(AuditoriaEvento)
            .where(
                AuditoriaEvento.material_id == material["id_lista"],
                AuditoriaEvento.tipo_accion.in_(
                    ["ELIMINACION_FO", "DEVOL_DEVOLUCION"]
                ),
            )
            .order_by(AuditoriaEvento.id.asc())
        )
    ).scalars().all()
    assert [e.tipo_accion for e in eventos] == [
        "ELIMINACION_FO",
        "DEVOL_DEVOLUCION",
    ]

    eliminacion = eventos[0]
    assert "modulo" not in (eliminacion.detalles or {})
    assert (eliminacion.detalles or {})["stock_eliminado"] == 20

    devolucion = eventos[1]
    assert "modulo_fo" not in (devolucion.detalles or {})
    assert devolucion.cantidad == 10
