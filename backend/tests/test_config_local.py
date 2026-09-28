"""Configuración operativa LOCAL por equipo — REQ-TEAM-001..004.

PATCH /api/v1/equipos/{equipo_id}/inventario/{material_id} sobre
`equipo_material_config` (0014): stock mínimo, categoría y U.M. propios del
equipo SIN tocar el catálogo maestro ni el stock, con auditoría inmutable
CONFIG_EQUIPO_MODIFICADA, valores efectivos por COALESCE en la lectura del
inventario y aislamiento por integrante (SEC-003).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    borrador_teams,
    carga_inicial,
    crear_equipo,
    crear_material,
    inventario_equipo,
    procesar,
)


async def _setup(
    client: AsyncClient, *, stock_equipo: int = 40
) -> tuple[dict, dict, int, int]:
    """Material con categoría A + categoría B incidental + equipo con stock."""
    cat_a = await crear_material(
        client, descripcion="Portador Cat A", nueva_categoria="Cat Local A"
    )
    cat_b = await crear_material(
        client, descripcion="Portador Cat B", nueva_categoria="Cat Local B"
    )
    material = await crear_material(
        client,
        descripcion="Config Local",
        codigo="CFG-001",
        u_m="PZ",
        stock_minimo=10,
        categoria_id=cat_a["categoria_id"],
    )
    equipo = await crear_equipo(client, nombre="Equipo Config")
    await carga_inicial(
        client, material_id=material["id_lista"], cantidad=100
    )
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=material["id_lista"],
        cantidad=stock_equipo,
    )
    await procesar(client, b["id"])
    return material, equipo, cat_a["categoria_id"], cat_b["categoria_id"]


async def _patch_config(
    client: AsyncClient, equipo_id: int, material_id: int, **campos
):
    return await client.patch(
        f"/api/v1/equipos/{equipo_id}/inventario/{material_id}",
        json=campos,
    )


async def _um_id(client: AsyncClient, nombre: str) -> int:
    resp = await client.get("/api/v1/catalogo/um")
    assert resp.status_code == 200, resp.text
    return next(u["id"] for u in resp.json() if u["nombre"] == nombre)


@pytest.mark.critical
async def test_REQ_TEAM_003_patch_config_local_200_persistido(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-003: PATCH fija stock mínimo, categoría y U.M. locales del
    equipo; los campos se persisten y las ediciones posteriores conservan
    los valores no enviados (patch semántico)."""
    material, equipo, _, cat_b = await _setup(client)
    um_metro = await _um_id(client, "METRO (M)")

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=5,
        categoria_local_id=cat_b,
        um_local_id=um_metro,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_minimo_local"] == 5
    assert body["categoria_local_id"] == cat_b
    assert body["um_local_id"] == um_metro

    # Patch semántico: solo stock mínimo — categoría y U.M. se conservan.
    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=8,
    )
    assert resp.status_code == 200

    filas = await inventario_equipo(client, equipo["equipo_id"])
    fila = filas[material["id_lista"]]
    assert fila["stock_minimo_local"] == 8
    assert fila["categoria_local_id"] == cat_b
    assert fila["um_local_id"] == um_metro


async def test_REQ_TEAM_001_002_patch_campos_prohibidos_422(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-001, REQ-TEAM-002: el stock actual, el código y la descripción NO son
    editables por configuración local (extra='forbid' → 422)."""
    material, equipo, _, _ = await _setup(client)
    for campo in (
        {"stock_actual": 99},
        {"codigo": "ZZZ-999"},
        {"descripcion": "Descripción alterada"},
    ):
        resp = await _patch_config(
            client, equipo["equipo_id"], material["id_lista"], **campo
        )
        assert resp.status_code == 422


async def test_REQ_TEAM_003_patch_vacio_422(client: AsyncClient) -> None:
    """REQ-TEAM-003: el PATCH exige al menos un campo a actualizar (422)."""
    material, equipo, _, _ = await _setup(client)
    resp = await client.patch(
        f"/api/v1/equipos/{equipo['equipo_id']}/inventario/"
        f"{material['id_lista']}",
        json={},
    )
    assert resp.status_code == 422


async def test_REQ_TEAM_003_patch_stock_minimo_local_negativo_422(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-003: stock mínimo local negativo viola el esquema (ge=0)
    y el CHECK de la tabla → 422."""
    material, equipo, _, _ = await _setup(client)
    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=-1,
    )
    assert resp.status_code == 422


