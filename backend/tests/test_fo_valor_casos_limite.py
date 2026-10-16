"""Complemento de trazabilidad T7 (Fase 8) — casos límite E1..E13 y
escenarios/cláusulas de RF-6, RF-7 y RF-9 que no tenían prueba directa.

Cambio 2026-10-fo-unificado-valor-unitario. Cada prueba asevera la
respuesta HTTP **y** el estado persistido en PostgreSQL; la aritmética de
stock y valor vive en PostgreSQL (nunca en Python).

Mapa (ver `trazabilidad.md`):

* E1  — ajuste a 0 conserva la fila, aporta 0 y se audita (RF-4/RF-6).
* E2  — Valor Unitario 0 permitido por API y BD; aporta 0 (RF-2/RF-4).
* E4  — desbordamiento: la BD también lo rechaza (RF-2, defensa en
  profundidad).
* E5  — notación científica sobre-precisa en CANTIDADES → 422 (RF-6).
* E10 — dos ediciones concurrentes del mismo Valor Unitario (RF-7).
* E11 — cantidad decimal en U.M. `PZ` permitida (RF-6, C-5).
* RF-4 — el Valor Total refleja carga, +Cantidad, Mover, TRANSF, DEVOL,
  cancelaciones y eliminación (sin caché).
* RF-6 — identificadores y `stock_minimo` permanecen enteros; +Cantidad,
  Mover y devolución aceptan decimales.
* RF-7 — evento de valor con actor y fecha; ledger inmutable.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, DataError

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    ajustar_stock,
    borrador_devol,
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    fibra_ajuste,
    fibra_carga_inicial,
    inventario_equipo,
    inventario_fo,
    patch_material,
    procesar,
    stock_seccion,
)

RESUMEN = "/api/v1/inventario/resumen-general"
SUMAR = "/api/v1/inventario/sumar-cantidad"
MOVER = "/api/v1/inventario/mover"
JSON_CT = {"content-type": "application/json"}


async def _valor_db(session, material_id: int) -> Decimal:
    fila = (
        await session.execute(
            text(
                "SELECT valor_unitario FROM catalogo_materiales "
                "WHERE id_lista = :m"
            ),
            {"m": material_id},
        )
    ).scalar_one()
    return Decimal(fila)


async def _eventos(session, tipo: str) -> list[AuditoriaEvento]:
    return list(
        (
            await session.execute(
                select(AuditoriaEvento)
                .where(AuditoriaEvento.tipo_accion == tipo)
                .order_by(AuditoriaEvento.id)
            )
        ).scalars()
    )


async def _stock_bd(session, tabla: str, material_id: int) -> Decimal | None:
    fila = (
        await session.execute(
            text(f"SELECT stock_actual FROM {tabla} WHERE material_id = :m"),  # noqa: S608
            {"m": material_id},
        )
    ).scalar_one_or_none()
    return None if fila is None else Decimal(fila)


# ── E1: ajustar stock a 0 ─────────────────────────────────────────────────


async def test_RF_006_E1_ajuste_a_cero_conserva_fila_aporta_cero_y_audita(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """E1 (RF-4/RF-6): ajustar el stock a 0 está permitido en Inventario
    General y en Inventario FO — la fila se CONSERVA con 0, aporta 0 al
    Valor Total (el resto del inventario sigue contando) y se audita."""
    a = await crear_material(client, descripcion="Material E1 general")
    b = await crear_material(client, descripcion="Material E1 fo")
    c = await crear_material(client, descripcion="Material E1 testigo")
    await carga_inicial(client, material_id=a["id_lista"], cantidad=4)
    await fibra_carga_inicial(client, material_id=b["id_lista"], cantidad=6)
    await carga_inicial(client, material_id=c["id_lista"], cantidad=2)
    await patch_material(client_admin, a["id_lista"], valor_unitario=5)
    await patch_material(client_admin, b["id_lista"], valor_unitario=2)
    await patch_material(client_admin, c["id_lista"], valor_unitario=3)
    # 4×5 + 6×2 + 2×3 = 38
    assert (await client.get(RESUMEN)).json()["valor_total"] == 38

    # General → 0.
    await ajustar_stock(
        client, almacen_id=1, material_id=a["id_lista"], nuevo_stock=0,
        motivo="Conteo en cero",
    )
    # FO → 0.
    await fibra_ajuste(
        client, material_id=b["id_lista"], nuevo_stock=0, motivo="FO en cero"
    )

    # HTTP: la fila sigue visible con 0 en ambas locaciones.
    assert (await stock_seccion(client, 1))[a["id_lista"]] == 0
    assert (await inventario_fo(client))[b["id_lista"]]["stock_actual"] == 0
    # BD: fila conservada con 0.000 (no se borra).
    assert await _stock_bd(session, "inventario_almacen", a["id_lista"]) == Decimal("0.000")
    assert await _stock_bd(session, "inventario_fibra", b["id_lista"]) == Decimal("0.000")
    # Aporte 0: solo cuenta el material testigo (2×3).
    assert (await client.get(RESUMEN)).json()["valor_total"] == 6

    # Auditoría: ambos ajustes registrados con cantidad 0 y diferencial negativo.
    gral = (await _eventos(session, "AJUSTE_INVENTARIO"))[-1]
    assert gral.material_id == a["id_lista"]
    assert gral.cantidad == Decimal("0.000")
    assert (gral.detalles or {})["diferencial"] == Decimal("-4.000")
    fo = (await _eventos(session, "AJUSTE_INVENTARIO_FO"))[-1]
    assert fo.material_id == b["id_lista"]
    assert fo.cantidad == Decimal("0.000")
    assert (fo.detalles or {})["diferencial"] == Decimal("-6.000")


# ── E2: Valor Unitario 0 ──────────────────────────────────────────────────


async def test_RF_002_E2_valor_unitario_cero_permitido_aporta_cero(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """E2 (RF-2/RF-4): `valor_unitario = 0` es válido (>= 0): 200, persiste
    0.000, aporta 0 al Valor Total y se audita como cambio 1.000 → 0.000."""
    a = await crear_material(client, descripcion="Material valor cero")
    b = await crear_material(client, descripcion="Material testigo valor")
    await carga_inicial(client, material_id=a["id_lista"], cantidad=10)
    await carga_inicial(client, material_id=b["id_lista"], cantidad=2)
    await patch_material(client_admin, b["id_lista"], valor_unitario=3)
    assert (await client.get(RESUMEN)).json()["valor_total"] == 16  # 10×1 + 2×3

    resp = await patch_material(client_admin, a["id_lista"], valor_unitario=0)
    assert resp.status_code == 200, resp.text
    assert resp.json()["valor_unitario"] == 0
    assert await _valor_db(session, a["id_lista"]) == Decimal("0.000")

    # Aporta 0: solo el testigo cuenta (2×3).
    assert (await client.get(RESUMEN)).json()["valor_total"] == 6

    evento = [
        e for e in await _eventos(session, "MATERIAL_MODIFICADO")
        if e.material_id == a["id_lista"]
    ]
    assert len(evento) == 1
    det = evento[0].detalles or {}
    assert Decimal(str(det["valores_anteriores"]["valor_unitario"])) == Decimal("1.000")
    assert Decimal(str(det["valores_nuevos"]["valor_unitario"])) == Decimal("0.000")


# ── E4: la BD también rechaza el desbordamiento ───────────────────────────


async def test_RF_002_E4_bd_rechaza_desbordamiento_aunque_se_salte_la_api(
    client: AsyncClient, session
) -> None:
    """E4 (RF-2, defensa en profundidad): un valor > 999 999 999.999
    escrito directo en PostgreSQL desborda NUMERIC(12,3) y se rechaza; el
    valor previo no cambia."""
    m = await crear_material(client, descripcion="Material desborde BD")
    with pytest.raises(DataError):
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET valor_unitario = 1000000000 "
                "WHERE id_lista = :m"
            ),
            {"m": m["id_lista"]},
        )
        await session.commit()
    await session.rollback()
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")

    # El máximo exacto SÍ cabe (límite inclusivo).
    await session.execute(
        text(
            "UPDATE catalogo_materiales SET valor_unitario = 999999999.999 "
            "WHERE id_lista = :m"
        ),
        {"m": m["id_lista"]},
    )
    await session.commit()
    assert await _valor_db(session, m["id_lista"]) == Decimal("999999999.999")


# ── E5: notación científica en cantidades ────────────────────────────────


@pytest.mark.parametrize("literal", ["1e-4", "1E-4", "1.5e-3"])
async def test_RF_006_E5_cantidad_en_notacion_cientifica_sobre_precisa_422(
    client: AsyncClient, session, literal: str
) -> None:
    """E5 (RF-6): una CANTIDAD en notación científica con más de 3
    decimales efectivos (1e-4 = 0.0001) se rechaza con 422 en carga
    inicial, ajuste y FO, sin alterar existencias ni ledger."""
    m = await crear_material(client, descripcion=f"Material E5 {literal}")
    mid = m["id_lista"]
    await carga_inicial(client, material_id=mid, cantidad=3)
    await fibra_carga_inicial(client, material_id=mid, cantidad=3)

    casos = [
        ("/api/v1/ajustes/carga-inicial",
         f'{{"almacen_id": 1, "material_id": {mid}, "cantidad": {literal}}}'),
        ("/api/v1/ajustes/stock-almacen",
         f'{{"almacen_id": 1, "material_id": {mid}, "nuevo_stock": {literal},'
         ' "motivo": "E5"}'),
        ("/api/v1/fibra/ajuste",
         f'{{"material_id": {mid}, "nuevo_stock": {literal}, "motivo": "E5"}}'),
        ("/api/v1/fibra/carga-inicial",
         f'{{"material_id": {mid}, "cantidad": {literal}}}'),
    ]
    for ruta, cuerpo in casos:
        resp = await client.post(ruta, content=cuerpo, headers=JSON_CT)
        assert resp.status_code == 422, (ruta, resp.text)

    assert (await stock_seccion(client, 1))[mid] == 3
    assert (await inventario_fo(client))[mid]["stock_actual"] == 3
    assert await _stock_bd(session, "inventario_almacen", mid) == Decimal("3.000")
    assert await _stock_bd(session, "inventario_fibra", mid) == Decimal("3.000")
    assert await _eventos(session, "AJUSTE_INVENTARIO") == []
    assert await _eventos(session, "AJUSTE_INVENTARIO_FO") == []


# ── E10: ediciones concurrentes del mismo Valor Unitario ─────────────────


async def test_RF_007_E10_ediciones_concurrentes_ultima_escritura_prevalece(
    client: AsyncClient, client_admin: AsyncClient, client_factory, session
) -> None:
    """E10 (RF-7): dos ediciones concurrentes del mismo Valor Unitario
    terminan con 200; prevalece la última escritura válida y AMBAS generan
    evento (la cadena anterior→nuevo es consistente: el segundo evento
    parte del valor que dejó el primero)."""
    m = await crear_material(client, descripcion="Material E10")
    mid = m["id_lista"]
    a1, a2 = client_factory("admin-qa"), client_factory("admin-qa")
    try:
        r1, r2 = await asyncio.gather(
            patch_material(a1, mid, valor_unitario=2.5),
            patch_material(a2, mid, valor_unitario=3.5),
        )
    finally:
        await a1.aclose()
        await a2.aclose()
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    final = await _valor_db(session, mid)
    assert final in (Decimal("2.500"), Decimal("3.500"))
    # La API refleja el valor persistido (la última escritura).
    resp = await client.get(f"/api/v1/catalogo/{mid}")
    assert Decimal(str(resp.json()["valor_unitario"])) == final

    eventos = [
        e.detalles or {}
        for e in await _eventos(session, "MATERIAL_MODIFICADO")
        if e.material_id == mid
    ]
    assert len(eventos) == 2, eventos
    cadena = [
        (
            Decimal(str(d["valores_anteriores"]["valor_unitario"])),
            Decimal(str(d["valores_nuevos"]["valor_unitario"])),
        )
        for d in eventos
    ]
    assert cadena[0][0] == Decimal("1.000")
    assert cadena[1][0] == cadena[0][1]          # eslabones encadenados
    assert cadena[1][1] == final                 # la última escritura prevalece
    assert {cadena[0][1], cadena[1][1]} == {Decimal("2.500"), Decimal("3.500")}


# ── E11 + RF-6: decimales en PZ; identificadores y stock_minimo enteros ──


async def test_RF_006_E11_cantidad_decimal_en_um_piezas_permitida(
    client: AsyncClient, session
) -> None:
    """E11 (RF-6, C-5): una cantidad decimal en un material con U.M. `PZ`
    es válida (sin restricción por U.M.): 200 y persistida exacta."""
    m = await crear_material(client, descripcion="Material PZ decimal", u_m="PZ")
    assert m["u_m"] == "PZ"
    await carga_inicial(client, material_id=m["id_lista"], cantidad=2.5)
    resp = await client.post(
        SUMAR,
        json={"destino": "GENERAL", "material_id": m["id_lista"], "cantidad": 0.25},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_nuevo"] == 2.75
    assert (await stock_seccion(client, 1))[m["id_lista"]] == 2.75
    assert await _stock_bd(
        session, "inventario_almacen", m["id_lista"]
    ) == Decimal("2.750")


async def test_RF_006_identificadores_y_stock_minimo_permanecen_enteros(
    client: AsyncClient, session
) -> None:
    """RF-6 (Ubiquitous): los identificadores son enteros sin decimales y
    `stock_minimo` permanece entero → una fracción se rechaza (422) sin
    alterar nada."""
    m = await crear_material(client, descripcion="Material enteros", stock_minimo=5)
    mid = m["id_lista"]

    # Identificadores con decimales → 422.
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 1, "material_id": mid + 0.5, "cantidad": 1},
    )
    assert resp.status_code == 422, resp.text
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={"almacen_id": 1.5, "material_id": mid, "cantidad": 1},
    )
    assert resp.status_code == 422, resp.text

    # stock_minimo fraccionario: alta y PATCH → 422.
    resp = await client.post(
        "/api/v1/catalogo",
        json={"descripcion": "Stock mínimo decimal", "u_m": "PZ", "stock_minimo": 1.5},
    )
    assert resp.status_code == 422, resp.text
    resp = await patch_material(client, mid, stock_minimo=2.5)
    assert resp.status_code == 422, resp.text

    # Estado persistido: stock_minimo intacto (entero) y sin existencias.
    fila = (
        await session.execute(
            text("SELECT stock_minimo FROM catalogo_materiales WHERE id_lista = :m"),
            {"m": mid},
        )
    ).scalar_one()
    assert fila == 5
    assert isinstance(fila, int)
    assert (await stock_seccion(client, 1)) == {}
    n = (
        await session.execute(
            text("SELECT count(*) FROM catalogo_materiales WHERE descripcion = :d"),
            {"d": "Stock mínimo decimal"},
        )
    ).scalar_one()
    assert n == 0


# ── RF-6: +Cantidad, Mover y devolución con decimales ────────────────────


async def test_RF_006_sumar_cantidad_y_mover_aceptan_decimales(
    client: AsyncClient, session
) -> None:
    """RF-6: +Cantidad y Mover aceptan cantidades decimales; PostgreSQL
    suma/descuenta exactamente y el ledger conserva NUMERIC(12,3)."""
    m = await crear_material(client, descripcion="Material operadores decimal")
    mid = m["id_lista"]
    await carga_inicial(client, material_id=mid, cantidad=3)
    await fibra_carga_inicial(client, material_id=mid, cantidad=1)

    resp = await client.post(
        SUMAR, json={"destino": "GENERAL", "material_id": mid, "cantidad": 0.5}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_nuevo"] == 3.5

    resp = await client.post(
        MOVER,
        json={"origen": "GENERAL", "destino": "FO", "material_id": mid,
              "cantidad": 1.25},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["stock_origen"], body["stock_destino"]) == (2.25, 2.25)

    assert await _stock_bd(session, "inventario_almacen", mid) == Decimal("2.250")
    assert await _stock_bd(session, "inventario_fibra", mid) == Decimal("2.250")
    suma = (await _eventos(session, "SUMA_CANTIDAD"))[0]
    assert suma.cantidad == Decimal("0.500")
    mover = (await _eventos(session, "MOVIMIENTO_INVENTARIO"))[0]
    assert mover.cantidad == Decimal("1.250")


async def test_RF_006_devolucion_fraccionaria_y_cancelacion_exacta(
    client: AsyncClient, session
) -> None:
    """RF-6: una devolución con cantidad decimal descuenta la Unidad e
    incrementa el origen exactamente; el detalle del movimiento conserva
    NUMERIC(12,3) y cancelarla revierte las cantidades originales."""
    m = await crear_material(client, descripcion="Material devol decimal")
    mid = m["id_lista"]
    await carga_inicial(client, material_id=mid, cantidad=5)
    equipo = await crear_equipo(client, nombre="Unidad devol decimal")
    eq = equipo["equipo_id"]
    b = await borrador_teams(
        client, almacen_id=1, equipo_id=eq, material_id=mid, cantidad=4
    )
    await procesar(client, b["id"])

    d = await borrador_devol(
        client, equipo_id=eq, almacen_id=1, material_id=mid, cantidad=1.5
    )
    await procesar(client, d["id"])

    assert (await stock_seccion(client, 1))[mid] == 2.5            # 1 + 1.5
    assert (await inventario_equipo(client, eq))[mid]["stock_actual"] == 2.5
    detalle = (
        await session.execute(
            text("SELECT cantidad FROM movimientos_detalle WHERE movimiento_id = :v"),
            {"v": d["id"]},
        )
    ).scalar_one()
    assert Decimal(detalle) == Decimal("1.500")

    resp = await client.post(
        f"/api/v1/movimientos/{d['id']}/cancelar", json={"motivo": "Revertir devol"}
    )
    assert resp.status_code == 200, resp.text
    assert (await stock_seccion(client, 1))[mid] == 1
    assert (await inventario_equipo(client, eq))[mid]["stock_actual"] == 4
    assert await _stock_bd(session, "inventario_almacen", mid) == Decimal("1.000")


# ── RF-7: actor/fecha, ledger inmutable, eventos históricos ──────────────


async def test_RF_007_evento_de_valor_registra_material_fecha_y_es_consultable(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-7: el evento de cambio de Valor Unitario registra MATERIAL y
    marca de tiempo, con valores anterior/nuevo, y es consultable por la
    API del ledger. (La atribución del ACTOR se cubre en
    `..._atribuye_al_actor_http`.)"""
    m = await crear_material(client, descripcion="Material fecha-ledger")
    antes = datetime.now(timezone.utc) - timedelta(minutes=5)
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=2.5)
    assert resp.status_code == 200, resp.text

    ev = [
        e for e in await _eventos(session, "MATERIAL_MODIFICADO")
        if e.material_id == m["id_lista"]
    ]
    assert len(ev) == 1
    assert ev[0].usuario  # actor no vacío
    assert ev[0].created_at is not None
    assert antes <= ev[0].created_at <= datetime.now(timezone.utc) + timedelta(minutes=1)

    resp = await client.get("/api/v1/auditoria", params={"material_id": m["id_lista"]})
    assert resp.status_code == 200, resp.text
    api = [e for e in resp.json()["eventos"] if e["tipo_accion"] == "MATERIAL_MODIFICADO"]
    assert len(api) == 1
    assert api[0]["created_at"]
    assert api[0]["detalles"]["valores_anteriores"]["valor_unitario"] == 1.0
    assert api[0]["detalles"]["valores_nuevos"]["valor_unitario"] == 2.5


