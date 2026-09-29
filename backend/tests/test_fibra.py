"""Fibra Óptica — inventarios independientes PAQUETE / EN_USO
(REQ-DOMAIN-003/004/005/006, REQ-API-001).

Cubre el contrato del router /api/v1/fibra: carga inicial idempotente,
ajuste auditado con motivo obligatorio, esquema estándar gobernado por U.M.
y cero fantasmas de materiales inactivos.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    crear_material,
    fibra_ajuste,
    fibra_carga_inicial,
)

MODULO_PAQUETE = "PAQUETE"
MODULO_EN_USO = "EN_USO"


async def _stock_fibra(
    client: AsyncClient, modulo: str
) -> dict[int, dict]:
    """Mapa {material_id: fila} del inventario FO vía GET /api/v1/fibra/{modulo}."""
    resp = await client.get(f"/api/v1/fibra/{modulo}")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f for f in resp.json()}


async def _material_fo(client: AsyncClient, *, descripcion: str, u_m: str) -> dict:
    return await crear_material(client, descripcion=descripcion, u_m=u_m)


@pytest.mark.critical
async def test_carga_inicial_fibra_ok_y_lectura_esquema_estandar(
    client: AsyncClient, session
) -> None:
    """REQ-DOMAIN-003/004/005: carga inicial OK en PAQUETE y lectura con el
    esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO,
    ALERTA STOCK), gobernado por la U.M. del catálogo maestro."""
    material = await _material_fo(
        client, descripcion="Cable 12F", u_m="CARRETE (1 KM)"
    )
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=50,
        motivo="Alta inicial",
    )

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    fila = filas[material["id_lista"]]
    assert fila["modulo"] == MODULO_PAQUETE
    assert fila["material_id"] == material["id_lista"]
    assert fila["descripcion"] == "Cable 12F"
    assert fila["u_m"] == "CARRETE (1 KM)"
    assert fila["stock_actual"] == 50
    assert fila["stock_minimo"] is None
    assert fila["alerta_stock"] is False

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "STOCK_INICIAL_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["modulo"] == MODULO_PAQUETE
    assert detalles["motivo"] == "Alta inicial"
    assert evento.cantidad == 50


async def test_carga_inicial_fibra_duplicada_400(client: AsyncClient) -> None:
    material = await _material_fo(client, descripcion="Cable Dup", u_m="METRO (M)")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )

    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={
            "modulo": MODULO_PAQUETE,
            "material_id": material["id_lista"],
            "cantidad": 20,
        },
    )
    assert resp.status_code == 400
    assert "ya posee un registro de inventario activo" in resp.json()["error"][
        "message"
    ]
    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 10


async def test_carga_inicial_fibra_cantidad_negativa_422(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable Neg", u_m="PZ")
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={
            "modulo": MODULO_PAQUETE,
            "material_id": material["id_lista"],
            "cantidad": -5,
        },
    )
    assert resp.status_code == 422


async def test_carga_inicial_fibra_modulo_invalido_422(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable Mod", u_m="PZ")
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={
            "modulo": "ALMACEN",
            "material_id": material["id_lista"],
            "cantidad": 5,
        },
    )
    assert resp.status_code == 422


@pytest.mark.critical
async def test_ajuste_fibra_ok_con_motivo_y_diferencial_auditado(
    client: AsyncClient, session
) -> None:
    """REQ-DOMAIN-003: ajuste administrativo OK con motivo obligatorio;
    el evento AJUSTE_INVENTARIO_FO registra modulo, diferencial y motivo."""
    material = await _material_fo(
        client, descripcion="Cable Ajuste", u_m="CARRETE (5 KM)"
    )
    await fibra_carga_inicial(
        client,
        modulo=MODULO_EN_USO,
        material_id=material["id_lista"],
        cantidad=100,
    )

    await fibra_ajuste(
        client,
        modulo=MODULO_EN_USO,
        material_id=material["id_lista"],
        nuevo_stock=60,
        motivo="Conteo físico FO",
    )

    filas = await _stock_fibra(client, MODULO_EN_USO)
    assert filas[material["id_lista"]]["stock_actual"] == 60

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["modulo"] == MODULO_EN_USO
    assert detalles["stock_anterior"] == 100
    assert detalles["stock_nuevo"] == 60
    assert detalles["diferencial"] == -40
    assert detalles["motivo"] == "Conteo físico FO"


async def test_ajuste_fibra_sin_motivo_422(client: AsyncClient) -> None:
    material = await _material_fo(client, descripcion="Cable Mot", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    for payload in (
        {"modulo": MODULO_PAQUETE, "material_id": material["id_lista"],
         "nuevo_stock": 5, "motivo": ""},
        {"modulo": MODULO_PAQUETE, "material_id": material["id_lista"],
         "nuevo_stock": 5},
    ):
        resp = await client.post("/api/v1/fibra/ajuste", json=payload)
        assert resp.status_code == 422


async def test_ajuste_fibra_nuevo_stock_negativo_422(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable Neg2", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=10,
    )
    resp = await client.post(
        "/api/v1/fibra/ajuste",
        json={
            "modulo": MODULO_PAQUETE,
            "material_id": material["id_lista"],
            "nuevo_stock": -1,
            "motivo": "X",
        },
    )
    assert resp.status_code == 422


async def test_ajuste_fibra_sin_registro_previo_404(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable SinReg", u_m="PZ")
    resp = await client.post(
        "/api/v1/fibra/ajuste",
        json={
            "modulo": MODULO_PAQUETE,
            "material_id": material["id_lista"],
            "nuevo_stock": 10,
            "motivo": "X",
        },
    )
    assert resp.status_code == 404
    assert "No se encuentra registro de inventario" in resp.json()["error"][
        "message"
    ]


async def test_lectura_fibra_modulo_invalido_422(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/fibra/ALMACEN")
    assert resp.status_code == 422


async def test_material_soft_deleted_omitido_de_lectura_fibra(
    client: AsyncClient,
) -> None:
    """REQ-API-001: un material soft-deleteado desaparece de la lectura del
    inventario FO aunque conserve fila física con stock."""
    material = await _material_fo(client, descripcion="Cable Ghost", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=30,
    )
    assert material["id_lista"] in await _stock_fibra(client, MODULO_PAQUETE)

    resp = await client.delete(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 204

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert material["id_lista"] not in filas


async def test_modulos_independientes_sin_cruce(client: AsyncClient) -> None:
    """REQ-DOMAIN-003: PAQUETE y EN_USO son raíces independientes; el stock
    de un módulo no aparece en el otro."""
    m1 = await _material_fo(client, descripcion="Fibra Paquete", u_m="PZ")
    m2 = await _material_fo(client, descripcion="Fibra Uso", u_m="PZ")
    await fibra_carga_inicial(
        client, modulo=MODULO_PAQUETE, material_id=m1["id_lista"], cantidad=10
    )
    await fibra_carga_inicial(
        client, modulo=MODULO_EN_USO, material_id=m2["id_lista"], cantidad=7
    )

    paquete = await _stock_fibra(client, MODULO_PAQUETE)
    en_uso = await _stock_fibra(client, MODULO_EN_USO)
    assert m1["id_lista"] in paquete and m1["id_lista"] not in en_uso
    assert m2["id_lista"] in en_uso and m2["id_lista"] not in paquete


# ═══════════════════════════════════════════════════════════════════════════
# CRUD FO por módulo — PATCH/DELETE /fibra/{modulo}/materiales/{material_id}
# (paquete 2026-09-29-fo-crud-management; REQ-CATFO-001/002,
# REQ-STOCK-001/002/003, REQ-DEL-001/002/003/004)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.critical
async def test_REQ_CATFO_001_patch_catalogo_edita_sin_tocar_stock_y_sin_ajuste(
    client: AsyncClient, session
) -> None:
    """REQ-CATFO-001: PATCH edita los campos de catálogo (descripción, código,
    U.M., stock mínimo) SIN tocar el stock registrado en `inventario_fibra`.
    El trigger audita MATERIAL_MODIFICADO con valores anteriores/nuevos y NO
    se genera ningún evento AJUSTE_INVENTARIO_FO."""
    material = await _material_fo(client, descripcion="Cable CatFO", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=40,
    )

    resp = await client.patch(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
        json={
            "descripcion": "Cable CatFO editado",
            "codigo": "SKU-FO-1",
            "u_m": "METRO (M)",
            "stock_minimo": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["modulo"] == MODULO_PAQUETE
    assert body["material_id"] == material["id_lista"]
    assert body["descripcion"] == "Cable CatFO editado"
    assert body["codigo"] == "SKU-FO-1"
    assert body["u_m"] == "METRO (M)"
    assert body["stock_minimo"] == 10
    # Stock intacto: la edición de catálogo jamás toca inventario_fibra.
    assert body["stock_actual"] == 40
    assert body["alerta_stock"] is False

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 40

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MATERIAL_MODIFICADO",
                AuditoriaEvento.material_id == material["id_lista"],
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    anteriores = detalles["valores_anteriores"]
    nuevos = detalles["valores_nuevos"]
    assert anteriores["descripcion"] == "Cable CatFO"
    assert anteriores["codigo"] is None
    assert nuevos["descripcion"] == "Cable CatFO editado"
    assert nuevos["codigo"] == "SKU-FO-1"
    assert nuevos["u_m"] == "METRO (M)"
    assert nuevos["stock_minimo"] == 10

    # Cero ajustes de inventario: solo la edición de catálogo fue auditada.
    ajustes = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert ajustes == []


async def test_REQ_STOCK_001_patch_stock_actual_sin_motivo_422_sin_cambios(
    client: AsyncClient, session
) -> None:
    """REQ-STOCK-001: cambiar `stock_actual` SIN motivo (ausente o en blanco)
    es rechazado por el validator del schema con 422 sin aplicar cambios en
    el catálogo ni en el inventario. El stock negativo también lo rechaza el
    validator (ge=0) antes de tocar la base."""
    material = await _material_fo(client, descripcion="Cable StockMot", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=25,
    )

    for payload in (
        {"stock_actual": 10},
        {"descripcion": "Editado que revierte", "stock_actual": 10, "motivo": "   "},
        {"stock_actual": -5, "motivo": "Negativo rechazado por el schema"},
    ):
        resp = await client.patch(
            f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
            json=payload,
        )
        assert resp.status_code == 422, resp.text

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 25
    assert filas[material["id_lista"]]["descripcion"] == "Cable StockMot"

    ajustes = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert ajustes == []


@pytest.mark.critical
async def test_REQ_STOCK_002_patch_stock_actual_con_motivo_200_diferencial_auditado(
    client: AsyncClient, session
) -> None:
    """REQ-STOCK-002: PATCH con `stock_actual` + `motivo` actualiza
    `inventario_fibra` vía `fn_ajustar_stock_fibra` (diferencial calculado en
    PostgreSQL) y audita AJUSTE_INVENTARIO_FO con modulo, stock_anterior,
    stock_nuevo, diferencial y motivo correctos."""
    material = await _material_fo(
        client, descripcion="Cable Dif", u_m="CARRETE (1 KM)"
    )
    await fibra_carga_inicial(
        client,
        modulo=MODULO_EN_USO,
        material_id=material["id_lista"],
        cantidad=80,
    )

    resp = await client.patch(
        f"/api/v1/fibra/{MODULO_EN_USO}/materiales/{material['id_lista']}",
        json={"stock_actual": 55, "motivo": "Conteo físico FO"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_actual"] == 55
    # El catálogo permanece intacto en un payload de solo-ajuste de stock.
    assert resp.json()["descripcion"] == "Cable Dif"

    filas = await _stock_fibra(client, MODULO_EN_USO)
    assert filas[material["id_lista"]]["stock_actual"] == 55

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["modulo"] == MODULO_EN_USO
    assert detalles["stock_anterior"] == 80
    assert detalles["stock_nuevo"] == 55
    assert detalles["diferencial"] == -25
    assert detalles["motivo"] == "Conteo físico FO"


async def test_REQ_STOCK_003_patch_atomico_um_invalida_revierte_catalogo_y_stock(
    client: AsyncClient, session
) -> None:
    """REQ-STOCK-003 (atomicidad): un PATCH con U.M. inexistente (422
    determinístico de REQ-CATFO-002) revierte TODA la transacción — ni la
    descripción ni el stock solicitados en el MISMO payload llegan a la base."""
    material = await _material_fo(client, descripcion="Cable Atom", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=30,
    )

    resp = await client.patch(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
        json={
            "descripcion": "Descripción que debe revertir",
            "stock_actual": 12,
            "motivo": "Ajuste que debe revertir",
            "u_m": "UNIDAD INEXISTENTE",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Unidad de medida no válida" in resp.json()["error"]["message"]

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    fila = filas[material["id_lista"]]
    assert fila["descripcion"] == "Cable Atom"
    assert fila["stock_actual"] == 30

    # La transacción falló completa: cero eventos de ajuste en el ledger.
    ajustes = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert ajustes == []


async def test_REQ_DEL_004_delete_stock_positivo_sin_motivo_422_fila_intacta(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-004: eliminar una fila con stock > 0 SIN motivo (ausente o en
    blanco) es rechazado con 422 por la validación autoritativa de PostgreSQL
    y la fila sigue existiendo sin eventos de eliminación."""
    material = await _material_fo(client, descripcion="Cable DelMot", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=15,
    )

    for params in (None, {"motivo": "   "}):
        resp = await client.delete(
            f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
            params=params,
        )
        assert resp.status_code == 422, resp.text
        assert "motivo" in resp.json()["error"]["message"].lower()

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert filas[material["id_lista"]]["stock_actual"] == 15

    eliminaciones = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "ELIMINACION_FO"
            )
        )
    ).scalars().all()
    assert eliminaciones == []