async def test_REQ_TEAM_003_patch_categoria_local_soft_deleted_404(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-TEAM-003: la categoría local debe estar activa — una categoría
    suprimida lógicamente clasifica 404."""
    material, equipo, _, cat_b = await _setup(client)
    resp = await client_admin.delete(f"/api/v1/catalogo/categorias/{cat_b}")
    assert resp.status_code == 204

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        categoria_local_id=cat_b,
    )
    assert resp.status_code == 404


async def test_REQ_TEAM_003_patch_um_local_inactiva_404(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-TEAM-003: la U.M. local debe estar activa — una U.M. suprimida
    lógicamente clasifica 404."""
    material, equipo, _, _ = await _setup(client)
    um_rollo = await _um_id(client, "ROLLO")
    resp = await client_admin.delete(f"/api/v1/catalogo/um/{um_rollo}")
    assert resp.status_code == 204

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        um_local_id=um_rollo,
    )
    assert resp.status_code == 404


@pytest.mark.critical
async def test_REQ_TEAM_004_patch_local_no_afecta_maestro(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-004: los parámetros locales del equipo jamás alteran el
    catálogo maestro — categoría, U.M. y stock mínimo originales intactos."""
    material, equipo, cat_a, cat_b = await _setup(client)
    um_metro = await _um_id(client, "METRO (M)")

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=45,
        categoria_local_id=cat_b,
        um_local_id=um_metro,
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 200
    maestro = resp.json()
    assert maestro["categoria_id"] == cat_a
    assert maestro["categoria"] == "Cat Local A"
    assert maestro["u_m"] == "PZ"
    assert maestro["stock_minimo"] == 10


async def test_REQ_TEAM_003_efectivos_locales_y_alerta_stock(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-003: con configuración local, los valores EFECTIVOS del
    inventario provienen de la configuración (COALESCE local → maestro) y
    la alerta de stock se calcula contra el mínimo local."""
    material, equipo, _, cat_b = await _setup(client, stock_equipo=40)
    um_metro = await _um_id(client, "METRO (M)")

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=45,
        categoria_local_id=cat_b,
        um_local_id=um_metro,
    )
    assert resp.status_code == 200

    fila = (await inventario_equipo(client, equipo["equipo_id"]))[
        material["id_lista"]
    ]
    assert fila["stock_minimo_efectivo"] == 45
    assert fila["categoria_efectiva"] == "Cat Local B"
    assert fila["um_efectivo"] == "METRO (M)"
    assert fila["alerta_stock"] is True


