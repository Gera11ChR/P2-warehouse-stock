"""Fibra Óptica — Inventario FO unificado (RF-1, cambio
2026-10-fo-unificado-valor-unitario; migración 0027).

Cubre el contrato del router /api/v1/fibra SIN `modulo`: carga inicial
idempotente, ajuste auditado con motivo opcional (ergonomía
`justificacion_opcional`), esquema estándar gobernado por U.M., VALOR
UNITARIO por JOIN al catálogo maestro (RF-3), cero fantasmas de
materiales inactivos y PATCH/DELETE por material.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.errors import BusinessRuleError
from app.models import AuditoriaEvento
from app.services import transaccional
from tests.helpers.fabrica import (
    crear_material,
    fibra_ajuste,
    fibra_carga_inicial,
    inventario_fo,
)


async def _material_fo(client: AsyncClient, *, descripcion: str, u_m: str) -> dict:
    return await crear_material(client, descripcion=descripcion, u_m=u_m)


@pytest.mark.critical
async def test_carga_inicial_fibra_ok_y_lectura_esquema_estandar(
    client: AsyncClient, session
) -> None:
    """RF-1/RF-3: carga inicial OK en el Inventario FO unificado y lectura
    con el esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL,
    STOCK MÍNIMO, ALERTA STOCK, VALOR UNITARIO), gobernado por la U.M. del
    catálogo maestro. El evento STOCK_INICIAL_FO ya no registra `modulo`."""
    material = await _material_fo(
        client, descripcion="Cable 12F", u_m="CARRETE (1 KM)"
    )
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=50,
        motivo="Alta inicial",
    )

    filas = await inventario_fo(client)
    fila = filas[material["id_lista"]]
    assert "modulo" not in fila  # RF-1: el contrato vivo no expone modulo
    assert fila["material_id"] == material["id_lista"]
    assert fila["descripcion"] == "Cable 12F"
    assert fila["u_m"] == "CARRETE (1 KM)"
    assert fila["stock_actual"] == 50
    assert fila["stock_minimo"] is None
    assert fila["alerta_stock"] is False
    # RF-3: valor unitario por JOIN al catálogo (default 1.000, número JSON).
    assert fila["valor_unitario"] == 1.0
    assert isinstance(fila["valor_unitario"], float)

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "STOCK_INICIAL_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo" not in detalles
    assert detalles["motivo"] == "Alta inicial"
    assert evento.cantidad == 50


async def test_carga_inicial_fibra_duplicada_400(client: AsyncClient) -> None:
    material = await _material_fo(client, descripcion="Cable Dup", u_m="METRO (M)")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=10,
    )

    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={
            "material_id": material["id_lista"],
            "cantidad": 20,
        },
    )
    assert resp.status_code == 400
    assert "ya posee un registro de inventario activo" in resp.json()["error"][
        "message"
    ]
    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 10


async def test_carga_inicial_fibra_cantidad_negativa_422(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable Neg", u_m="PZ")
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={
            "material_id": material["id_lista"],
            "cantidad": -5,
        },
    )
    assert resp.status_code == 422


async def test_lectura_fibra_ruta_con_modulo_desaparece_404(
    client: AsyncClient,
) -> None:
    """RF-1: la ruta legada `GET /fibra/{modulo}` fue REEMPLAZADA por
    `GET /fibra`; la URL antigua ya no existe (404)."""
    resp = await client.get("/api/v1/fibra/PAQUETE")
    assert resp.status_code == 404


@pytest.mark.critical
async def test_ajuste_fibra_ok_con_motivo_y_diferencial_auditado(
    client: AsyncClient, session
) -> None:
    """RF-1: ajuste administrativo OK con motivo; el evento
    AJUSTE_INVENTARIO_FO registra stock_anterior, stock_nuevo, diferencial
    y motivo (sin `modulo`)."""
    material = await _material_fo(
        client, descripcion="Cable Ajuste", u_m="CARRETE (5 KM)"
    )
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=100,
    )

    await fibra_ajuste(
        client,
        material_id=material["id_lista"],
        nuevo_stock=60,
        motivo="Conteo físico FO",
    )

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 60

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo" not in detalles
    assert detalles["stock_anterior"] == 100
    assert detalles["stock_nuevo"] == 60
    assert detalles["diferencial"] == -40
    assert detalles["motivo"] == "Conteo físico FO"


async def test_ajuste_fibra_sin_motivo_200(
    client: AsyncClient, session
) -> None:
    """REQ-ERG-005: ajuste administrativo FO con motivo omitido o vacío se
    acepta (200) y audita AJUSTE_INVENTARIO_FO con el motivo tal como
    llega (NULL permitido)."""
    material = await _material_fo(client, descripcion="Cable Mot", u_m="PZ")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=10,
    )
    for payload in (
        {"material_id": material["id_lista"], "nuevo_stock": 5, "motivo": ""},
        {"material_id": material["id_lista"], "nuevo_stock": 5},
    ):
        resp = await client.post("/api/v1/fibra/ajuste", json=payload)
        assert resp.status_code == 200, resp.text

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 5

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert len(eventos) == 2
    assert [(e.detalles or {}).get("motivo") for e in eventos] == ["", None]


async def test_ajuste_fibra_nuevo_stock_negativo_422(
    client: AsyncClient,
) -> None:
    material = await _material_fo(client, descripcion="Cable Neg2", u_m="PZ")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=10,
    )
    resp = await client.post(
        "/api/v1/fibra/ajuste",
        json={
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
            "material_id": material["id_lista"],
            "nuevo_stock": 10,
            "motivo": "X",
        },
    )
    assert resp.status_code == 404
    assert "No se encuentra registro de inventario" in resp.json()["error"][
        "message"
    ]


async def test_material_soft_deleted_omitido_de_lectura_fibra(
    client: AsyncClient,
) -> None:
    """REQ-API-001: un material soft-deleteado desaparece de la lectura del
    Inventario FO aunque conserve fila física con stock."""
    material = await _material_fo(client, descripcion="Cable Ghost", u_m="PZ")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=30,
    )
    assert material["id_lista"] in await inventario_fo(client)

    resp = await client.delete(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 204

    filas = await inventario_fo(client)
    assert material["id_lista"] not in filas


async def test_rf_1_inventario_fo_unico_sin_subapartados(
    client: AsyncClient, session
) -> None:
    """RF-1: una única locación Inventario FO — dos materiales conviven en
    la MISMA tabla de materiales FO (sin módulos ni subapartados); una fila
    por material."""
    m1 = await _material_fo(client, descripcion="Fibra A", u_m="PZ")
    m2 = await _material_fo(client, descripcion="Fibra B", u_m="PZ")
    await fibra_carga_inicial(client, material_id=m1["id_lista"], cantidad=10)
    await fibra_carga_inicial(client, material_id=m2["id_lista"], cantidad=7)

    filas = await inventario_fo(client)
    assert filas[m1["id_lista"]]["stock_actual"] == 10
    assert filas[m2["id_lista"]]["stock_actual"] == 7
    assert len(filas) == 2

    # RF-1 (Unwanted): enviar `modulo` a una operación FO → 422 sin efectos.
    resp = await client.post(
        "/api/v1/fibra/carga-inicial",
        json={"modulo": "PAQUETE", "material_id": m1["id_lista"], "cantidad": 99},
    )
    assert resp.status_code == 422
    assert "modulo" in str(resp.json())
    filas = await inventario_fo(client)
    assert filas[m1["id_lista"]]["stock_actual"] == 10


# ═══════════════════════════════════════════════════════════════════════════
# CRUD FO por material — PATCH/DELETE /fibra/materiales/{material_id}
# (paquete 2026-09-29-fo-crud-management; REQ-CATFO-001/002,
# REQ-STOCK-001/002/003, REQ-DEL-001/002/003/004 — rutas sin modulo, RF-1)
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
        material_id=material["id_lista"],
        cantidad=40,
    )

    resp = await client.patch(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        json={
            "descripcion": "Cable CatFO editado",
            "codigo": "SKU-FO-1",
            "u_m": "METRO (M)",
            "stock_minimo": 10,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "modulo" not in body
    assert body["material_id"] == material["id_lista"]
    assert body["descripcion"] == "Cable CatFO editado"
    assert body["codigo"] == "SKU-FO-1"
    assert body["u_m"] == "METRO (M)"
    assert body["stock_minimo"] == 10
    assert body["valor_unitario"] == 1.0  # RF-3 (default, JOIN al catálogo)
    # Stock intacto: la edición de catálogo jamás toca inventario_fibra.
    assert body["stock_actual"] == 40
    assert body["alerta_stock"] is False

    filas = await inventario_fo(client)
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


async def test_REQ_ERG_004_patch_stock_actual_sin_motivo_200(
    client: AsyncClient, session
) -> None:
    """REQ-ERG-004: cambiar `stock_actual` SIN motivo (ausente, null o en
    blanco) se acepta (200): fn_ajustar_stock_fibra audita
    AJUSTE_INVENTARIO_FO con el motivo tal como llega. El stock negativo
    lo sigue rechazando el validator (ge=0) antes de tocar la base."""
    material = await _material_fo(client, descripcion="Cable StockMot", u_m="PZ")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=25,
    )

    for payload in (
        {"stock_actual": 10},
        {"descripcion": "Editado que revierte", "stock_actual": 10, "motivo": "   "},
        {"stock_actual": 12, "motivo": None},
    ):
        resp = await client.patch(
            f"/api/v1/fibra/materiales/{material['id_lista']}",
            json=payload,
        )
        assert resp.status_code == 200, resp.text

    resp = await client.patch(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        json={"stock_actual": -5, "motivo": "Negativo rechazado por el schema"},
    )
    assert resp.status_code == 422

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 12

    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().all()
    assert len(eventos) == 3
    assert [(e.detalles or {}).get("motivo") for e in eventos] == [
        None,
        "   ",
        None,
    ]


@pytest.mark.critical
async def test_REQ_STOCK_002_patch_stock_actual_con_motivo_200_diferencial_auditado(
    client: AsyncClient, session
) -> None:
    """REQ-STOCK-002: PATCH con `stock_actual` + `motivo` actualiza
    `inventario_fibra` vía `fn_ajustar_stock_fibra` (diferencial calculado en
    PostgreSQL) y audita AJUSTE_INVENTARIO_FO con stock_anterior,
    stock_nuevo, diferencial y motivo correctos (sin modulo)."""
    material = await _material_fo(
        client, descripcion="Cable Dif", u_m="CARRETE (1 KM)"
    )
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=80,
    )

    resp = await client.patch(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        json={"stock_actual": 55, "motivo": "Conteo físico FO"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stock_actual"] == 55
    # El catálogo permanece intacto en un payload de solo-ajuste de stock.
    assert resp.json()["descripcion"] == "Cable Dif"

    filas = await inventario_fo(client)
    assert filas[material["id_lista"]]["stock_actual"] == 55

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "AJUSTE_INVENTARIO_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo" not in detalles
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
        material_id=material["id_lista"],
        cantidad=30,
    )

    resp = await client.patch(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        json={
            "descripcion": "Descripción que debe revertir",
            "stock_actual": 12,
            "motivo": "Ajuste que debe revertir",
            "u_m": "UNIDAD INEXISTENTE",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "Unidad de medida no válida" in resp.json()["error"]["message"]

    filas = await inventario_fo(client)
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
        material_id=material["id_lista"],
        cantidad=15,
    )

    for params in (None, {"motivo": "   "}):
        resp = await client.delete(
            f"/api/v1/fibra/materiales/{material['id_lista']}",
            params=params,
        )
        assert resp.status_code == 422, resp.text
        assert "motivo" in resp.json()["error"]["message"].lower()

    filas = await inventario_fo(client)
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
    Inventario FO — el material sigue vivo en el catálogo y en el Inventario
    General — y audita ELIMINACION_FO con snapshot jsonb completo
    (material_id, stock_eliminado, motivo; sin modulo) y cantidad == stock
    eliminado."""
    from tests.helpers.fabrica import carga_inicial

    material = await _material_fo(client, descripcion="Cable DelOK", u_m="PZ")
    mid = material["id_lista"]
    await carga_inicial(client, material_id=mid, cantidad=25)
    await fibra_carga_inicial(client, material_id=mid, cantidad=15)

    resp = await client.delete(
        f"/api/v1/fibra/materiales/{mid}",
        params={"motivo": "Baja administrativa FO"},
    )
    assert resp.status_code == 204

    # La fila desaparece del Inventario FO; el Inventario General intacto.
    assert mid not in await inventario_fo(client)
    resp = await client.get("/api/v1/inventario/secciones/1")
    assert {f["material_id"]: f["stock_actual"] for f in resp.json()}[mid] == 25

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
    assert "modulo" not in detalles
    assert detalles["material_id"] == mid
    assert detalles["stock_eliminado"] == 15
    assert detalles["motivo"] == "Baja administrativa FO"
    assert evento.material_id == mid
    assert evento.cantidad == detalles["stock_eliminado"]


