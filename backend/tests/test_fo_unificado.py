"""Inventario FO unificado (RF-1) y compatibilidad con movimientos
históricos (RF-9) — cambio 2026-10-fo-unificado-valor-unitario.

RF-1: una sola existencia FO por material, sin `modulo` en el contrato
vivo (enviarlo → 422 sin efectos). RF-9: movimientos históricos con
orígenes/destinos legacy FO_PAQUETE/FO_EN_USO siguen consultables,
procesables (BORRADOR, E8) y cancelables contra el Inventario FO unificado
(reversión exacta), y las secciones legacy no son seleccionables.
"""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
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

ALMACEN_PAQUETE = 2  # sección legacy FO_PAQUETE (histórica, RF-9)
ALMACEN_EN_USO = 3   # sección legacy FO_EN_USO (histórica, RF-9)


# ── RF-1: una sola existencia por material, sin subapartados ──────────────


async def test_RF_001_una_fila_por_material_y_modulo_rechazado(
    client: AsyncClient, session
) -> None:
    """RF-1: el Inventario FO mantiene UNA fila por material; enviar
    `modulo` a una operación FO devuelve 422 SIN efectos en la BD."""
    m1 = await crear_material(client, descripcion="FO unificado A")
    m2 = await crear_material(client, descripcion="FO unificado B")
    await fibra_carga_inicial(client, material_id=m1["id_lista"], cantidad=10)
    await fibra_carga_inicial(client, material_id=m2["id_lista"], cantidad=5)

    filas = await inventario_fo(client)
    assert {f["material_id"]: f["stock_actual"] for f in filas.values()} == {
        m1["id_lista"]: 10,
        m2["id_lista"]: 5,
    }
    for fila in filas.values():
        assert "modulo" not in fila

    # RF-1 (Unwanted): modulo en carga-inicial → 422, sin efectos en BD.
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={"modulo": "PAQUETE", "material_id": m1["id_lista"], "cantidad": 99},
    )
    assert resp.status_code == 422
    assert "modulo" in str(resp.json())
    filas = await inventario_fo(client)
    assert filas[m1["id_lista"]]["stock_actual"] == 10

    # En la BD: una sola fila por material (PK material_id, sin columna modulo).
    rows = (
        await session.execute(
            text("SELECT material_id, stock_actual FROM inventario_fibra "
                 "ORDER BY material_id")
        )
    ).all()
    assert [(r.material_id, r.stock_actual) for r in rows] == [
        (m1["id_lista"], Decimal("10.000")),
        (m2["id_lista"], Decimal("5.000")),
    ]
    cols = (
        await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'inventario_fibra'"
            )
        )
    ).scalars().all()
    assert "modulo" not in cols


async def test_RF_001_modulo_rechazado_en_toda_operacion_fo(
    client: AsyncClient, session
) -> None:
    """RF-1: `modulo` es rechazado (422) en carga inicial, ajuste y PATCH de
    Inventario FO, sin efectos secundarios en existencias ni ledger."""
    m = await crear_material(client, descripcion="FO anti-modulo")
    await fibra_carga_inicial(client, material_id=m["id_lista"], cantidad=7)

    casos = [
        (
            "post",
            "/api/v1/fibra/carga-inicial",
            {"modulo": "PAQUETE", "material_id": m["id_lista"], "cantidad": 1},
        ),
        (
            "post",
            "/api/v1/fibra/ajuste",
            {"modulo": "EN_USO", "material_id": m["id_lista"],
             "nuevo_stock": 1, "motivo": "X"},
        ),
        (
            "patch",
            f"/api/v1/fibra/materiales/{m['id_lista']}",
            {"modulo": "PAQUETE", "descripcion": "Cambio prohibido"},
        ),
    ]
    for metodo, ruta, payload in casos:
        resp = await getattr(client, metodo)(ruta, json=payload)
        assert resp.status_code == 422, (ruta, resp.text)

    filas = await inventario_fo(client)
    assert filas[m["id_lista"]]["stock_actual"] == 7
    assert filas[m["id_lista"]]["descripcion"] == "FO anti-modulo"

    ajustes = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert ajustes == []


# ── RF-9: compatibilidad con movimientos históricos ───────────────────────