async def test_REQ_TEAM_003_efectivos_fallback_maestro(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-003: sin configuración local, los efectivos replican el
    maestro (mínimo, categoría y U.M. del catálogo) y la alerta se calcula
    contra el stock mínimo maestro."""
    material, equipo, _, _ = await _setup(client, stock_equipo=40)

    fila = (await inventario_equipo(client, equipo["equipo_id"]))[
        material["id_lista"]
    ]
    assert fila["stock_minimo_local"] is None
    assert fila["categoria_local_id"] is None
    assert fila["um_local_id"] is None
    assert fila["stock_minimo_efectivo"] == 10
    assert fila["categoria_efectiva"] == "Cat Local A"
    assert fila["um_efectivo"] == "PZ"
    assert fila["alerta_stock"] is False


async def test_REQ_TEAM_003_config_material_sin_recibir_200_y_lectura_vacia(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-003 + modelo sparse preservado: configurar un material que
    el equipo jamás ha recibido funciona (200) y la lectura del inventario
    NO fabrica filas fantasma ([])."""
    material, equipo, _, _ = await _setup(client)
    huesped = await crear_material(client, descripcion="Nunca recibido")

    resp = await _patch_config(
        client,
        equipo["equipo_id"],
        huesped["id_lista"],
        stock_minimo_local=3,
    )
    assert resp.status_code == 200

    filas = await inventario_equipo(client, equipo["equipo_id"])
    assert huesped["id_lista"] not in filas
    assert material["id_lista"] in filas


async def test_REQ_TEAM_003_auditoria_config_equipo_modificada(
    client: AsyncClient, session
) -> None:
    """REQ-TEAM-003 + Constitución 6.2: cada mutación de configuración
    emite CONFIG_EQUIPO_MODIFICADA con el actor del header; la segunda
    edición conserva los valores anteriores en el detalle."""
    material, equipo, _, cat_b = await _setup(client)
    await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=7,
    )
    await _patch_config(
        client,
        equipo["equipo_id"],
        material["id_lista"],
        stock_minimo_local=9,
        categoria_local_id=cat_b,
    )

    eventos = (
        await session.execute(
            select(AuditoriaEvento)
            .where(AuditoriaEvento.tipo_accion == "CONFIG_EQUIPO_MODIFICADA")
            .order_by(AuditoriaEvento.id)
        )
    ).scalars().all()
    assert len(eventos) == 2
    for evento in eventos:
        assert evento.usuario == "qa"
        assert (evento.detalles or {})["equipo_id"] == equipo["equipo_id"]

    insertado = eventos[0].detalles or {}
    assert insertado["stock_minimo_local"] == 7
    assert insertado["valores_anteriores"] is None

    actualizado = eventos[1].detalles or {}
    assert actualizado["stock_minimo_local"] == 9
    assert actualizado["categoria_local_id"] == cat_b
    assert actualizado["valores_anteriores"]["stock_minimo_local"] == 7
    assert actualizado["valores_anteriores"]["categoria_local_id"] is None


async def test_SEC_003_aislamiento_no_integrante_403_y_admin_pase(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """SEC-003: lectura del inventario y PATCH de configuración exigen
    integrante del equipo (403 para ajenos); el administrador recibe pase
    transversal."""
    material, _, _, _ = await _setup(client)
    ajeno = await crear_equipo(
        client, nombre="Equipo ajeno config", integrantes=["otro"]
    )

    resp = await client.get(
        f"/api/v1/equipos/{ajeno['equipo_id']}/inventario"
    )
    assert resp.status_code == 403

    resp = await _patch_config(
        client,
        ajeno["equipo_id"],
        material["id_lista"],
        stock_minimo_local=5,
    )
    assert resp.status_code == 403

    resp = await client_admin.get(
        f"/api/v1/equipos/{ajeno['equipo_id']}/inventario"
    )
    assert resp.status_code == 200

    resp = await _patch_config(
        client_admin,
        ajeno["equipo_id"],
        material["id_lista"],
        stock_minimo_local=5,
    )
    assert resp.status_code == 200


async def test_REQ_TEAM_001_codigo_descripcion_desde_maestro_inmutables(
    client: AsyncClient,
) -> None:
    """REQ-TEAM-001: el código y la descripción expuestos en el inventario
    del equipo provienen SIEMPRE del catálogo maestro (trazabilidad) y el
    PATCH no puede reescribirlos (422)."""
    material, equipo, _, _ = await _setup(client)

    fila = (await inventario_equipo(client, equipo["equipo_id"]))[
        material["id_lista"]
    ]
    assert fila["codigo"] == "CFG-001"
    assert fila["descripcion"] == "Config Local"

    for campo in ({"codigo": "HACK-001"}, {"descripcion": "Alterado"}):
        resp = await _patch_config(
            client, equipo["equipo_id"], material["id_lista"], **campo
        )
        assert resp.status_code == 422

    fila = (await inventario_equipo(client, equipo["equipo_id"]))[
        material["id_lista"]
    ]
    assert fila["codigo"] == "CFG-001"
    assert fila["descripcion"] == "Config Local"
