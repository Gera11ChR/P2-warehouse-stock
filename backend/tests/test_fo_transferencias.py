"""Transferencias TEAMS/DEVOL hacia y desde Fibra Óptica — REQ-FO-001/002.

Enrutamiento aditivo de fn_procesar_movimiento / fn_cancelar_movimiento
(migración 0014): las secciones FO_PAQUETE (almacén 2) y FO_EN_USO
(almacén 3) son manejadores de ruteo hacia inventario_fibra con la MISMA
lógica uniforme del Inventario General — validación de stock, auditoría con
`modulo_fo`, cancelaciones simétricas y aislamiento por scope/sección
(SEC-002) y por integrante de equipo (V3).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import AuditoriaEvento, InventarioFibra
from tests.helpers.fabrica import (
    borrador_devol,
    borrador_teams,
    cancelar,
    crear_equipo,
    crear_material,
    fibra_carga_inicial,
    inventario_equipo,
    procesar,
)

MODULO_PAQUETE = "PAQUETE"
MODULO_EN_USO = "EN_USO"
ALMACEN_PAQUETE = 2
ALMACEN_EN_USO = 3


async def _scopes_fo(session) -> None:
    """Scope de sección para los almacenes FO (SEC-002)."""
    await session.execute(
        text(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('qa', 2), ('qa', 3)"
        )
    )
    await session.commit()


async def _stock_fibra(client: AsyncClient, modulo: str) -> dict[int, dict]:
    resp = await client.get(f"/api/v1/fibra/{modulo}")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f for f in resp.json()}


async def _setup_fo(
    client: AsyncClient, session, *, modulo: str = MODULO_PAQUETE, cantidad: int = 50
) -> tuple[dict, dict]:
    """Material + inventario FO sembrado + equipo (integrante qa)."""
    await _scopes_fo(session)
    material = await crear_material(client, descripcion="Cable FO QA")
    await fibra_carga_inicial(
        client, modulo=modulo, material_id=material["id_lista"], cantidad=cantidad
    )
    equipo = await crear_equipo(client, nombre="Equipo FO")
    return material, equipo


@pytest.mark.critical
async def test_REQ_FO_001_002_teams_desde_paquete_200_ajuste_y_auditoria(
    client: AsyncClient, session
) -> None:
    """REQ-FO-001/002: TEAMS desde "Fibra Óptica - Paquete" (almacén 2)
    descuenta inventario_fibra(PAQUETE), acredita el equipo y audita
    TEAMS_TRANSFERENCIA con detalles.modulo_fo='PAQUETE'."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])

    filas = await _stock_fibra(client, MODULO_PAQUETE)
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
    assert detalles["modulo_fo"] == MODULO_PAQUETE
    assert evento.cantidad == 30


