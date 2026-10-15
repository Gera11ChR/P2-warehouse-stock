"""Valor Unitario y Valor Total — RF-2/RF-3/RF-4/RF-7/RF-8 (backend).

Cambio 2026-10-fo-unificado-valor-unitario:

* RF-2: `valor_unitario` NUMERIC(12,3) no negativo (hasta 3 dp, máximo
  999 999 999.999); rechazos 422 sin modificar el material.
* RF-3: default 1.000 en todo el catálogo (nuevo y existente); edición con
  decimales visible en Inventario General, Inventario FO y por Unidad.
* RF-4: Valor Total = Σ(Stock Actual × Valor Unitario) de General activo +
  Inventario FO, calculado por PostgreSQL (`fn_valor_total_inventario`),
  expuesto en `GET /inventario/resumen-general` con moneda MXN.
* RF-7: evento MATERIAL_MODIFICADO con anterior/nuevo; sin evento si el
  valor no cambia.
* RF-8: RBAC por PRESENCIA del campo (403 no-admin, null = no-op), contrato
  estricto (extra → 422), números JSON, default-deny en resumen-general y
  errores 400/422 canónicos (nunca 500).
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import AuditoriaEvento
from tests.helpers.fabrica import (
    ajustar_stock,
    carga_inicial,
    crear_material,
    fibra_carga_inicial,
    inventario_equipo,
    inventario_fo,
    patch_material,
    stock_seccion,
)

RESUMEN = "/api/v1/inventario/resumen-general"


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


async def _eventos_valor(session, material_id: int) -> list[dict]:
    filas = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "MATERIAL_MODIFICADO",
                AuditoriaEvento.material_id == material_id,
            )
        )
    ).scalars().all()
    return [e.detalles or {} for e in filas]


# ── RF-2: atributo Valor Unitario ─────────────────────────────────────────


async def test_RF_002_persistencia_exacta_12_345(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-2: asignar 12.345 persiste y devuelve EXACTAMENTE 12.345 (número
    JSON, no string)."""
    m = await crear_material(client, descripcion="Cable valorado")
    resp = await patch_material(
        client_admin, m["id_lista"], valor_unitario=12.345
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["valor_unitario"] == 12.345
    assert isinstance(resp.json()["valor_unitario"], float)

    resp = await client.get(f"/api/v1/catalogo/{m['id_lista']}")
    assert resp.json()["valor_unitario"] == 12.345
    assert await _valor_db(session, m["id_lista"]) == Decimal("12.345")


@pytest.mark.parametrize("valor", [-1, 1.2345, 1000000000])
async def test_RF_002_valor_fuera_de_rango_422_sin_cambios(
    client: AsyncClient, client_admin: AsyncClient, session, valor: float
) -> None:
    """RF-2: negativo, más de 3 decimales o mayor que 999 999 999.999 →
    422 y el Valor Unitario previo NO cambia."""
    m = await crear_material(client, descripcion=f"Material rango {valor}")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=valor)
    assert resp.status_code == 422, resp.text
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")
    assert await _eventos_valor(session, m["id_lista"]) == []


async def test_RF_002_check_en_bd_defensa_en_profundidad(
    client: AsyncClient, session
) -> None:
    """RF-2/E4: el CHECK `ck_catalogo_valor_unitario_non_negative` de la BD
    rechaza un valor negativo aunque se intente saltar la API."""
    m = await crear_material(client, descripcion="Material CHECK")
    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET valor_unitario = -1 "
                "WHERE id_lista = :m"
            ),
            {"m": m["id_lista"]},
        )
        await session.commit()
    await session.rollback()
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")


# ── RF-3: valor inicial, visualización y edición ──────────────────────────


async def test_RF_003_default_1_000_en_todo_el_catalogo(
    client: AsyncClient, session
) -> None:
    """RF-3: todo material nuevo nace con Valor Unitario 1.000 (default de
    PostgreSQL) y la API lo devuelve como número JSON."""
    m1 = await crear_material(client, descripcion="Default A")
    m2 = await crear_material(client, descripcion="Default B", codigo="DEF-2")
    resp = await client.get("/api/v1/catalogo")
    valores = {
        f["id_lista"]: f["valor_unitario"]
        for f in resp.json()["materiales"]
    }
    assert valores[m1["id_lista"]] == 1.0
    assert valores[m2["id_lista"]] == 1.0
    assert await _valor_db(session, m1["id_lista"]) == Decimal("1.000")
    assert await _valor_db(session, m2["id_lista"]) == Decimal("1.000")


