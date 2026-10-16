"""Inventario FO unificado (RF-1) y compatibilidad con movimientos
históricos (RF-9) — cambio 2026-10-fo-unificado-valor-unitario.

RF-1: una sola existencia FO por material, sin `modulo` en el contrato
vivo (enviarlo → 422 sin efectos). RF-4 (2026-10-purga-legacy-fo): las
secciones legacy FO_PAQUETE/FO_EN_USO fueron purgadas (0028); un
`almacen_id` purgado responde 422 «Sección … inexistente».
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

# Ids de las secciones legacy ya purgadas (0028): NO existen; se usan solo
# para verificar el rechazo 422 (RF-4).
ALMACEN_PAQUETE = 2
ALMACEN_EN_USO = 3


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


# ── RF-4: secciones legacy purgadas (cambio 2026-10-purga-legacy-fo) ─────


async def test_RF_4_secciones_transferibles_solo_general_y_fo(
    client: AsyncClient, session
) -> None:
    """RF-4: el selector de origen/destino (secciones/transferibles) ofrece
    SOLO GENERAL activas e "Inventario FO"; los ids 2 y 3 (antes legacy) ya
    no existen en la base."""
    fo = await seccion_fo(client)
    resp = await client.get("/api/v1/inventario/secciones/transferibles")
    assert resp.status_code == 200
    datos = resp.json()
    tipos = [s["tipo"] for s in datos]
    assert tipos == ["GENERAL", "FO"] or set(tipos) == {"GENERAL", "FO"}
    assert ALMACEN_PAQUETE not in {s["almacen_id"] for s in datos}
    assert ALMACEN_EN_USO not in {s["almacen_id"] for s in datos}
    # La tabla tampoco conserva tipos legacy (ck_secciones_tipo).
    legacy = await session.execute(
        text("SELECT count(*) FROM secciones WHERE tipo NOT IN ('GENERAL','FO')")
    )
    assert legacy.scalar_one() == 0
    fo_seccion = next(s for s in datos if s["tipo"] == "FO")
    assert fo_seccion["nombre"] == "Inventario FO"
    assert fo_seccion["almacen_id"] == fo["almacen_id"]
    assert fo_seccion["transferible"] is True


async def test_RF_4_origen_purgado_responde_422_sin_efectos(
    client: AsyncClient, session
) -> None:
    """RF-4/E10: un borrador TEAMS con origen_almacen_id = 2 (antes
    FO_PAQUETE) responde 422 «Sección origen inexistente» y no persiste
    nada."""
    m = await crear_material(client, descripcion="FO origen purgado")
    equipo = await crear_equipo(client, nombre="Unidad purgada")
    antes = (
        await session.execute(text("SELECT count(*) FROM movimientos_cabecera"))
    ).scalar_one()

    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": ALMACEN_PAQUETE,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": m["id_lista"], "cantidad": 1}],
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Sección origen inexistente" in resp.text

    despues = (
        await session.execute(text("SELECT count(*) FROM movimientos_cabecera"))
    ).scalar_one()
    assert despues == antes


async def test_RF_4_destino_devol_purgado_y_origen_id3_responden_422(
    client: AsyncClient, session
) -> None:
    """RF-4/E10: el id 3 (antes FO_EN_USO) como origen TEAMS y el id 2 como
    destino DEVOL responden 422 «Sección … inexistente», sin efectos."""
    m = await crear_material(client, descripcion="FO ids purgados")
    equipo = await crear_equipo(client, nombre="Unidad ids purgados")
    antes = (
        await session.execute(text("SELECT count(*) FROM movimientos_cabecera"))
    ).scalar_one()

    r1 = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "TEAMS",
            "origen_almacen_id": ALMACEN_EN_USO,
            "destino_equipo_id": equipo["equipo_id"],
            "detalle": [{"material_id": m["id_lista"], "cantidad": 1}],
        },
    )
    assert r1.status_code == 422, r1.text
    assert "Sección origen inexistente" in r1.text

    r2 = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": equipo["equipo_id"],
            "destino_almacen_id": ALMACEN_PAQUETE,
            "detalle": [{"material_id": m["id_lista"], "cantidad": 1}],
        },
    )
    assert r2.status_code == 422, r2.text
    assert "Sección destino inexistente" in r2.text

    despues = (
        await session.execute(text("SELECT count(*) FROM movimientos_cabecera"))
    ).scalar_one()
    assert despues == antes