async def test_RF_007_evento_de_valor_atribuye_al_actor_http(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-7: `usuario` del evento = actor que ejecutó el PATCH ('admin-qa'),
    en BD y en la API del ledger (igual que UM_MODIFICADA en SEC-001)."""
    m = await crear_material(client, descripcion="Material actor-ledger")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=2.5)
    assert resp.status_code == 200, resp.text
    ev = [
        e for e in await _eventos(session, "MATERIAL_MODIFICADO")
        if e.material_id == m["id_lista"]
    ]
    assert len(ev) == 1
    assert ev[0].usuario == "admin-qa"
    resp = await client.get("/api/v1/auditoria", params={"material_id": m["id_lista"]})
    api = [e for e in resp.json()["eventos"] if e["tipo_accion"] == "MATERIAL_MODIFICADO"]
    assert api[0]["usuario"] == "admin-qa"


async def test_RF_007_ledger_inmutable_update_y_delete_rechazados(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-7/Constitución §2.4: los eventos del ledger (incluido el de
    Valor Unitario) no se pueden actualizar ni borrar — el trigger de
    PostgreSQL lo rechaza y el evento queda íntegro."""
    m = await crear_material(client, descripcion="Material ledger inmutable")
    await patch_material(client_admin, m["id_lista"], valor_unitario=7.5)
    ev = [
        e for e in await _eventos(session, "MATERIAL_MODIFICADO")
        if e.material_id == m["id_lista"]
    ][0]
    eid, usuario = ev.id, ev.usuario

    for sentencia in (
        "UPDATE auditoria_eventos SET usuario = 'alterado' WHERE id = :i",
        "DELETE FROM auditoria_eventos WHERE id = :i",
    ):
        with pytest.raises(DBAPIError) as exc:
            await session.execute(text(sentencia), {"i": eid})
            await session.commit()
        assert "append-only" in str(exc.value)
        await session.rollback()

    fila = (
        await session.execute(
            text("SELECT usuario, tipo_accion FROM auditoria_eventos WHERE id = :i"),
            {"i": eid},
        )
    ).one()
    assert (fila.usuario, fila.tipo_accion) == (usuario, "MATERIAL_MODIFICADO")


# ── RF-4: el Valor Total refleja TODA mutación de existencias ────────────


async def test_RF_004_valor_total_refleja_cada_mutacion_de_existencias(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-4 (Event-driven): carga, +Cantidad, Mover, TRANSF, devolución,
    cancelación y eliminación cambian el Valor Total calculado por
    PostgreSQL de inmediato (sin caché). Valor Unitario = 2.

    General 10 → 20 · +5 → 30 · Mover 4 a FO → 30 (se conserva) ·
    TRANSF 3 → 24 (C-6: lo entregado sale del total) · DEVOL 1 → 26 ·
    cancelar DEVOL → 24 · cancelar TRANSF → 30 · eliminar FO (4) → 22."""
    m = await crear_material(client, descripcion="Material valor mutaciones")
    mid = m["id_lista"]
    await patch_material(client_admin, mid, valor_unitario=2)

    async def total() -> float:
        resp = await client.get(RESUMEN)
        assert resp.status_code == 200, resp.text
        return resp.json()["valor_total"]

    await carga_inicial(client, material_id=mid, cantidad=10)
    assert await total() == 20

    resp = await client.post(
        SUMAR, json={"destino": "GENERAL", "material_id": mid, "cantidad": 5}
    )
    assert resp.status_code == 200, resp.text
    assert await total() == 30

    resp = await client.post(
        MOVER,
        json={"origen": "GENERAL", "destino": "FO", "material_id": mid, "cantidad": 4},
    )
    assert resp.status_code == 200, resp.text
    assert await total() == 30

    equipo = await crear_equipo(client, nombre="Unidad valor mutaciones")
    eq = equipo["equipo_id"]
    t = await borrador_teams(
        client, almacen_id=1, equipo_id=eq, material_id=mid, cantidad=3
    )
    await procesar(client, t["id"])
    assert await total() == 24

    d = await borrador_devol(
        client, equipo_id=eq, almacen_id=1, material_id=mid, cantidad=1
    )
    await procesar(client, d["id"])
    assert await total() == 26

    resp = await client.post(
        f"/api/v1/movimientos/{d['id']}/cancelar", json={"motivo": "Valor devol"}
    )
    assert resp.status_code == 200, resp.text
    assert await total() == 24
    resp = await client.post(
        f"/api/v1/movimientos/{t['id']}/cancelar", json={"motivo": "Valor transf"}
    )
    assert resp.status_code == 200, resp.text
    assert await total() == 30

    resp = await client.delete(
        f"/api/v1/fibra/materiales/{mid}", params={"motivo": "Baja FO valor"}
    )
    assert resp.status_code == 204, resp.text
    assert await total() == 22

    # BD: PostgreSQL es la autoridad del cálculo (mismo valor, exacto).
    exacto = (await session.execute(text("SELECT fn_valor_total_inventario()"))).scalar_one()
    assert Decimal(exacto) == Decimal("22.000")