async def test_RF_003_edicion_decimal_visible_en_las_tres_tablas(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-3/C-2: al guardar 2.5 en Modificar Material, las tres tablas
    (Inventario General, Inventario FO, por Unidad) muestran 2.5 tras
    refrescar; en Unidad es solo lectura (viene del catálogo por JOIN)."""
    m = await crear_material(client, descripcion="Material 2.5")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=4)
    await fibra_carga_inicial(client, material_id=m["id_lista"], cantidad=10)
    # Unidad con stock (vía TEAMS) para que la fila aparezca en su inventario.
    from tests.helpers.fabrica import (
        borrador_teams,
        crear_equipo,
        procesar,
    )

    equipo = await crear_equipo(client, nombre="Unidad valor")
    b = await borrador_teams(
        client,
        almacen_id=1,
        equipo_id=equipo["equipo_id"],
        material_id=m["id_lista"],
        cantidad=1,
    )
    await procesar(client, b["id"])

    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=2.5)
    assert resp.status_code == 200, resp.text

    # Inventario General.
    filas = await stock_seccion(client, 1)
    assert filas[m["id_lista"]] == 3
    resp = await client.get("/api/v1/inventario/secciones/1")
    por_id = {f["material_id"]: f for f in resp.json()}
    assert por_id[m["id_lista"]]["valor_unitario"] == 2.5

    # Inventario FO.
    assert (await inventario_fo(client))[m["id_lista"]]["valor_unitario"] == 2.5

    # Por Unidad (solo lectura: JOIN al catálogo maestro).
    assert (
        (await inventario_equipo(client, equipo["equipo_id"]))[m["id_lista"]][
            "valor_unitario"
        ]
        == 2.5
    )


# ── RF-4: cálculo transaccional del Valor Total ───────────────────────────


async def test_RF_004_caso_exacto_spec_general_4x2_5_fo_10x1_25_22_500(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-4 (caso exacto de spec): A (General) stock 4 valor 2.5 y B (FO)
    stock 10 valor 1.25 → Valor Total = 22.500 con moneda MXN."""
    a = await crear_material(client, descripcion="Material A")
    b = await crear_material(client, descripcion="Material B")
    await carga_inicial(client, material_id=a["id_lista"], cantidad=4)
    await fibra_carga_inicial(client, material_id=b["id_lista"], cantidad=10)
    await patch_material(client_admin, a["id_lista"], valor_unitario=2.5)
    await patch_material(client_admin, b["id_lista"], valor_unitario=1.25)

    resp = await client.get(RESUMEN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"valor_total": 22.5, "moneda": "MXN"}
    assert isinstance(body["valor_total"], float)


async def test_RF_004_inventario_vacio_devuelve_0(
    client: AsyncClient,
) -> None:
    """RF-4: sin existencias el Valor Total es 0 (nunca null ni error)."""
    resp = await client.get(RESUMEN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["valor_total"] == 0
    assert resp.json()["moneda"] == "MXN"


async def test_RF_004_material_inactivo_excluido(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-4: un material con stock que pasa a inactivo deja de contar en el
    Valor Total."""
    m = await crear_material(client, descripcion="Material a desactivar")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=5)
    await patch_material(client_admin, m["id_lista"], valor_unitario=10)
    assert (await client.get(RESUMEN)).json()["valor_total"] == 50

    resp = await client.delete(f"/api/v1/catalogo/{m['id_lista']}")
    assert resp.status_code == 204
    assert (await client.get(RESUMEN)).json()["valor_total"] == 0


async def test_RF_004_refleja_cambios_de_stock_y_de_valor(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-4: el siguiente cálculo refleja el estado persistido — cambios de
    stock (ajuste) y de Valor Unitario actualizan el Valor Total (sin caché)."""
    m = await crear_material(client, descripcion="Material dinámico")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=10)
    await patch_material(client_admin, m["id_lista"], valor_unitario=2)
    assert (await client.get(RESUMEN)).json()["valor_total"] == 20

    await ajustar_stock(client, almacen_id=1, material_id=m["id_lista"], nuevo_stock=7)
    assert (await client.get(RESUMEN)).json()["valor_total"] == 14

    await patch_material(client_admin, m["id_lista"], valor_unitario=0.5)
    assert (await client.get(RESUMEN)).json()["valor_total"] == 3.5


async def test_RF_004_E9_valores_grandes_sin_truncar_ni_error(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-4/E9: stock grande × valor grande → el Valor Total no se trunca
    ni falla (aritmética NUMERIC exacta en PostgreSQL; el API devuelve un
    número JSON y la BD conserva el valor exacto)."""
    m = await crear_material(client, descripcion="Material gigante")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=999999999.999)
    resp = await patch_material(
        client_admin, m["id_lista"], valor_unitario=999999999.999
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(RESUMEN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["moneda"] == "MXN"
    assert isinstance(body["valor_total"], float)
    # Sin error y en el orden de magnitud esperado (1e18; la serialización
    # float pierde sub-unidades por encima de 9e12, documentado plan §2.1).
    esperado = float(Decimal("999999999.999") * Decimal("999999999.999"))
    assert abs(body["valor_total"] - esperado) <= esperado * 1e-9

    # La BD conserva la aritmética EXACTA (redondeo a 3 dp solo al final).
    exacto = (
        await session.execute(
            text("SELECT fn_valor_total_inventario()")
        )
    ).scalar_one()
    assert Decimal(exacto) == Decimal("999999999998000000.000")


# ── RF-7: auditoría del Valor Unitario ────────────────────────────────────


async def test_RF_007_evento_material_modificado_con_anterior_y_nuevo(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-7: al cambiar 1.000 → 2.500 se emite un evento MATERIAL_MODIFICADO
    inmutable con actor, material y valores anterior/nuevo."""
    m = await crear_material(client, descripcion="Material auditado")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=2.5)
    assert resp.status_code == 200, resp.text

    eventos = await _eventos_valor(session, m["id_lista"])
    assert len(eventos) == 1
    anteriores = eventos[0]["valores_anteriores"]
    nuevos = eventos[0]["valores_nuevos"]
    assert Decimal(str(anteriores["valor_unitario"])) == Decimal("1.000")
    assert Decimal(str(nuevos["valor_unitario"])) == Decimal("2.500")


async def test_RF_007_sin_evento_si_el_valor_no_cambia(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-7: una edición que NO modifica el Valor Unitario no emite evento
    de valor (comparación IS DISTINCT FROM: 1.0 == 1.000)."""
    m = await crear_material(client, descripcion="Material sin cambio")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=1.0)
    assert resp.status_code == 200, resp.text
    assert await _eventos_valor(session, m["id_lista"]) == []


# ── RF-8: contrato API y seguridad ────────────────────────────────────────


async def test_RF_008_campo_extra_422(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-8: una propiedad no declarada en el PATCH de material → 422."""
    m = await crear_material(client, descripcion="Material extra")
    resp = await patch_material(
        client_admin, m["id_lista"], descripcion="ok", tipo="GENERAL"
    )
    assert resp.status_code == 422


async def test_RF_008_no_admin_con_valor_403_y_valor_sin_cambios(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-8: un actor NO administrador que envía `valor_unitario` recibe 403
    (gate por PRESENCIA del campo, incl. null explícito) y el valor en BD no
    cambia — aunque el admin ya lo hubiera cambiado antes."""
    m = await crear_material(client, descripcion="Material RBAC")
    await patch_material(client_admin, m["id_lista"], valor_unitario=3.5)

    for payload in ({"valor_unitario": 2.5}, {"valor_unitario": None}):
        resp = await patch_material(client, m["id_lista"], **payload)
        assert resp.status_code == 403, resp.text
        assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    assert await _valor_db(session, m["id_lista"]) == Decimal("3.500")


async def test_RF_008_no_admin_en_patch_fibra_con_valor_403(
    client: AsyncClient, session
) -> None:
    """RF-8: el gate RBAC también aplica en PATCH /fibra/materiales/{id}
    (presencia de valor_unitario → 403 para no administradores)."""
    m = await crear_material(client, descripcion="Material FO RBAC")
    await fibra_carga_inicial(client, material_id=m["id_lista"], cantidad=5)
    resp = await client.patch(
        f"/api/v1/fibra/materiales/{m['id_lista']}",
        json={"valor_unitario": 2.5},
    )
    assert resp.status_code == 403
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")


async def test_RF_008_admin_con_null_noop_sin_evento(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """RF-8/E15: `valor_unitario: null` explícito con actor ADMIN es NO-OP:
    200, sin escritura, sin evento de auditoría y jamás un 500."""
    m = await crear_material(client, descripcion="Material null")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=None)
    assert resp.status_code == 200, resp.text
    assert resp.json()["valor_unitario"] == 1.0
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")
    assert await _eventos_valor(session, m["id_lista"]) == []


async def test_RF_008_resumen_general_default_deny(
    client_factory,
) -> None:
    """RF-8: GET /inventario/resumen-general exige actor autenticado —
    sin header → 422 y actor sin scope → 403 (default-deny)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    sin_header = AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )
    try:
        resp = await sin_header.get(RESUMEN)
        assert resp.status_code == 422
    finally:
        await sin_header.aclose()

    intruso = client_factory("intruso")
    try:
        resp = await intruso.get(RESUMEN)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTHORIZATION_FAILED"
    finally:
        await intruso.aclose()


@pytest.mark.parametrize(
    ("cuerpo", "input_sanitizado"),
    [
        ('{"valor_unitario": NaN}', "nan"),         # NaN
        ('{"valor_unitario": Infinity}', "inf"),    # Infinity
        ('{"valor_unitario": -Infinity}', "-inf"),  # -Infinity
    ],
)
async def test_RF_008_entradas_no_finitas_rechazadas_sin_cambios(
    client: AsyncClient,
    client_admin: AsyncClient,
    session,
    cuerpo: str,
    input_sanitizado: str,
) -> None:
    """RF-8 (plan §2.1): NaN/Infinity se rechazan con 422 canónico — la
    estructura por defecto `{"detail": [{loc, type, msg, input}]}` con el
    valor no finito sanitizado a cadena — sin cambios en BD ni ledger."""
    m = await crear_material(client, descripcion=f"Material no finito {cuerpo}")

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    # raise_app_exceptions=False: la respuesta se observa tal cual un
    # despliegue real la devolvería (jamás un 200 silencioso).
    crudo = AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"X-Actor": "admin-qa"},
    )
    try:
        resp = await crudo.patch(
            f"/api/v1/catalogo/{m['id_lista']}",
            content=cuerpo,
            headers={"content-type": "application/json"},
        )
    finally:
        await crudo.aclose()

    assert resp.status_code == 422, resp.text
    detalle = resp.json()["detail"]
    assert isinstance(detalle, list) and len(detalle) == 1
    assert detalle[0]["type"] == "finite_number"
    assert detalle[0]["loc"] == ["body", "valor_unitario"]
    assert detalle[0]["input"] == input_sanitizado
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")
    assert await _eventos_valor(session, m["id_lista"]) == []


@pytest.mark.parametrize(
    "valor",
    [
        1e-4,               # notación científica sobre-precisa (E5) → 422
        1.0005,             # 4 decimales → 422
        1000000000,         # desbordamiento API (>999 999 999.999) → 422
    ],
)
async def test_RF_008_entradas_decimales_invalidas_422(
    client: AsyncClient, client_admin: AsyncClient, session, valor: float
) -> None:
    """RF-8/RF-2/RF-6: 1e-4/1.0005/desbordamiento se rechazan con 422
    (esquemas estrictos, jamás redondeo silencioso) y el valor persistido
    no cambia."""
    m = await crear_material(client, descripcion=f"Material inválido {valor}")
    resp = await patch_material(client_admin, m["id_lista"], valor_unitario=valor)
    assert resp.status_code == 422, resp.text
    assert await _valor_db(session, m["id_lista"]) == Decimal("1.000")
    assert await _eventos_valor(session, m["id_lista"]) == []


async def test_RF_008_desbordamiento_sql_22003_400_canonico(
    client: AsyncClient, session
) -> None:
    """RF-8/plan §2.5: una regla de PostgreSQL que rechaza la operación por
    desbordamiento NUMERIC (SQLSTATE 22003) responde 400 con el error
    canónico — nunca 500 — y el stock queda intacto."""
    m = await crear_material(client, descripcion="Material desborde SQL")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=999999999.999)
    resp = await client.post(
        "/api/v1/inventario/sumar-cantidad",
        json={
            "destino": "GENERAL",
            "material_id": m["id_lista"],
            "cantidad": 0.001,
        },
    )
    assert resp.status_code == 400, resp.text
    assert "excede el rango" in resp.json()["error"]["message"]
    assert (await stock_seccion(client, 1))[m["id_lista"]] == 999999999.999


async def test_RF_008_respuestas_con_numero_json_no_string(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """RF-8: Valor Unitario, existencias y Valor Total se representan como
    NÚMEROS JSON (sin pérdida de precisión ni strings)."""
    m = await crear_material(client, descripcion="Material JSON")
    await carga_inicial(client, material_id=m["id_lista"], cantidad=4)
    await patch_material(client_admin, m["id_lista"], valor_unitario=12.345)

    resp = await client.get(f"/api/v1/catalogo/{m['id_lista']}")
    assert isinstance(resp.json()["valor_unitario"], float)

    resp = await client.get("/api/v1/inventario/secciones/1")
    fila = next(f for f in resp.json() if f["material_id"] == m["id_lista"])
    assert isinstance(fila["stock_actual"], float)
    assert isinstance(fila["valor_unitario"], float)

    resp = await client.get(RESUMEN)
    assert isinstance(resp.json()["valor_total"], float)