async def test_REQ_DEL_004_delete_stock_cero_sin_motivo_204_opcional(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-004: con stock_actual = 0 el motivo es opcional (204) y el
    evento ELIMINACION_FO registra el snapshot con stock_eliminado = 0
    (sin modulo)."""
    material = await _material_fo(client, descripcion="Cable Cero", u_m="PZ")
    await fibra_carga_inicial(
        client,
        material_id=material["id_lista"],
        cantidad=0,
    )

    resp = await client.delete(
        f"/api/v1/fibra/materiales/{material['id_lista']}"
    )
    assert resp.status_code == 204

    filas = await inventario_fo(client)
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
    assert "modulo" not in (evento.detalles or {})


async def test_REQ_DEL_002_delete_fila_inexistente_404(
    client: AsyncClient,
) -> None:
    """REQ-DEL-002: eliminar una fila inexistente en `inventario_fibra`
    clasifica 404 sin efectos colaterales."""
    material = await _material_fo(client, descripcion="Cable 404", u_m="PZ")

    resp = await client.delete(
        f"/api/v1/fibra/materiales/{material['id_lista']}"
    )
    assert resp.status_code == 404
    assert "No se encuentra registro de inventario" in resp.json()["error"][
        "message"
    ]


async def test_REQ_CATFO_001_patch_fila_inexistente_404(
    client: AsyncClient,
) -> None:
    """REQ-CATFO-001: PATCH sobre una fila FO inexistente clasifica 404 con
    las coordenadas (material_id) sin alterar nada."""
    material = await _material_fo(client, descripcion="Cable 404 Patch", u_m="PZ")

    resp = await client.patch(
        f"/api/v1/fibra/materiales/{material['id_lista']}",
        json={"descripcion": "Nueva descripción"},
    )
    assert resp.status_code == 404
    assert "Material no encontrado en Inventario FO" in resp.json()["error"][
        "message"
    ]


# ============================================================================
# Paquete 2026-09-29-fo-delete-fix (fo_report_1.md): cero HTTP 500 en DELETE FO
# ============================================================================


class _FakeDiag:
    message_primary = "mensaje de prueba del motor"


class _FakeOrig(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("error simulado")
        self.sqlstate = sqlstate
        self.diag = _FakeDiag()


def _fake_dbapi_error(sqlstate: str) -> DBAPIError:
    error = DBAPIError.instance("DELETE", {}, _FakeOrig(sqlstate), Exception)
    assert isinstance(error, DBAPIError)
    return error


async def test_REQ_DEL_FIX_002_mapeo_fk_23503_409_mensaje_claro() -> None:
    """REQ-DEL-FIX-002: una violación de FK (SQLSTATE 23503 — historial de
    movimientos/transferencias) se traduce a 409 con el mensaje de dominio
    claro y las coordenadas {material_id} — jamás un 500."""
    error = await transaccional.mapear_error_delete_fibra(
        _fake_dbapi_error("23503"), material_id=7
    )
    assert isinstance(error, BusinessRuleError)
    assert error.status_code == 409
    assert error.code == "FO_DELETE_INTEGRITY_CONFLICT"
    assert "movimientos o transferencias" in error.message
    assert error.coordinates == [{"material_id": 7}]


async def test_REQ_DEL_FIX_002_mapeo_fk_restrict_23001_409_mensaje_claro() -> None:
    """REQ-DEL-FIX-002: la violación RESTRICT que PostgreSQL reporta cuando
    un DELETE viola una FK ON DELETE RESTRICT desde dentro de una stored
    function (SQLSTATE 23001) recibe el mismo 409 de dominio."""
    error = await transaccional.mapear_error_delete_fibra(
        _fake_dbapi_error("23001"), material_id=7
    )
    assert isinstance(error, BusinessRuleError)
    assert error.status_code == 409
    assert error.code == "FO_DELETE_INTEGRITY_CONFLICT"
    assert "movimientos o transferencias" in error.message


async def test_REQ_DEL_FIX_002_mapeo_funcion_inexistente_42883_409() -> None:
    """REQ-DEL-FIX-002/007: la falta de `fn_eliminar_inventario_fibra` en el
    despliegue (SQLSTATE 42883 — causa raíz de fo_report_1.md) se traduce a
    409 controlado con mensaje operativo, sin propagar un 500."""
    error = await transaccional.mapear_error_delete_fibra(
        _fake_dbapi_error("42883"), material_id=33
    )
    assert isinstance(error, BusinessRuleError)
    assert error.status_code == 409
    assert error.code == "FO_DELETE_UNAVAILABLE"
    assert "no está disponible" in error.message
    assert error.coordinates == [{"material_id": 33}]


async def test_REQ_DEL_FIX_002_delete_con_historial_fk_409_fila_intacta(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-FIX-002/003: si PostgreSQL rechaza la eliminación por
    integridad referencial (material con historial que impide el borrado),
    el endpoint retorna HTTP 409 con el mensaje claro y coordenadas — la
    fila de `inventario_fibra` permanece intacta y cero eventos
    ELIMINACION_FO (jamás un 500)."""
    material = await _material_fo(client, descripcion="Cable FK", u_m="METRO (M)")
    mid = material["id_lista"]
    await fibra_carga_inicial(client, material_id=mid, cantidad=4300)

    # Guarda referencial transitoria que simula el historial de movimientos
    # asociados: bloquea el DELETE con SQLSTATE 23503 (ON DELETE RESTRICT).
    await session.execute(
        text(
            "CREATE TABLE fo_delete_guard ("
            " material_id INT NOT NULL,"
            " FOREIGN KEY (material_id)"
            "   REFERENCES inventario_fibra(material_id)"
            "   ON DELETE RESTRICT)"
        )
    )
    await session.commit()
    try:
        await session.execute(
            text(
                "INSERT INTO fo_delete_guard (material_id) "
                "VALUES (:material_id)"
            ),
            {"material_id": mid},
        )
        await session.commit()

        resp = await client.delete(
            f"/api/v1/fibra/materiales/{mid}",
            params={"motivo": "Intento de baja con historial"},
        )
        assert resp.status_code == 409, resp.text
        body = resp.json()["error"]
        assert body["code"] == "FO_DELETE_INTEGRITY_CONFLICT"
        assert "movimientos o transferencias" in body["message"]
        assert body["coordinates"] == [{"material_id": mid}]

        filas = await inventario_fo(client)
        assert filas[mid]["stock_actual"] == 4300

        eliminaciones = (
            await session.execute(
                select(AuditoriaEvento).where(
                    AuditoriaEvento.tipo_accion == "ELIMINACION_FO"
                )
            )
        ).scalars().all()
        assert eliminaciones == []
    finally:
        await session.execute(text("DROP TABLE IF EXISTS fo_delete_guard"))
        await session.commit()


async def test_REQ_DEL_FIX_001_path_y_query_params_resueltos(
    client: AsyncClient, session
) -> None:
    """REQ-DEL-FIX-001: el endpoint desempaqueta correctamente el path
    parameter (material_id) y el query parameter (motivo) y los entrega a
    PostgreSQL con los tipos exactos: DELETE con motivo → 204 y el snapshot
    ELIMINACION_FO conserva material_id y motivo (sin modulo)."""
    material = await _material_fo(
        client, descripcion="Cable Params", u_m="METRO (M)"
    )
    mid = material["id_lista"]
    await fibra_carga_inicial(client, material_id=mid, cantidad=20)

    resp = await client.delete(
        f"/api/v1/fibra/materiales/{mid}",
        params={"motivo": "Baja por prueba de parámetros"},
    )
    assert resp.status_code == 204, resp.text

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "ELIMINACION_FO"
            )
        )
    ).scalars().one()
    detalles = evento.detalles or {}
    assert "modulo" not in detalles
    assert detalles["material_id"] == mid
    assert detalles["motivo"] == "Baja por prueba de parámetros"
    assert evento.material_id == mid