async def test_RF_009_cancelar_transf_confirmado_origen_legacy_en_uso_restaura(
    client: AsyncClient, session
) -> None:
    """RF-9: cancelar un TRANSF CONFIRMADO previo a la migración cuyo origen
    era FO En Uso (cantidad 3) REVIERTE contra el Inventario FO unificado:
    la existencia aumenta exactamente 3, el movimiento queda CANCELADO y el
    motivo se registra en el ledger."""
    m = await crear_material(client, descripcion="FO histórico EN_USO")
    mid = m["id_lista"]
    # Estado post-migración: el material conserva su existencia unificada
    # (7 = stock que quedó tras el consumo histórico).
    await fibra_carga_inicial(client, material_id=mid, cantidad=7)
    equipo = await crear_equipo(client, nombre="Unidad histórica")
    eq = equipo["equipo_id"]

    # Siembra DIRECTA del movimiento histórico CONFIRMADO (pre-0027): la
    # unidad conserva las 3 unidades entregadas y la línea referencia la
    # sección legacy FO_EN_USO (almacén 3).
    await session.execute(
        text(
            "INSERT INTO inventario_equipos "
            "(equipo_id, material_id, stock_actual, ultimo_movimiento_id) "
            "VALUES (:eq, :m, 3, NULL)"
        ),
        {"eq": eq, "m": mid},
    )
    await session.execute(
        text(
            "INSERT INTO movimientos_cabecera "
            "(tipo_movimiento, estado, usuario, origen_almacen_id, "
            "destino_equipo_id) "
            "VALUES ('TEAMS','CONFIRMADO','qa',:origen,:eq) RETURNING id"
        ),
        {"origen": ALMACEN_EN_USO, "eq": eq},
    )
    mv = (
        await session.execute(
            text("SELECT max(id) FROM movimientos_cabecera")
        )
    ).scalar_one()
    await session.execute(
        text(
            "INSERT INTO movimientos_detalle "
            "(movimiento_id, material_id, cantidad, origen_almacen_id) "
            "VALUES (:mv, :m, 3, :origen)"
        ),
        {"mv": mv, "m": mid, "origen": ALMACEN_EN_USO},
    )
    await session.commit()

    await cancelar(client, mv, motivo="Baja histórica EN_USO")

    # Reversión EXACTA contra el FO unificado (7 + 3 = 10).
    filas = await inventario_fo(client)
    assert filas[mid]["stock_actual"] == 10
    # La unidad devuelve las 3 unidades (fila 0: sin fantasmas).
    equipo_filas = await inventario_equipo(client, eq)
    assert mid not in equipo_filas

    resp = await client.get(f"/api/v1/movimientos/{mv}")
    assert resp.json()["estado"] == "CANCELADO"

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MOVIMIENTO_CANCELADO"
            )
        )
    ).scalars().one()
    assert evento.almacen_origen_id == ALMACEN_EN_USO
    assert evento.cantidad == 3
    assert (evento.detalles or {})["motivo_cancelacion"] == (
        "Baja histórica EN_USO"
    )


async def test_RF_009_borrador_legacy_origen_paquete_procesable(
    client: AsyncClient, session
) -> None:
    """RF-9/E8: un movimiento BORRADOR en curso con origen legacy FO_PAQUETE
    (previo a la migración) se puede CONFIRMAR contra el Inventario FO
    unificado."""
    from sqlalchemy import text

    m = await crear_material(client, descripcion="FO borrador legacy")
    mid = m["id_lista"]
    await fibra_carga_inicial(client, material_id=mid, cantidad=20)
    equipo = await crear_equipo(client, nombre="Unidad legacy")
    await session.execute(
        text(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "VALUES ('qa', :i) ON CONFLICT DO NOTHING"
        ),
        {"i": ALMACEN_PAQUETE},
    )
    await session.commit()

    b = await borrador_teams(
        client,
        almacen_id=ALMACEN_PAQUETE,
        equipo_id=equipo["equipo_id"],
        material_id=mid,
        cantidad=8,
    )
    await procesar(client, b["id"])

    filas = await inventario_fo(client)
    assert filas[mid]["stock_actual"] == 12
    equipo_filas = await inventario_equipo(client, equipo["equipo_id"])
    assert equipo_filas[mid]["stock_actual"] == 8


async def test_RF_009_secciones_legacy_no_seleccionables(
    client: AsyncClient,
) -> None:
    """RF-9: el selector de origen/destino (secciones/transferibles) ofrece
    SOLO "Inventario FO" — las secciones legacy FO_PAQUETE/FO_EN_USO no
    aparecen como opciones."""
    fo = await seccion_fo(client)
    resp = await client.get("/api/v1/inventario/secciones/transferibles")
    assert resp.status_code == 200
    datos = resp.json()
    tipos = [s["tipo"] for s in datos]
    assert tipos == ["GENERAL", "FO"] or set(tipos) == {"GENERAL", "FO"}
    assert ALMACEN_PAQUETE not in {s["almacen_id"] for s in datos}
    assert ALMACEN_EN_USO not in {s["almacen_id"] for s in datos}
    fo_seccion = next(s for s in datos if s["tipo"] == "FO")
    assert fo_seccion["nombre"] == "Inventario FO"
    assert fo_seccion["almacen_id"] == fo["almacen_id"]
    assert fo_seccion["transferible"] is True
