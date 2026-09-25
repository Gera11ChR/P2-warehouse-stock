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
