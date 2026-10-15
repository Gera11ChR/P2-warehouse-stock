"""Existencias y cantidades decimales — RF-6 (cambio
2026-10-fo-unificado-valor-unitario).

Cantidades con hasta 3 decimales (máximo 999 999 999.999) en inventarios,
movimientos, seguimientos y ledger; invariante de saldo no negativo con
decimales; reversión EXACTA de cancelaciones; sobre-precisión → 422 sin
efectos; concurrencia FOR UPDATE con decimales; y auditoría con cantidades
decimales (NUMERIC(12,3)).
"""

import asyncio
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    ajustar_stock,
    borrador_teams,
    cancelar,
    carga_inicial,
    crear_equipo,
    crear_material,
    fibra_carga_inicial,
    inventario_equipo,
    inventario_fo,
    procesar,
    stock_seccion,
)


async def _eventos(session, tipo: str) -> list[AuditoriaEvento]:
    return (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == tipo
            )
        )
    ).scalars().all()


async def test_RF_006_ajuste_fraccionario_7_250(
    client: AsyncClient, session
) -> None:
    """RF-6: ajustar el stock de un material a 7.250 → la API y la BD
    devuelven 7.250 y el evento de auditoría registra el diferencial
    decimal (NUMERIC exacto, sin redondeo silencioso)."""
    m = await crear_material(client, descripcion="Material fraccionario")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=5)

    await ajustar_stock(
        client,
        almacen_id=1,
        material_id=m["id_lista"],
        nuevo_stock=7.25,
        motivo="Conteo fraccionario",
    )

    assert (await stock_seccion(client, 1))[m["id_lista"]] == 7.25
    fila = (
        await session.execute(
            text(
                "SELECT stock_actual FROM inventario_almacen "
                "WHERE material_id = :m"
            ),
            {"m": m["id_lista"]},
        )
    ).scalar_one()
    assert Decimal(fila) == Decimal("7.250")

    evento = (await _eventos(session, "AJUSTE_INVENTARIO"))[0]
    assert evento.cantidad == Decimal("7.250")
    assert (evento.detalles or {})["diferencial"] == Decimal("2.250")


async def test_RF_006_transferencia_2_5_y_cancelacion_reversion_exacta(
    client: AsyncClient, session
) -> None:
    """RF-6: transferir 2.5 a una Unidad y cancelar el movimiento → el
    origen vuelve EXACTAMENTE a su cantidad original y la Unidad a la suya
    (cero filas fantasma); el detalle y el ledger conservan Decimal."""
    m = await crear_material(client, descripcion="Material 2.5")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=5)
    equipo = await crear_equipo(client, nombre="Unidad decimal")

    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"],
        cantidad=2.5,
    )
    await procesar(client, b["id"])

    assert (await stock_seccion(client, 1))[m["id_lista"]] == 2.5
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[m["id_lista"]]["stock_actual"] == 2.5

    detalle_bd = (
        await session.execute(
            text(
                "SELECT cantidad FROM movimientos_detalle "
                "WHERE movimiento_id = :mv"
            ),
            {"mv": b["id"]},
        )
    ).scalar_one()
    assert Decimal(detalle_bd) == Decimal("2.500")

    await cancelar(client, b["id"], motivo="Cancelación decimal")

    assert (await stock_seccion(client, 1))[m["id_lista"]] == 5
    assert m["id_lista"] not in await inventario_equipo(
        client, equipo["equipo_id"]
    )
    evento = (await _eventos(session, "MOVIMIENTO_CANCELADO"))[0]
    assert evento.cantidad == Decimal("2.500")


async def test_RF_006_sobre_precision_1_0005_422_sin_efectos(
    client: AsyncClient, session
) -> None:
    """RF-6: una cantidad 1.0005 (4 decimales) → 422 y NINGUNA existencia
    cambia (sin redondeo silencioso)."""
    m = await crear_material(client, descripcion="Material sobre-preciso")
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 1, "material_id": m["id_lista"], "cantidad": 1.0005},
    )
    assert resp.status_code == 422, resp.text

    assert (await stock_seccion(client, 1)) == {}
    assert await _eventos(session, "STOCK_INICIAL") == []

    # Ajuste FO también rechaza sobre-precisión (defensa de esquema).
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={"material_id": m["id_lista"], "cantidad": 1.0005},
    )
    assert resp.status_code == 422, resp.text
    assert (await inventario_fo(client)) == {}