@pytest.mark.critical
async def test_REQ_DEL_001_003_delete_stock_positivo_con_motivo_204_aislado_y_auditado(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-001/003: DELETE con motivo elimina SOLO la fila física del
    módulo indicado — el material sigue vivo en el otro módulo FO y en el
    catálogo — y audita ELIMINACION_FO con snapshot jsonb completo
    (modulo, material_id, stock_eliminado, motivo) y cantidad == stock
    eliminado."""
    material = await _material_fo(client, descripcion="Cable DelOK", u_m="PZ")
    mid = material["id_lista"]
    await fibra_carga_inicial(
        client, modulo=MODULO_PAQUETE, material_id=mid, cantidad=15
    )
    await fibra_carga_inicial(
        client, modulo=MODULO_EN_USO, material_id=mid, cantidad=7
    )

    resp = await client.delete(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{mid}",
        params={"motivo": "Baja administrativa FO"},
    )
    assert resp.status_code == 204

    # La fila desaparece SOLO de PAQUETE; EN_USO conserva su stock propio.
    paquete = await _stock_fibra(client, MODULO_PAQUETE)
    assert mid not in paquete
    en_uso = await _stock_fibra(client, MODULO_EN_USO)
    assert en_uso[mid]["stock_actual"] == 7

    # El catálogo maestro permanece íntegro (REQ-DEL-003): detalle y listado.
    resp = await client.get(f"/api/v1/catalogo/{mid}")
    assert resp.status_code == 200
    assert resp.json()["descripcion"] == "Cable DelOK"
    assert resp.json()["is_active"] is True
    resp = await client.get("/api/v1/catalogo")
    ids_catalogo = {m["id_lista"] for m in resp.json()["materiales"]}
    assert mid in ids_catalogo

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "ELIMINACION_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert detalles["modulo"] == MODULO_PAQUETE
    assert detalles["material_id"] == mid
    assert detalles["stock_eliminado"] == 15
    assert detalles["motivo"] == "Baja administrativa FO"
    assert evento.material_id == mid
    assert evento.cantidad == detalles["stock_eliminado"]


async def test_REQ_DEL_004_delete_stock_cero_sin_motivo_204_opcional(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-004: con stock_actual = 0 el motivo es opcional (204) y el
    evento ELIMINACION_FO registra el snapshot con stock_eliminado = 0."""
    material = await _material_fo(client, descripcion="Cable Cero", u_m="PZ")
    await fibra_carga_inicial(
        client,
        modulo=MODULO_PAQUETE,
        material_id=material["id_lista"],
        cantidad=0,
    )

    resp = await client.delete(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}"
    )
    assert resp.status_code == 204

    filas = await _stock_fibra(client, MODULO_PAQUETE)
    assert material["id_lista"] not in filas

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "ELIMINACION_FO"
            )
        )
    ).scalars().one()
    assert evento.cantidad == 0
    assert (evento.detalles or {})["stock_eliminado"] == 0
    assert (evento.detalles or {})["modulo"] == MODULO_PAQUETE


async def test_REQ_DEL_002_delete_fila_inexistente_404(
    client: AsyncClient,
) -> None:
    """REQ-DEL-002: eliminar una fila (modulo, material_id) inexistente en
    `inventario_fibra` clasifica 404 sin efectos colaterales."""
    material = await _material_fo(client, descripcion="Cable 404", u_m="PZ")

    resp = await client.delete(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}"
    )
    assert resp.status_code == 404
    assert "No se encuentra registro de inventario" in resp.json()["error"][
        "message"
    ]


async def test_REQ_CATFO_001_patch_fila_inexistente_404(
    client: AsyncClient,
) -> None:
    """REQ-CATFO-001: PATCH sobre una fila FO inexistente clasifica 404 con
    las coordenadas (modulo, material_id) sin alterar nada."""
    material = await _material_fo(client, descripcion="Cable 404 Patch", u_m="PZ")

    resp = await client.patch(
        f"/api/v1/fibra/{MODULO_PAQUETE}/materiales/{material['id_lista']}",
        json={"descripcion": "Nueva descripción"},
    )
    assert resp.status_code == 404
    assert "Material no encontrado en el módulo FO" in resp.json()["error"][
        "message"
    ]