async def test_REQ_FO_001_002_teams_desde_en_uso_200_ajuste_y_auditoria(
    client: AsyncClient, session
) -> None:
    """REQ-FO-001/002: TEAMS desde "Fibra Óptica - En Uso" (almacén 3)
    descuenta inventario_fibra(EN_USO) con auditoría modulo_fo='EN_USO'."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_EN_USO)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_EN_USO,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])

    filas = await _stock_fibra(client, MODULO_EN_USO)
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
    assert (evento.detalles or {})["modulo_fo"] == MODULO_EN_USO


async def test_REQ_FO_002_teams_fo_stock_insuficiente_400(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: comportamiento uniforme — stock insuficiente en el módulo
    FO hace RAISE y mapea a 400 sin alterar inventarios."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=60,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en Origen (Módulo FO" in resp.json()["error"][
        "message"
    ]

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 50
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert material["id_lista"] not in equipo_filas


async def test_REQ_FO_002_devol_hacia_fo_paquete_200_ajuste(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: DEVOL desde el equipo hacia FO_PAQUETE incrementa
    inventario_fibra(PAQUETE), descuenta el equipo y audita modulo_fo."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b1 = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])

    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=ALMACEN_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    filas = await _stock_fibra(client, MODULO_PAQUETE)
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
    assert (evento.detalles or {})["modulo_fo"] == MODULO_PAQUETE


async def test_REQ_FO_002_cancelar_teams_fo_restituye_inventario_fibra(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: cancelar un TEAMS-FO restituye inventario_fibra y
    descuenta el equipo (reversión simétrica auditada con modulo_fo)."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b["id"])
    await cancelar(client, b["id"], motivo="FO errónea")

    filas = await _stock_fibra(client, MODULO_PAQUETE)
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
    assert detalles["modulo_fo"] == MODULO_PAQUETE
    assert detalles["motivo_cancelacion"] == "FO errónea"


async def test_REQ_FO_002_cancelar_devol_fo_restituye_equipo(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: cancelar una DEVOL-FO restituye el equipo y descuenta el
    inventario_fibra destino (simetría exacta del procesamiento)."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b1 = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=ALMACEN_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])
    await cancelar(client, b2["id"], motivo="DEVOL FO errónea")

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 20
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[material["id_lista"]]["stock_actual"] == 30


async def test_REQ_FO_001_secciones_transferibles_incluyen_fo(
    client: AsyncClient, session
) -> None:
    """REQ-FO-001: las secciones transferibles reconocen explícitamente
    ambos almacenes FO como opciones de transferencia (transferible=true
    aunque is_active=false), sin alterar el contrato de GET /secciones."""
    await _scopes_fo(session)

    resp = await client.get("/api/v1/inventario/secciones/transferibles")
    assert resp.status_code == 200
    por_id = {s["almacen_id"]: s for s in resp.json()}
    assert set(por_id) == {1, 2, 3}
    assert por_id[1]["tipo"] == "GENERAL"
    assert por_id[2]["tipo"] == "FO_PAQUETE"
    assert por_id[3]["tipo"] == "FO_EN_USO"
    assert all(s["transferible"] is True for s in por_id.values())

    resp = await client.get("/api/v1/inventario/secciones")
    assert [s["almacen_id"] for s in resp.json()] == [1]


async def test_REQ_FO_002_borrador_fo_seccion_inactiva_permitido(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: el borrador TEAMS contra una sección FO se acepta aunque
    la sección esté is_active=false (manejador de ruteo, no inventario)."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=5,
    )
    assert b["estado"] == "BORRADOR"


async def test_REQ_FO_002_sin_scope_fo_403(client: AsyncClient) -> None:
    """REQ-FO-002 + SEC-002: sin scope sobre la sección FO, la creación del
    borrador TEAMS es rechazada con 403 (default-deny)."""
    material = await crear_material(client, descripcion="FO sin scope")
    equipo = await crear_equipo(client, nombre="Equipo sin scope")
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": ALMACEN_PAQUETE,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 5}],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"


async def test_REQ_FO_002_no_integrante_destino_403(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002 + V3: un actor con scope FO pero SIN membresía en el
    equipo destino recibe 403 al crear el borrador TEAMS."""
    await _scopes_fo(session)
    material = await crear_material(client, descripcion="FO ajeno")
    equipo = await crear_equipo(
        client, nombre="Equipo ajeno", integrantes=["otro"]
    )
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": ALMACEN_PAQUETE,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": material["id_lista"], "cantidad": 5}],
        },
    )
    assert resp.status_code == 403


async def test_REQ_FO_002_cancelacion_revertir_sin_stock_equipo_400(
    client: AsyncClient, session
) -> None:
    """REQ-FO-002: reversión no-negativa — si el equipo ya no dispone del
    stock a revertir, fn_cancelar_movimiento hace RAISE y mapea a 400
    dejando el movimiento CONFIRMADO."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b1 = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b1["id"])
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=ALMACEN_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    resp = await client.post(
        f"/api/v1/movimientos/{b1['id']}/cancelar",
        json={"motivo": "Revertir sin stock"},
    )
    assert resp.status_code == 400
    assert "Stock insuficiente en el Equipo destino" in resp.json()["error"][
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
    preexistente de fn_procesar_movimiento — traza auditable
    ELIMINACION_FO → DEVOL_DEVOLUCION sin corrupción de stock."""
    material, equipo = await _setup_fo(client, session, modulo=MODULO_PAQUETE)

    b1 = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=30,
    )
    await procesar(client, b1["id"])

    # Eliminación FÍSICA de la fila FO del módulo PAQUETE (REQ-DEL-001):
    # el stock eliminado (20) queda registrado en el ledger.
    resp = await client.delete(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
        params={"motivo": "Depuración previa a devolución"},
    )
    assert resp.status_code == 204
    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert material["id_lista"] not in filas

    # DEVOL desde el equipo hacia la raíz FO: el UPSERT
    # INSERT ... ON CONFLICT (modulo, material_id) DO UPDATE recrea la fila.
    b2 = await borrador_devol(
        client,
        equipo_id=equipo["equipo_id"],
        almacen_id=ALMACEN_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    await procesar(client, b2["id"])

    filas = await _stock_fibra(client, MODULO_PAQUETE)
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
    assert (eliminacion.detalles or {})["modulo"] == MODULO_PAQUETE
    assert (eliminacion.detalles or {})["stock_eliminado"] == 20

    devolucion = eventos[1]
    assert (devolucion.detalles or {})["modulo_fo"] == MODULO_PAQUETE
    assert devolucion.cantidad == 10