async def test_RF_006_saldo_nunca_negativo_con_decimales(
    client: AsyncClient, session
) -> None:
    """RF-6: pedir 2.5 con stock 2.4 → 400 (RAISE canónico de PostgreSQL) y
    el saldo jamás se vuelve negativo."""
    m = await crear_material(client, descripcion="Material insuficiente")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=2.4)
    equipo = await crear_equipo(client, nombre="Unidad negada")

    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"],
        cantidad=2.5,
    )
    resp = await client.post(
        "/api/v1/movimientos/procesar", json={"movimiento_id": b["id"]}
    )
    assert resp.status_code == 400, resp.text
    assert (await stock_seccion(client, 1))[m["id_lista"]] == 2.4
    assert m["id_lista"] not in await inventario_equipo(
        client, equipo["equipo_id"]
    )
    assert await _eventos(session, "TEAMS_TRANSFERENCIA") == []


async def test_RF_006_concurrencia_8_vs_7_sobre_stock_10(
    client: AsyncClient, client_factory, session
) -> None:
    """RF-6: dos TRANSF simultáneas intentan consumir 8 y 7 de un stock de
    10 → el FOR UPDATE concede UNA y rechaza la otra (400/422); el stock
    final nunca es negativo."""
    m = await crear_material(client, descripcion="Material concurrente")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)
    equipo = await crear_equipo(client, nombre="Unidad concurrencia")

    b8 = await borrador_teams(
        client, almacen_id=1, equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"], cantidad=8,
    )
    b7 = await borrador_teams(
        client, almacen_id=1, equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"], cantidad=7,
    )

    c1, c2 = client_factory(), client_factory()
    try:
        r = await asyncio.gather(
            c1.post(
                "/api/v1/movimientos/procesar",
                json={"movimiento_id": b8["id"]},
            ),
            c2.post(
                "/api/v1/movimientos/procesar",
                json={"movimiento_id": b7["id"]},
            ),
        )
    finally:
        await c1.aclose()
        await c2.aclose()

    codigos = sorted(x.status_code for x in r)
    assert codigos == [200, 400], [x.text for x in r]

    # Una sola transacción concluyó: stock final ∈ {2, 3} y nunca negativo.
    stock_final = (await stock_seccion(client, 1))[m["id_lista"]]
    assert stock_final in (2, 3)
    entregado = (await inventario_equipo(client, equipo["equipo_id"]))[
        m["id_lista"]
    ]["stock_actual"]
    assert (stock_final, entregado) in ((2, 8), (3, 7))


async def test_RF_006_evento_auditoria_con_cantidad_decimal(
    client: AsyncClient, session
) -> None:
    """RF-6: la cantidad del ledger es decimal — un ajuste FO a 7.250
    audita AJUSTE_INVENTARIO_FO con cantidad NUMERIC(12,3) exacta."""
    m = await crear_material(client, descripcion="Material ledger decimal")
    await fibra_carga_inicial(client, material_id=m["id_lista"], cantidad=3)

    resp = await client.post(
        "/api/v1/fibra/ajuste",
        json={
            "material_id": m["id_lista"],
            "nuevo_stock": 7.25,
            "motivo": "Ledger decimal",
        },
    )
    assert resp.status_code == 200, resp.text
    assert (await inventario_fo(client))[m["id_lista"]]["stock_actual"] == 7.25

    evento = (await _eventos(session, "AJUSTE_INVENTARIO_FO"))[0]
    assert evento.cantidad == Decimal("7.250")
    assert (evento.detalles or {})["diferencial"] == Decimal("4.250")


async def test_RF_006_seguimiento_con_cantidades_decimales(
    client: AsyncClient, session
) -> None:
    """RF-6: las cantidades tomadas y consumidas de los seguimientos son
    decimales y el consumo descuenta exactamente el stock de la Unidad."""
    m = await crear_material(client, descripcion="Material seguimiento")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)
    equipo = await crear_equipo(client, nombre="Unidad seguimiento")
    b = await borrador_teams(
        client, almacen_id=1, equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"], cantidad=2.5,
    )
    await procesar(client, b["id"])

    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos",
        json={
            "items": [{"material_id": m["id_lista"], "cantidad_tomada": 2.5}]
        },
    )
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/equipos/{equipo['equipo_id']}/seguimientos/{sid}/cerrar",
        json={
            "consumidos": [
                {"material_id": m["id_lista"], "cantidad_consumida": 1.25}
            ]
        },
    )
    assert resp.status_code == 200, resp.text

    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[m["id_lista"]]["stock_actual"] == 1.25

    item_bd = (
        await session.execute(
            text(
                "SELECT cantidad_tomada, cantidad_consumida "
                "FROM seguimiento_items WHERE seguimiento_id = :s"
            ),
            {"s": sid},
        )
    ).one()
    assert Decimal(item_bd.cantidad_tomada) == Decimal("2.500")
    assert Decimal(item_bd.cantidad_consumida) == Decimal("1.250")

    evento = (await _eventos(session, "SEGUIMIENTO_CERRADO"))[0]
    assert evento.cantidad == Decimal("1.250")
    assert (evento.detalles or {})["cantidad_consumida"] == Decimal("1.250")
