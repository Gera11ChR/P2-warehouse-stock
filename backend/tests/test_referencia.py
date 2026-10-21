"""REFERENCIA de materiales por Unidad (0030) — pruebas de API (T6,
paquete 2026-10-referencia-materiales-unidades).

Una prueba por requisito `test_req_ref_NNN_*` que asevera la respuesta
HTTP **y** el estado de la base de datos por SQL directo (fixture
`session`):

* REQ-REF-005: listado `{items, total}` con orden derivado por SQL
  (`ORDER BY descripcion, material_id`, nunca `sorted()` de Python),
  `descripcion`/`codigo` del catálogo EN VIVO, U.M. efectiva de la Unidad
  (Q2), línea oculta por material inactivo conservada y reaparición, y
  lectura sin eventos de auditoría.
* REQ-REF-006: alta masiva todo-o-nada (201 con las líneas creadas
  ordenadas como el GET y `total` = creadas); el origen de la interfaz
  (Inventario General / Inventario FO) queda fuera del contrato (422).
* REQ-REF-007: validaciones 422 (cantidad, material_id de cuerpo, campos
  extra, 0/51 líneas, duplicados del payload con `coordinates`), 404
  `MATERIAL_NO_ENCONTRADO`, 409 `REFERENCIA_DUPLICADA`, precedencia de
  errores y atomicidad de la petición mixta.
* REQ-REF-008: modificar solo la cantidad (200 con `updated_at`), no-op
  con la misma cantidad (sin escritura ni evento), 404 para línea
  inexistente u oculta y 422 de validación.
* REQ-REF-009: eliminar (204, fila ausente, material e inventarios
  intactos), reintento 404, línea oculta conservada.
* REQ-REF-010: aislamiento y precedencia (404 antes de 403, Unidad
  inactiva 404 en lectura y escritura, 403 de ajenos, integrante sin
  sección: lectura 200 y escrituras 403, X-Actor ausente/inválido 422 sin
  BD, identificadores fuera de INT4: 403 antes de la BD / 400 canónico /
  422 para 0 y negativos, administrador transversal).
* REQ-REF-011: snapshot (conteo + checksum) de las 11 tablas de negocio
  idéntico tras un ciclo completo POST→PATCH→DELETE→GET.
* REQ-REF-012: exactamente 3 eventos con actor, material, resultado y
  valores previos/nuevos; las peticiones rechazadas no dejan evento y el
  rollback de una petición mixta no deja ni fila ni evento.
* REQ-REF-015: cuerpos canónicos (`{detail:[…]}` / `{error:{…}}` / 403
  vigente), mensajes con «Unidad», 201 como `ReferenciaListOut` y un
  interbloqueo residual 40P01 → 409 controlado (jamás 500).

Casos límite (§6): carrera de dos altas del mismo material (201/409 con
una sola fila y un solo evento) y altas cruzadas en orden distinto (sin
500), por `asyncio.gather` con clientes independientes.
"""

import asyncio
import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.fabrica import carga_inicial, crear_equipo, crear_material

# Nomenclatura oficial (REQ-UNI-006): ningún mensaje de error de la API
# puede contener la palabra antigua.
_PALABRA_ANTIGUA = re.compile(r"equipo", re.IGNORECASE)

# Tablas de negocio que la Referencia no puede alterar (REQ-REF-011);
# misma lista que `sql_tests/test_fase_referencia.py` (11 tablas).
TABLAS_NEGOCIO = (
    "inventario_equipos",
    "inventario_almacen",
    "inventario_fibra",
    "catalogo_materiales",
    "equipo_material_config",
    "movimientos_cabecera",
    "movimientos_detalle",
    "seguimientos",
    "seguimiento_items",
    "actividades_reportes",
    "actas_reportes",
)


def _ruta(equipo_id: int | Any, material_id: int | Any | None = None) -> str:
    base = f"/api/v1/equipos/{equipo_id}/referencia"
    return base if material_id is None else f"{base}/{material_id}"


async def _um_id(client: AsyncClient, nombre: str) -> int:
    resp = await client.get("/api/v1/catalogo/um")
    assert resp.status_code == 200, resp.text
    return next(u["id"] for u in resp.json() if u["nombre"] == nombre)


async def _snapshot_negocio(session: AsyncSession) -> dict[str, Any]:
    """Conteo + checksum (md5 de la concatenación ordenada de los md5 de
    cada fila completa) de cada tabla de negocio: determinista y comparable
    antes/después (mismo cálculo que `sql_tests/test_fase_referencia.py`)."""
    async with session.begin():
        out: dict[str, Any] = {}
        for tabla in TABLAS_NEGOCIO:
            out[tabla] = (
                await session.execute(
                    text(
                        f"SELECT count(*), "
                        f"coalesce(md5(string_agg(md5(t::text), '' "
                        f"ORDER BY md5(t::text))), md5('')) FROM {tabla} t"
                    )
                )
            ).one()
        return out


async def _eventos_referencia(session: AsyncSession) -> list[Any]:
    async with session.begin():
        return list(
            (
                await session.execute(
                    text(
                        "SELECT id, usuario, tipo_accion, material_id, "
                        "resultado, detalles FROM auditoria_eventos "
                        "WHERE tipo_accion IN "
                        "('REFERENCIA_LINEA_CREADA',"
                        "'REFERENCIA_LINEA_MODIFICADA',"
                        "'REFERENCIA_LINEA_ELIMINADA') ORDER BY id"
                    )
                )
            ).all()
        )


async def _contar_eventos_referencia(session: AsyncSession) -> int:
    async with session.begin():
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM auditoria_eventos "
                    "WHERE tipo_accion LIKE 'REFERENCIA%'"
                )
            )
        ).scalar_one()


# ---------------------------------------------------------------- REQ-REF-005


async def test_req_ref_005_listado_ordenado_por_sql_y_total(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-005/C-5: GET devuelve `{items, total}` con las líneas
    ordenadas por `descripcion` (collation de la BD) y luego `material_id`;
    el orden esperado se deriva con SQL, jamás con `sorted()` de Python, y
    `total` cuenta solo los ítems listados."""
    m_z = await crear_material(client, descripcion="Zeta Dos", codigo="REF-Z")
    m_b = await crear_material(client, descripcion="Beta Uno")
    m_m = await crear_material(client, descripcion="Medio Tres", codigo="REF-M")
    m_a = await crear_material(client, descripcion="Alfa Cuatro")
    equipo = await crear_equipo(client, nombre="Unidad Orden")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m_z["id_lista"], "cantidad_semanal": 1},
                {"material_id": m_b["id_lista"], "cantidad_semanal": 2.5},
                {"material_id": m_m["id_lista"], "cantidad_semanal": 3},
                {"material_id": m_a["id_lista"], "cantidad_semanal": 4.5},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"items", "total"}
    assert body["total"] == 4

    # Orden esperado derivado por SQL (mismo ORDER BY que el contrato).
    async with session.begin():
        orden = (
            await session.execute(
                text(
                    "SELECT r.material_id FROM referencia_materiales r "
                    "JOIN catalogo_materiales c ON c.id_lista = r.material_id "
                    "WHERE r.equipo_id = :e AND c.is_active "
                    "ORDER BY c.descripcion ASC, r.material_id ASC"
                ),
                {"e": eid},
            )
        ).scalars().all()
    assert [i["material_id"] for i in body["items"]] == list(orden)

    # Campos exactos de cada línea; codigo puede ser null.
    por_id = {i["material_id"]: i for i in body["items"]}
    for item in body["items"]:
        assert set(item) == {
            "material_id",
            "codigo",
            "descripcion",
            "u_m",
            "cantidad_semanal",
        }
    assert por_id[m_z["id_lista"]]["codigo"] == "REF-Z"
    assert por_id[m_b["id_lista"]]["codigo"] is None
    assert por_id[m_a["id_lista"]]["cantidad_semanal"] == 4.5

    # BD: las 4 filas con sus cantidades.
    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales"),
            )
        ).scalar_one()
    assert n == 4


async def test_req_ref_005_descripcion_y_codigo_vivos_del_catalogo(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-005: `descripcion` y `codigo` se leen del catálogo EN VIVO en
    cada consulta (el siguiente GET refleja el cambio); la fila de la
    Referencia no duplica esos datos."""
    material = await crear_material(
        client, descripcion="Original Vivo", codigo="VIVO-1"
    )
    equipo = await crear_equipo(client, nombre="Unidad Viva")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": material["id_lista"], "cantidad_semanal": 5}
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(_ruta(eid))
    item = resp.json()["items"][0]
    assert item["descripcion"] == "Original Vivo"
    assert item["codigo"] == "VIVO-1"

    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET descripcion = :d, "
                "codigo = :c WHERE id_lista = :m"
            ),
            {"d": "Renombrado Vivo", "c": "VIVO-2", "m": material["id_lista"]},
        )

    resp = await client.get(_ruta(eid))
    item = resp.json()["items"][0]
    assert item["descripcion"] == "Renombrado Vivo"
    assert item["codigo"] == "VIVO-2"

    async with session.begin():
        cantidad = (
            await session.execute(
                text(
                    "SELECT cantidad_semanal FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": material["id_lista"]},
            )
        ).scalar_one()
    assert Decimal(str(cantidad)) == Decimal("5.000")


async def test_req_ref_005_um_efectiva_local_frente_a_catalogo(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-005/C-1/Q2/P-9: `u_m` es la U.M. EFECTIVA de la Unidad — la
    local de `equipo_material_config` donde exista y la del catálogo en el
    resto (COALESCE igual al `um_efectivo` del inventario)."""
    m1 = await crear_material(client, descripcion="Mat UM A", u_m="PZ")
    m2 = await crear_material(client, descripcion="Mat UM B", u_m="LT")
    equipo = await crear_equipo(client, nombre="Unidad UM")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 5},
                {"material_id": m2["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(_ruta(eid))
    por_id = {i["material_id"]: i for i in resp.json()["items"]}
    assert por_id[m1["id_lista"]]["u_m"] == "PZ"
    assert por_id[m2["id_lista"]]["u_m"] == "LT"

    um_metro = await _um_id(client, "METRO (M)")
    resp = await client.patch(
        f"/api/v1/equipos/{eid}/inventario/{m1['id_lista']}",
        json={"um_local_id": um_metro},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(_ruta(eid))
    por_id = {i["material_id"]: i for i in resp.json()["items"]}
    assert por_id[m1["id_lista"]]["u_m"] == "METRO (M)"  # local
    assert por_id[m2["id_lista"]]["u_m"] == "LT"  # sin config: catálogo

    async with session.begin():
        config = (
            await session.execute(
                text(
                    "SELECT um_local_id FROM equipo_material_config "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": m1["id_lista"]},
            )
        ).scalar_one()
    assert config == um_metro


async def test_req_ref_005_material_inactivo_oculto_y_reaparece(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-005/C-4: la línea de un material inactivo NO se lista pero se
    CONSERVA, y reaparece sin cambios al reactivarlo por SQL (no hay
    endpoint de reactivación)."""
    m1 = await crear_material(client, descripcion="Mat Oc A")
    m2 = await crear_material(client, descripcion="Mat Oc B")
    m3 = await crear_material(client, descripcion="Mat Oc C")
    equipo = await crear_equipo(client, nombre="Unidad Oculta")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 5},
                {"material_id": m2["id_lista"], "cantidad_semanal": 2.5},
                {"material_id": m3["id_lista"], "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET is_active = false "
                "WHERE id_lista = :m"
            ),
            {"m": m2["id_lista"]},
        )

    resp = await client.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert m2["id_lista"] not in [i["material_id"] for i in body["items"]]

    # La línea oculta se conserva en BD.
    async with session.begin():
        cantidad = (
            await session.execute(
                text(
                    "SELECT cantidad_semanal FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": m2["id_lista"]},
            )
        ).scalar_one()
    assert Decimal(str(cantidad)) == Decimal("2.500")

    # Reactivación por SQL: la línea reaparece sin cambios.
    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET is_active = true "
                "WHERE id_lista = :m"
            ),
            {"m": m2["id_lista"]},
        )
    resp = await client.get(_ruta(eid))
    body = resp.json()
    assert body["total"] == 3
    por_id = {i["material_id"]: i for i in body["items"]}
    assert por_id[m2["id_lista"]]["cantidad_semanal"] == 2.5


async def test_req_ref_005_get_sin_eventos_de_auditoria(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-011/012: la lectura de la Referencia NO emite eventos de
    auditoría (ni ningún otro tipo de escritura)."""
    material = await crear_material(client, descripcion="Mat Lectura")
    equipo = await crear_equipo(client, nombre="Unidad Lectura")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": material["id_lista"], "cantidad_semanal": 5}
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    async with session.begin():
        antes = (
            await session.execute(text("SELECT count(*) FROM auditoria_eventos"))
        ).scalar_one()

    for _ in range(2):
        resp = await client.get(_ruta(eid))
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 1

    async with session.begin():
        despues = (
            await session.execute(text("SELECT count(*) FROM auditoria_eventos"))
        ).scalar_one()
    assert despues == antes


async def test_req_ref_005_codigo_y_um_null_se_serializan(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-005/015: el catálogo admite `codigo`/`u_m` NULL; el listado
    los devuelve como `null` sin degradar la respuesta (jamás 500)."""
    equipo = await crear_equipo(client, nombre="Unidad Nulos Ref")
    eid = equipo["equipo_id"]
    async with session.begin():
        mid = (
            await session.execute(
                text(
                    "INSERT INTO catalogo_materiales (descripcion, codigo, u_m) "
                    "VALUES ('Sin codigo UM', NULL, NULL) RETURNING id_lista"
                )
            )
        ).scalar_one()

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid, "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 201, resp.text
    resp = await client.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["codigo"] is None and item["u_m"] is None


# ---------------------------------------------------------------- REQ-REF-006


async def test_req_ref_006_alta_201_lote_ordenado_total_y_origen_fuera_de_contrato(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-006/C-8: alta masiva de 1..50 líneas en una transacción; 201
    con las líneas creadas ordenadas como el GET y `total` = creadas. El
    origen de la interfaz (Inventario General / Inventario FO) NO forma
    parte del contrato: campo extra → 422 sin efectos."""
    m_z = await crear_material(client, descripcion="Zeta Alta")
    m_a = await crear_material(client, descripcion="Alfa Alta")
    m_m = await crear_material(client, descripcion="Medio Alta")
    equipo = await crear_equipo(client, nombre="Unidad Alta")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m_z["id_lista"], "cantidad_semanal": 1},
                {"material_id": m_a["id_lista"], "cantidad_semanal": 2},
                {"material_id": m_m["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    creadas = resp.json()
    assert set(creadas) == {"items", "total"}
    assert creadas["total"] == 3

    resp = await client.get(_ruta(eid))
    listado = resp.json()
    assert creadas == listado  # el 201 replica el orden y contenido del GET
    assert [i["material_id"] for i in creadas["items"]] == [
        m_a["id_lista"],
        m_m["id_lista"],
        m_z["id_lista"],
    ]

    # BD: tres filas con sus cantidades.
    async with session.begin():
        filas = (
            await session.execute(
                text(
                    "SELECT material_id, cantidad_semanal "
                    "FROM referencia_materiales WHERE equipo_id = :e "
                    "ORDER BY material_id"
                ),
                {"e": eid},
            )
        ).all()
    assert {
        f.material_id: Decimal(str(f.cantidad_semanal)) for f in filas
    } == {
        m_a["id_lista"]: Decimal("2.000"),
        m_m["id_lista"]: Decimal("3.000"),
        m_z["id_lista"]: Decimal("1.000"),
    }

    # Origen fuera del contrato: 422 de validación y cero efectos.
    for extra in (
        {
            "origen": "Inventario General",
            "lineas": [{"material_id": m_a["id_lista"], "cantidad_semanal": 9}],
        },
        {
            "lineas": [
                {
                    "material_id": m_a["id_lista"],
                    "cantidad_semanal": 9,
                    "origen": "Inventario FO",
                }
            ]
        },
    ):
        resp = await client.post(_ruta(eid), json=extra)
        assert resp.status_code == 422, resp.text
        assert set(resp.json()) == {"detail"}

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 3
    assert await _contar_eventos_referencia(session) == 3


# ---------------------------------------------------------------- REQ-REF-007


@pytest.mark.parametrize(
    "cantidad",
    [0, -1, -0.001, 1.2345, 9999999999999],
    ids=["cero", "negativa", "negativa_fraccion", "4_decimales", "13_digitos"],
)
async def test_req_ref_007_cantidad_invalida_422(
    client: AsyncClient, session: AsyncSession, cantidad: float | int
) -> None:
    """REQ-REF-007/C-13: cantidad ≤ 0, con más de 3 decimales o más de 12
    dígitos → 422 de validación (`{detail:[…]}`) sin escribir nada."""
    material = await crear_material(client, descripcion=f"Mat Q {cantidad}")
    equipo = await crear_equipo(client, nombre=f"Unidad Q {cantidad}")

    resp = await client.post(
        _ruta(equipo["equipo_id"]),
        json={
            "lineas": [
                {"material_id": material["id_lista"], "cantidad_semanal": cantidad}
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    assert set(resp.json()) == {"detail"}

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0
    assert await _contar_eventos_referencia(session) == 0


@pytest.mark.parametrize(
    "material_id",
    [0, -3, 2147483648, 10**30],
    ids=["cero", "negativo", "mayor_int4", "enorme"],
)
async def test_req_ref_007_material_id_de_cuerpo_invalido_422(
    client: AsyncClient, session: AsyncSession, material_id: int
) -> None:
    """REQ-REF-007/015: `material_id` del CUERPO que no es un INT4 positivo
    es un 422 de validación (a diferencia del 400 canónico de la ruta)."""
    equipo = await crear_equipo(client, nombre=f"Unidad Mid {material_id}")

    resp = await client.post(
        _ruta(equipo["equipo_id"]),
        json={"lineas": [{"material_id": material_id, "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 422, resp.text
    assert set(resp.json()) == {"detail"}

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0


async def test_req_ref_007_campos_extra_y_lineas_0_o_51_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-007: campos no declarados (`extra="forbid"`), 0 líneas y 51
    líneas (límite defensivo) → 422 de validación sin efectos."""
    material = await crear_material(client, descripcion="Mat Extra")
    equipo = await crear_equipo(client, nombre="Unidad Extra")
    eid = equipo["equipo_id"]
    mid = material["id_lista"]

    casos: list[dict] = [
        {"lineas": []},  # 0 líneas
        {"lineas": [{"material_id": mid, "cantidad_semanal": 1}] * 51},
        {
            "lineas": [{"material_id": mid, "cantidad_semanal": 1}],
            "notas": "x",  # campo extra en la raíz
        },
        {
            "lineas": [
                {
                    "material_id": mid,
                    "cantidad_semanal": 1,
                    "origen": "Inventario General",  # extra por línea
                }
            ]
        },
        {
            "lineas": [
                {"material_id": mid, "cantidad_semanal": 1, "stock": 3}
            ]
        },
    ]
    for payload in casos:
        resp = await client.post(_ruta(eid), json=payload)
        assert resp.status_code == 422, resp.text
        assert set(resp.json()) == {"detail"}

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0


async def test_req_ref_007_material_repetido_422_linea_duplicada(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-007: el mismo `material_id` dos veces en el payload → 422
    `REFERENCIA_LINEA_DUPLICADA` con las coordinates de la 2.ª aparición
    (índice cero-basado), sin tocar la BD."""
    m1 = await crear_material(client, descripcion="Mat Dup A")
    m2 = await crear_material(client, descripcion="Mat Dup B")
    equipo = await crear_equipo(client, nombre="Unidad Dup")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 1},
                {"material_id": m2["id_lista"], "cantidad_semanal": 2},
                {"material_id": m1["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "REFERENCIA_LINEA_DUPLICADA"
    assert error["coordinates"] == [{"linea": 2, "material_id": m1["id_lista"]}]

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0
    assert await _contar_eventos_referencia(session) == 0


async def test_req_ref_007_material_inexistente_o_inactivo_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-007: material inexistente o inactivo → 404
    `MATERIAL_NO_ENCONTRADO` con la primera línea por índice (coordinates
    con `linea`); nada se crea."""
    m1 = await crear_material(client, descripcion="Mat 404 A")
    m2 = await crear_material(client, descripcion="Mat 404 B")
    m3 = await crear_material(client, descripcion="Mat 404 C")
    equipo = await crear_equipo(client, nombre="Unidad 404")
    eid = equipo["equipo_id"]

    # Material inexistente: primera línea por índice.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": 999999, "cantidad_semanal": 1},
                {"material_id": m1["id_lista"], "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert error["code"] == "MATERIAL_NO_ENCONTRADO"
    assert error["coordinates"] == [{"linea": 0, "material_id": 999999}]

    # Material inactivo del catálogo (en mitad del payload).
    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET is_active = false "
                "WHERE id_lista = :m"
            ),
            {"m": m2["id_lista"]},
        )
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 1},
                {"material_id": m3["id_lista"], "cantidad_semanal": 1},
                {"material_id": m2["id_lista"], "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert error["code"] == "MATERIAL_NO_ENCONTRADO"
    assert error["coordinates"] == [{"linea": 2, "material_id": m2["id_lista"]}]

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0


async def test_req_ref_007_material_ya_presente_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-007: material ya presente en la Referencia → 409
    `REFERENCIA_DUPLICADA` con la primera línea por índice; la línea
    existente NO se modifica."""
    m1 = await crear_material(client, descripcion="Mat 409 A")
    m2 = await crear_material(client, descripcion="Mat 409 B")
    equipo = await crear_equipo(client, nombre="Unidad 409")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 5}
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 9}
            ]
        },
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert error["code"] == "REFERENCIA_DUPLICADA"
    assert error["coordinates"] == [{"linea": 0, "material_id": m1["id_lista"]}]

    # Con dos líneas: la primera ya presente por índice.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m2["id_lista"], "cantidad_semanal": 1},
                {"material_id": m1["id_lista"], "cantidad_semanal": 9},
            ]
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["coordinates"] == [
        {"linea": 1, "material_id": m1["id_lista"]}
    ]

    # La línea existente conserva su cantidad original.
    async with session.begin():
        cantidad = (
            await session.execute(
                text(
                    "SELECT cantidad_semanal FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": m1["id_lista"]},
            )
        ).scalar_one()
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert Decimal(str(cantidad)) == Decimal("5.000")
    assert n == 1
    assert await _contar_eventos_referencia(session) == 1


async def test_req_ref_007_precedencia_de_errores(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-006: con varios errores a la vez el orden es 422 (duplicados
    del payload) → 404 (materiales desconocidos/inactivos) → 409 (ya
    presentes), siempre la primera línea por índice."""
    m1 = await crear_material(client, descripcion="Mat Prec A")
    m2 = await crear_material(client, descripcion="Mat Prec B")
    equipo = await crear_equipo(client, nombre="Unidad Prec")
    eid = equipo["equipo_id"]
    mid1, mid2 = m1["id_lista"], m2["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 201, resp.text

    # Duplicado del payload gana sobre material inexistente (422).
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid2, "cantidad_semanal": 1},
                {"material_id": mid2, "cantidad_semanal": 1},
                {"material_id": 999999, "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_LINEA_DUPLICADA"
    assert resp.json()["error"]["coordinates"] == [
        {"linea": 1, "material_id": mid2}
    ]

    # Material inexistente gana sobre ya presente (404).
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": 999999, "cantidad_semanal": 1},
                {"material_id": mid1, "cantidad_semanal": 2},
            ]
        },
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "MATERIAL_NO_ENCONTRADO"
    assert resp.json()["error"]["coordinates"] == [
        {"linea": 0, "material_id": 999999}
    ]

    # Ya presente sin otros errores (409, primera línea por índice).
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid1, "cantidad_semanal": 2},
                {"material_id": mid2, "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_DUPLICADA"
    assert resp.json()["error"]["coordinates"] == [
        {"linea": 0, "material_id": mid1}
    ]

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 1
    assert await _contar_eventos_referencia(session) == 1


async def test_req_ref_007_todo_o_nada_peticion_mixta(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-006/007: una petición mixta (líneas válidas + inválidas) no
    crea NINGUNA fila ni evento — atomicidad de la transacción."""
    m1 = await crear_material(client, descripcion="Mat TON A")
    m2 = await crear_material(client, descripcion="Mat TON B")
    m3 = await crear_material(client, descripcion="Mat TON C")
    equipo = await crear_equipo(client, nombre="Unidad TON")
    eid = equipo["equipo_id"]
    base = [
        {"material_id": m1["id_lista"], "cantidad_semanal": 1},
        {"material_id": m2["id_lista"], "cantidad_semanal": 2},
    ]

    # Cantidad inválida en la tercera línea → 422, nada creado.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                *base,
                {"material_id": m3["id_lista"], "cantidad_semanal": 0},
            ]
        },
    )
    assert resp.status_code == 422, resp.text

    # Material inexistente en la tercera línea → 404, nada creado.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                *base,
                {"material_id": 999999, "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "MATERIAL_NO_ENCONTRADO"
    assert resp.json()["error"]["coordinates"] == [
        {"linea": 2, "material_id": 999999}
    ]

    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0
    assert await _contar_eventos_referencia(session) == 0


# ---------------------------------------------------------------- REQ-REF-008


async def test_req_ref_008_modificar_200_actualiza_cantidad_y_timestamp(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-008/C-11/Q4: PATCH actualiza SOLO la Cantidad Semanal y
    refresca `updated_at` (verificado por SQL); no existe campo para
    cambiar el material (extra → 422)."""
    m1 = await crear_material(client, descripcion="Mat Mod A")
    m2 = await crear_material(client, descripcion="Mat Mod B")
    equipo = await crear_equipo(client, nombre="Unidad Mod")
    eid = equipo["equipo_id"]
    mid1, mid2 = m1["id_lista"], m2["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid1, "cantidad_semanal": 5},
                {"material_id": mid2, "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    async with session.begin():
        antes = (
            await session.execute(
                text(
                    "SELECT updated_at FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()

    resp = await client.patch(
        _ruta(eid, mid1), json={"cantidad_semanal": 7.5}
    )
    assert resp.status_code == 200, resp.text
    linea = resp.json()
    assert set(linea) == {
        "material_id",
        "codigo",
        "descripcion",
        "u_m",
        "cantidad_semanal",
    }
    assert linea["material_id"] == mid1  # el material NO cambia
    assert linea["cantidad_semanal"] == 7.5

    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT cantidad_semanal, updated_at "
                    "FROM referencia_materiales WHERE equipo_id = :e "
                    "AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).one()
    assert Decimal(str(fila.cantidad_semanal)) == Decimal("7.500")
    assert fila.updated_at != antes  # el timestamp se refrescó

    # El material de una línea NO se puede cambiar: campo extra → 422.
    resp = await client.patch(
        _ruta(eid, mid1),
        json={"cantidad_semanal": 8, "material_id": mid2},
    )
    assert resp.status_code == 422, resp.text


async def test_req_ref_008_noop_misma_cantidad_200_sin_escritura(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-008/C-11/H-08: PATCH con la MISMA cantidad responde 200 sin
    escribir: `updated_at` intacto y CERO eventos nuevos (no-op)."""
    m1 = await crear_material(client, descripcion="Mat Noop")
    equipo = await crear_equipo(client, nombre="Unidad Noop")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    async with session.begin():
        antes = (
            await session.execute(
                text(
                    "SELECT updated_at FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()
    ev_antes = await _contar_eventos_referencia(session)

    resp = await client.patch(_ruta(eid, mid1), json={"cantidad_semanal": 5})
    assert resp.status_code == 200, resp.text
    assert resp.json()["cantidad_semanal"] == 5

    async with session.begin():
        despues = (
            await session.execute(
                text(
                    "SELECT updated_at FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()
    assert despues == antes  # sin refresco de timestamp
    assert await _contar_eventos_referencia(session) == ev_antes == 1


async def test_req_ref_008_modificar_404_linea_inexistente_u_oculta(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-008/C-4: línea inexistente o con material inactivo → 404
    `REFERENCIA_NO_ENCONTRADA`; la línea oculta se CONSERVA."""
    m1 = await crear_material(client, descripcion="Mat Mod404 A")
    m2 = await crear_material(client, descripcion="Mat Mod404 B")
    m3 = await crear_material(client, descripcion="Mat Mod404 C")
    equipo = await crear_equipo(client, nombre="Unidad Mod404")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 5},
                {"material_id": m3["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    # Línea inexistente (material activo pero sin línea): 404.
    resp = await client.patch(
        _ruta(eid, m2["id_lista"]), json={"cantidad_semanal": 9}
    )
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert error["code"] == "REFERENCIA_NO_ENCONTRADA"
    assert error["coordinates"] == [
        {"equipo_id": eid, "material_id": m2["id_lista"]}
    ]

    # Línea oculta por material inactivo: 404 y la línea se conserva.
    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET is_active = false "
                "WHERE id_lista = :m"
            ),
            {"m": m3["id_lista"]},
        )
    resp = await client.patch(
        _ruta(eid, m3["id_lista"]), json={"cantidad_semanal": 9}
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_NO_ENCONTRADA"

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": m3["id_lista"]},
            )
        ).scalar_one()
    assert n == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"cantidad_semanal": 0},
        {"cantidad_semanal": -5},
        {"cantidad_semanal": 1.2345},
        {"cantidad_semanal": 9999999999999},
        {"cantidad_semanal": 1, "material_id": 2},
    ],
    ids=[
        "cero",
        "negativa",
        "4_decimales",
        "13_digitos",
        "campo_extra",
    ],
)
async def test_req_ref_008_modificar_422_cantidad_invalida(
    client: AsyncClient, session: AsyncSession, payload: dict
) -> None:
    """REQ-REF-008/007: cantidad inválida o campo no declarado en el PATCH →
    422 de validación y la línea queda intacta."""
    m1 = await crear_material(client, descripcion="Mat Mod422")
    equipo = await crear_equipo(client, nombre="Unidad Mod422")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    resp = await client.patch(_ruta(eid, mid1), json=payload)
    assert resp.status_code == 422, resp.text
    assert set(resp.json()) == {"detail"}

    async with session.begin():
        cantidad = (
            await session.execute(
                text(
                    "SELECT cantidad_semanal FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()
    assert Decimal(str(cantidad)) == Decimal("5.000")


# ---------------------------------------------------------------- REQ-REF-009


async def test_req_ref_009_eliminar_204_reintento_404_e_inventarios_intactos(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-009/C-3: DELETE elimina físicamente la línea (204), el
    material y los inventarios quedan intactos, y el reintento responde
    404 `REFERENCIA_NO_ENCONTRADA`."""
    m1 = await crear_material(client, descripcion="Mat Del A")
    m2 = await crear_material(client, descripcion="Mat Del B")
    equipo = await crear_equipo(client, nombre="Unidad Del")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    # Siembra de inventarios físicos del material (REQ-REF-011).
    async with session.begin():
        almacen = (
            await session.execute(
                text(
                    "SELECT almacen_id FROM secciones "
                    "WHERE tipo = 'GENERAL' LIMIT 1"
                )
            )
        ).scalar_one()
        await session.execute(
            text(
                "INSERT INTO inventario_equipos "
                "(equipo_id, material_id, stock_actual) VALUES (:e, :m, 11.5)"
            ),
            {"e": eid, "m": mid1},
        )
        await session.execute(
            text(
                "INSERT INTO inventario_almacen "
                "(almacen_id, material_id, stock_actual) VALUES (:a, :m, 22.5)"
            ),
            {"a": almacen, "m": mid1},
        )

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid1, "cantidad_semanal": 5},
                {"material_id": m2["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.delete(_ruta(eid, mid1))
    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    async with session.begin():
        fila = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()
        cat = (
            await session.execute(
                text(
                    "SELECT count(*) FROM catalogo_materiales "
                    "WHERE id_lista = :m AND is_active"
                ),
                {"m": mid1},
            )
        ).scalar_one()
        inv_eq = (
            await session.execute(
                text(
                    "SELECT stock_actual FROM inventario_equipos "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid1},
            )
        ).scalar_one()
        inv_alm = (
            await session.execute(
                text(
                    "SELECT stock_actual FROM inventario_almacen "
                    "WHERE almacen_id = :a AND material_id = :m"
                ),
                {"a": almacen, "m": mid1},
            )
        ).scalar_one()
    assert fila == 0  # la fila ya no existe
    assert cat == 1  # el material sigue en el catálogo
    assert Decimal(str(inv_eq)) == Decimal("11.5")  # inventarios intactos
    assert Decimal(str(inv_alm)) == Decimal("22.5")

    # Reintento del DELETE ya ejecutado → 404.
    resp = await client.delete(_ruta(eid, mid1))
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_NO_ENCONTRADA"


async def test_req_ref_009_eliminar_404_linea_inexistente_u_oculta(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-009/C-4: línea inexistente o con material inactivo → 404 y la
    línea oculta se conserva (no se elimina nada)."""
    m1 = await crear_material(client, descripcion="Mat Del404 A")
    m2 = await crear_material(client, descripcion="Mat Del404 B")
    m3 = await crear_material(client, descripcion="Mat Del404 C")
    equipo = await crear_equipo(client, nombre="Unidad Del404")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": m1["id_lista"], "cantidad_semanal": 5},
                {"material_id": m3["id_lista"], "cantidad_semanal": 3},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    # Línea inexistente (material activo sin línea): 404.
    resp = await client.delete(_ruta(eid, m2["id_lista"]))
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_NO_ENCONTRADA"

    # Línea oculta por material inactivo: 404 y la línea se conserva.
    async with session.begin():
        await session.execute(
            text(
                "UPDATE catalogo_materiales SET is_active = false "
                "WHERE id_lista = :m"
            ),
            {"m": m3["id_lista"]},
        )
    resp = await client.delete(_ruta(eid, m3["id_lista"]))
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_NO_ENCONTRADA"

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 2  # ambas líneas conservadas


# ---------------------------------------------------------------- REQ-REF-010


async def test_req_ref_010_404_antes_de_403(
    client: AsyncClient, client_sin_scope: AsyncClient
) -> None:
    """REQ-REF-010 (precedencia 3 antes de 4): una Unidad inexistente
    responde 404 antes que el 403 de pertenencia — tanto para un integrante
    de otra Unidad como para un actor ajeno — en lectura y escritura."""
    await crear_equipo(client, nombre="Unidad Anfitriona")  # qa es integrante

    resp = await client.get("/api/v1/equipos/999999/referencia")
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["message"] == "Unidad no encontrada"

    resp = await client.post(
        "/api/v1/equipos/999999/referencia",
        json={"lineas": [{"material_id": 1, "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 404, resp.text

    # La lectura no aplica la regla de autenticación: el actor sin scope
    # también recibe 404 (nunca 403) para una Unidad inexistente.
    resp = await client_sin_scope.get("/api/v1/equipos/999999/referencia")
    assert resp.status_code == 404, resp.text


@pytest.mark.critical
async def test_req_ref_010_unidad_inactiva_404_en_las_cuatro_operaciones(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-010/C-9 (Q1 = A): una Unidad de baja responde 404 en LECTURA
    y ESCRITURA (las cuatro operaciones), sin efectos; la línea se
    conserva."""
    m1 = await crear_material(client, descripcion="Mat Inactiva A")
    m2 = await crear_material(client, descripcion="Mat Inactiva B")
    equipo = await crear_equipo(client, nombre="Unidad Inactiva")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    async with session.begin():
        await session.execute(
            text("UPDATE equipos SET is_active = false WHERE equipo_id = :e"),
            {"e": eid},
        )

    resp = await client.get(_ruta(eid))
    assert resp.status_code == 404, resp.text
    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": m2["id_lista"], "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 404, resp.text
    resp = await client.patch(_ruta(eid, mid1), json={"cantidad_semanal": 9})
    assert resp.status_code == 404, resp.text
    resp = await client.delete(_ruta(eid, mid1))
    assert resp.status_code == 404, resp.text

    # Sin efectos: la línea original sigue y no se creó ni auditó nada nuevo.
    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 1
    assert await _contar_eventos_referencia(session) == 1


async def test_req_ref_010_actor_ajeno_403_en_las_cuatro(
    client: AsyncClient, client_factory: Any, session: AsyncSession
) -> None:
    """REQ-REF-010 (precedencia 4): actor con scope pero sin membresía y no
    administrador → 403 con el cuerpo de autorización vigente en las cuatro
    operaciones, sin efectos; una Unidad inexistente sigue siendo 404."""
    m1 = await crear_material(client, descripcion="Mat Ajeno A")
    m2 = await crear_material(client, descripcion="Mat Ajeno B")
    equipo = await crear_equipo(client, nombre="Unidad Ajen")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": m1["id_lista"], "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    # El actor "ajeno" tiene scope (sección 1) pero no es integrante.
    async with session.begin():
        await session.execute(
            text(
                "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
                "VALUES ('ajeno', 1)"
            )
        )

    async with client_factory("ajeno") as ajeno:
        resp = await ajeno.get(_ruta(eid))
        assert resp.status_code == 403, resp.text
        error = resp.json()["error"]
        assert error["code"] == "AUTHORIZATION_FAILED"
        assert error["message"] == "El actor no tiene acceso a esta unidad"
        assert error["actor"] == "ajeno"

        resp = await ajeno.post(
            _ruta(eid),
            json={
                "lineas": [
                    {"material_id": m2["id_lista"], "cantidad_semanal": 1}
                ]
            },
        )
        assert resp.status_code == 403, resp.text
        resp = await ajeno.patch(
            _ruta(eid, m1["id_lista"]), json={"cantidad_semanal": 9}
        )
        assert resp.status_code == 403, resp.text
        resp = await ajeno.delete(_ruta(eid, m1["id_lista"]))
        assert resp.status_code == 403, resp.text

        # Unidad inexistente con actor ajeno: 404 antes que 403.
        resp = await ajeno.get("/api/v1/equipos/999999/referencia")
        assert resp.status_code == 404, resp.text

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 1
    assert await _contar_eventos_referencia(session) == 1


async def test_req_ref_010_integrante_sin_seccion_lectura_200_escrituras_403(
    client: AsyncClient, client_sin_scope: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-010/C-12 (Q6): un integrante SIN sección asignada puede LEER
    (solo pertenencia) pero las escrituras aplican la regla de
    autenticación de Configuración → 403."""
    m1 = await crear_material(client, descripcion="Mat SinScope A")
    m2 = await crear_material(client, descripcion="Mat SinScope B")
    equipo = await crear_equipo(
        client, nombre="Unidad SinScope", integrantes=["intruso", "qa"]
    )
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    resp = await client_sin_scope.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = await client_sin_scope.post(
        _ruta(eid),
        json={
            "lineas": [{"material_id": m2["id_lista"], "cantidad_semanal": 1}]
        },
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["message"] == (
        "Actor sin alcance de sección asignado"
    )
    resp = await client_sin_scope.patch(
        _ruta(eid, mid1), json={"cantidad_semanal": 9}
    )
    assert resp.status_code == 403, resp.text
    resp = await client_sin_scope.delete(_ruta(eid, mid1))
    assert resp.status_code == 403, resp.text

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 1


async def test_req_ref_010_x_actor_ausente_o_invalido_422_sin_consultar_bd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-REF-010 (precedencia 1): `X-Actor` ausente o inválido responde
    422 SIN consultar datos de negocio (el espía de `SessionLocal` de
    seguridad no registra ni un checkout)."""
    from app import security
    from app.main import app

    class _Spy:
        def __init__(self) -> None:
            self.checkouts = 0

        def __call__(self) -> Any:
            self.checkouts += 1
            raise AssertionError("X-Actor inválido no debe abrir sesión")

    spy = _Spy()
    monkeypatch.setattr(security, "SessionLocal", spy)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as sin_actor:
        resp = await sin_actor.get("/api/v1/equipos/1/referencia")
    assert resp.status_code == 422, resp.text
    assert set(resp.json()) == {"detail"}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Actor": "   "},
    ) as actor_invalido:
        resp = await actor_invalido.get("/api/v1/equipos/1/referencia")
    assert resp.status_code == 422, resp.text

    assert spy.checkouts == 0


async def test_req_ref_010_ids_fuera_de_rango_400_403_y_422(
    client: AsyncClient,
    client_admin: AsyncClient,
    client_sin_scope: AsyncClient,
) -> None:
    """REQ-REF-010/015: identificadores de RUTA fuera de INT4 — la
    autenticación precede a la BD (403 para un actor sin scope, observación
    R1 de @sec-ops), el actor autorizado recibe el 400 canónico
    `NUMERIC_OUT_OF_RANGE`, y el 0/negativo es 422 de validación."""
    ID_GRANDE = 10**12
    payload = {"lineas": [{"material_id": 1, "cantidad_semanal": 1}]}

    # Escritura con actor SIN scope: 403 — la autenticación precede a la BD.
    resp = await client_sin_scope.post(
        f"/api/v1/equipos/{ID_GRANDE}/referencia", json=payload
    )
    assert resp.status_code == 403, resp.text

    # Con actor autorizado el ID sí llega a PostgreSQL → 400 canónico.
    resp = await client_admin.post(
        f"/api/v1/equipos/{ID_GRANDE}/referencia", json=payload
    )
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "NUMERIC_OUT_OF_RANGE"
    assert error["coordinates"] == []

    # Lectura con actor regular: la consulta de Unidad precede a la
    # pertenencia → 400 canónico.
    resp = await client.get(f"/api/v1/equipos/{ID_GRANDE}/referencia")
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "NUMERIC_OUT_OF_RANGE"

    # ID de ruta 0 o negativo: 422 de validación.
    resp = await client.get("/api/v1/equipos/0/referencia")
    assert resp.status_code == 422, resp.text
    resp = await client.post("/api/v1/equipos/-1/referencia", json=payload)
    assert resp.status_code == 422, resp.text
    resp = await client.patch(
        "/api/v1/equipos/1/referencia/0", json={"cantidad_semanal": 1}
    )
    assert resp.status_code == 422, resp.text
    resp = await client.delete("/api/v1/equipos/1/referencia/-3")
    assert resp.status_code == 422, resp.text


async def test_req_ref_010_admin_transversal_lee_y_escribe(
    client: AsyncClient, client_admin: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-010/C-12: el administrador lee y escribe en CUALQUIER Unidad
    (pase transversal) sin pertenencia."""
    m1 = await crear_material(client, descripcion="Mat Admin A")
    m2 = await crear_material(client, descripcion="Mat Admin B")
    equipo = await crear_equipo(client, nombre="Unidad Admin")
    eid = equipo["equipo_id"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": m1["id_lista"], "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    resp = await client_admin.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = await client_admin.post(
        _ruta(eid),
        json={"lineas": [{"material_id": m2["id_lista"], "cantidad_semanal": 2}]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["total"] == 1

    resp = await client_admin.patch(
        _ruta(eid, m1["id_lista"]), json={"cantidad_semanal": 9}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cantidad_semanal"] == 9

    resp = await client_admin.delete(_ruta(eid, m2["id_lista"]))
    assert resp.status_code == 204, resp.text

    async with session.begin():
        filas = (
            await session.execute(
                text(
                    "SELECT material_id, cantidad_semanal "
                    "FROM referencia_materiales WHERE equipo_id = :e "
                    "ORDER BY material_id"
                ),
                {"e": eid},
            )
        ).all()
    assert [
        (f.material_id, Decimal(str(f.cantidad_semanal))) for f in filas
    ] == [(m1["id_lista"], Decimal("9.000"))]


# ---------------------------------------------------------------- REQ-REF-011


@pytest.mark.critical
async def test_req_ref_011_snapshot_tablas_negocio_intactas(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-011: un ciclo completo por API (POST→PATCH→DELETE→GET) deja
    idénticas las 11 tablas de negocio (conteo + checksum md5 por fila,
    mismo cálculo que `sql_tests/test_fase_referencia.py`); la única
    escritura permitida fuera de `referencia_materiales` es el ledger."""
    material = await crear_material(client, descripcion="Mat Snapshot")
    equipo = await crear_equipo(client, nombre="Unidad Snapshot")
    eid = equipo["equipo_id"]
    mid = material["id_lista"]
    await carga_inicial(client, material_id=mid, cantidad=100)

    # Siembra de negocio por SQL para que el checksum sea significativo
    # (inventario_almacen ya queda sembrado por `carga_inicial`).
    async with session.begin():
        await session.execute(
            text(
                "INSERT INTO inventario_equipos "
                "(equipo_id, material_id, stock_actual) VALUES (:e, :m, 42.5)"
            ),
            {"e": eid, "m": mid},
        )
        await session.execute(
            text(
                "INSERT INTO inventario_fibra (material_id, stock_actual) "
                "VALUES (:m, 40)"
            ),
            {"m": mid},
        )
        await session.execute(
            text(
                "INSERT INTO equipo_material_config "
                "(equipo_id, material_id, stock_minimo_local) "
                "VALUES (:e, :m, 3)"
            ),
            {"e": eid, "m": mid},
        )

    antes = await _snapshot_negocio(session)

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text
    resp = await client.patch(_ruta(eid, mid), json={"cantidad_semanal": 7.5})
    assert resp.status_code == 200, resp.text
    resp = await client.delete(_ruta(eid, mid))
    assert resp.status_code == 204, resp.text
    resp = await client.get(_ruta(eid))
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 0

    despues = await _snapshot_negocio(session)
    assert despues == antes


# ---------------------------------------------------------------- REQ-REF-012


@pytest.mark.critical
async def test_req_ref_012_auditoria_tres_eventos_con_valores_previos_y_nuevos(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-012: POST→PATCH→DELETE emiten exactamente 3 eventos
    `REFERENCIA_LINEA_CREADA/_MODIFICADA/_ELIMINADA`, en orden, con el
    actor, el material, `resultado='EXITO'` y los valores anteriores y
    nuevos en `detalles`."""
    m1 = await crear_material(client, descripcion="Mat Audit")
    equipo = await crear_equipo(client, nombre="Unidad Audit")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text
    resp = await client.patch(_ruta(eid, mid1), json={"cantidad_semanal": 7.5})
    assert resp.status_code == 200, resp.text
    resp = await client.delete(_ruta(eid, mid1))
    assert resp.status_code == 204, resp.text

    eventos = await _eventos_referencia(session)
    assert [e.tipo_accion for e in eventos] == [
        "REFERENCIA_LINEA_CREADA",
        "REFERENCIA_LINEA_MODIFICADA",
        "REFERENCIA_LINEA_ELIMINADA",
    ]
    for evento in eventos:
        assert evento.usuario == "qa"
        assert evento.material_id == mid1
        assert evento.resultado == "EXITO"
        det = evento.detalles
        assert det["modulo"] == "REFERENCIA"
        assert det["equipo_id"] == eid

    creada, modificada, eliminada = [e.detalles for e in eventos]
    assert creada["accion"] == "CREAR"
    assert creada["valores_anteriores"] is None
    assert Decimal(str(creada["valores_nuevos"]["cantidad_semanal"])) == Decimal(
        "5.000"
    )
    assert modificada["accion"] == "MODIFICAR"
    assert Decimal(
        str(modificada["valores_anteriores"]["cantidad_semanal"])
    ) == Decimal("5.000")
    assert Decimal(
        str(modificada["valores_nuevos"]["cantidad_semanal"])
    ) == Decimal("7.500")
    assert eliminada["accion"] == "ELIMINAR"
    assert Decimal(
        str(eliminada["valores_anteriores"]["cantidad_semanal"])
    ) == Decimal("7.500")
    assert eliminada["valores_nuevos"] is None


async def test_req_ref_012_peticiones_rechazadas_no_dejan_evento(
    client: AsyncClient, session: AsyncSession
) -> None:
    """REQ-REF-012: una petición rechazada (422/404/409) NO deja evento y el
    rollback de una petición mixta no deja ni línea ni evento."""
    m1 = await crear_material(client, descripcion="Mat Rech A")
    m2 = await crear_material(client, descripcion="Mat Rech B")
    equipo = await crear_equipo(client, nombre="Unidad Rech")
    eid = equipo["equipo_id"]
    mid1, mid2 = m1["id_lista"], m2["id_lista"]

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text

    rechazos: list[tuple[str, str, dict | None, int]] = [
        (
            "post",
            _ruta(eid),
            {"lineas": [{"material_id": 999999, "cantidad_semanal": 1}]},
            404,
        ),
        (
            "post",
            _ruta(eid),
            {"lineas": [{"material_id": mid1, "cantidad_semanal": 9}]},
            409,
        ),
        (
            "post",
            _ruta(eid),
            {"lineas": [{"material_id": mid2, "cantidad_semanal": 0}]},
            422,
        ),
        ("patch", _ruta(eid, mid2), {"cantidad_semanal": 3}, 404),
        ("delete", _ruta(eid, mid2), None, 404),
    ]
    for metodo, ruta, cuerpo, esperado in rechazos:
        resp = await client.request(metodo, ruta, json=cuerpo)
        assert resp.status_code == esperado, resp.text

    # Rollback de una petición mixta: nada creado, nada auditado.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid2, "cantidad_semanal": 1},
                {"material_id": 999999, "cantidad_semanal": 1},
            ]
        },
    )
    assert resp.status_code == 404, resp.text

    async with session.begin():
        n = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e"
                ),
                {"e": eid},
            )
        ).scalar_one()
    assert n == 1
    assert await _contar_eventos_referencia(session) == 1


# ---------------------------------------------------------------- REQ-REF-015


async def test_req_ref_015_cuerpos_canonicos_y_mensajes_unidad(
    client: AsyncClient, client_factory: Any, session: AsyncSession
) -> None:
    """REQ-REF-015: validación `{detail:[…]}`, negocio
    `{error:{code,message,coordinates}}`, 403 con el cuerpo de autorización
    vigente, mensajes con «Unidad» (sin la palabra antigua) y el 201
    devuelve `ReferenciaListOut`."""
    m1 = await crear_material(client, descripcion="Mat Contrato")
    equipo = await crear_equipo(client, nombre="Unidad Contrato")
    eid = equipo["equipo_id"]
    mid1 = m1["id_lista"]

    # 201 devuelve ReferenciaListOut ({items, total} con líneas canónicas).
    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 201, resp.text
    creadas = resp.json()
    assert set(creadas) == {"items", "total"} and creadas["total"] == 1
    assert set(creadas["items"][0]) == {
        "material_id",
        "codigo",
        "descripcion",
        "u_m",
        "cantidad_semanal",
    }

    # Validación → cuerpo estándar {detail:[…]} (422 con dos formas).
    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 0}]},
    )
    assert resp.status_code == 422, resp.text
    assert set(resp.json()) == {"detail"}
    assert isinstance(resp.json()["detail"], list)

    # Negocio → {error:{code,message,coordinates}}.
    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": 999999, "cantidad_semanal": 1}]},
    )
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "MATERIAL_NO_ENCONTRADO"
    assert error["coordinates"] == [{"linea": 0, "material_id": 999999}]
    assert not _PALABRA_ANTIGUA.search(error["message"])

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid1, "cantidad_semanal": 9}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "REFERENCIA_DUPLICADA"
    assert "Unidad" in resp.json()["error"]["message"]
    assert not _PALABRA_ANTIGUA.search(resp.json()["error"]["message"])

    resp = await client.patch(_ruta(eid, mid1), json={"cantidad_semanal": 6})
    assert resp.status_code == 200, resp.text
    resp = await client.patch(_ruta(eid, 7777777), json={"cantidad_semanal": 6})
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert error["code"] == "REFERENCIA_NO_ENCONTRADA"
    assert "Unidad" in error["message"]
    assert not _PALABRA_ANTIGUA.search(error["message"])

    # 422 de negocio (línea duplicada): mismo cuerpo canónico.
    resp = await client.post(
        _ruta(eid),
        json={
            "lineas": [
                {"material_id": mid1, "cantidad_semanal": 1},
                {"material_id": mid1, "cantidad_semanal": 2},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "REFERENCIA_LINEA_DUPLICADA"

    # 404 de Unidad inexistente: mensaje con «Unidad».
    resp = await client.get("/api/v1/equipos/999999/referencia")
    assert resp.status_code == 404, resp.text
    error = resp.json()["error"]
    assert error["message"] == "Unidad no encontrada"
    assert error["coordinates"] == [{"equipo_id": 999999}]
    assert not _PALABRA_ANTIGUA.search(error["message"])

    # 403: cuerpo de autorización vigente y mensaje con «Unidad».
    async with session.begin():
        await session.execute(
            text(
                "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
                "VALUES ('ajeno', 1)"
            )
        )
    async with client_factory("ajeno") as ajeno:
        resp = await ajeno.get(_ruta(eid))
    assert resp.status_code == 403, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "actor", "required_scope"}
    assert error["code"] == "AUTHORIZATION_FAILED"
    # Mensaje canónico vigente de autorización (con la nomenclatura oficial;
    # la suite de nomenclatura lo fija exactamente en minúscula).
    assert error["message"] == "El actor no tiene acceso a esta unidad"
    assert error["actor"] == "ajeno"
    assert not _PALABRA_ANTIGUA.search(error["message"])


async def test_req_ref_015_contrato_openapi_y_formas_de_los_dto(
    client: AsyncClient,
) -> None:
    """REQ-REF-015: el OpenAPI vivo expone las cuatro operaciones y los DTO
    con nombres, tipos y límites del contrato (borrador T7): 1..50 líneas,
    `material_id` 0 < x ≤ 2147483647, `extra=forbid` y campos exactos."""
    from app.main import app

    o = app.openapi()
    base = "/api/v1/equipos/{equipo_id}/referencia"
    assert {"get", "post"} <= set(o["paths"][base])
    assert {"patch", "delete"} <= set(o["paths"][base + "/{material_id}"])

    schemas = o["components"]["schemas"]
    crear = schemas["ReferenciaCreate"]
    assert crear["additionalProperties"] is False
    assert set(crear["properties"]) == {"lineas"}
    lineas = crear["properties"]["lineas"]
    assert (lineas["minItems"], lineas["maxItems"]) == (1, 50)
    ref = lineas["items"]["$ref"].split("/")[-1]
    linea_create = schemas[ref]
    assert linea_create["additionalProperties"] is False
    assert set(linea_create["properties"]) == {
        "material_id",
        "cantidad_semanal",
    }
    assert linea_create["properties"]["material_id"]["exclusiveMinimum"] == 0
    assert linea_create["properties"]["material_id"]["maximum"] == 2147483647

    update = schemas["ReferenciaUpdate"]
    assert update["additionalProperties"] is False
    assert set(update["properties"]) == {"cantidad_semanal"}

    assert set(schemas["ReferenciaListOut"]["properties"]) == {"items", "total"}
    assert set(schemas["ReferenciaLineaOut"]["properties"]) == {
        "material_id",
        "codigo",
        "descripcion",
        "u_m",
        "cantidad_semanal",
    }


# ---------------------------------------------------------------- §6 Concurrencia


async def test_req_ref_007_concurrencia_mismo_material_201_y_409(
    client: AsyncClient, client_factory: Any, session: AsyncSession
) -> None:
    """§6/REQ-REF-007: dos altas SIMULTÁNEAS del mismo material → {201, 409}
    (la PK compuesta resuelve la carrera), una sola fila y un solo evento
    (el rollback del perdedor no deja huella)."""
    material = await crear_material(client, descripcion="Mat Carrera PK")
    equipo = await crear_equipo(client, nombre="Unidad Carrera")
    eid = equipo["equipo_id"]
    mid = material["id_lista"]
    payload = {"lineas": [{"material_id": mid, "cantidad_semanal": 5}]}

    async def intentar() -> tuple[int, dict]:
        c = client_factory("qa")
        try:
            r = await c.post(_ruta(eid), json=payload)
            return r.status_code, r.json()
        finally:
            await c.aclose()

    r1, r2 = await asyncio.gather(intentar(), intentar())
    assert sorted([r1[0], r2[0]]) == [201, 409]
    perdedor = r1 if r1[0] == 409 else r2
    assert perdedor[1]["error"]["code"] == "REFERENCIA_DUPLICADA"

    async with session.begin():
        filas = (
            await session.execute(
                text(
                    "SELECT count(*) FROM referencia_materiales "
                    "WHERE equipo_id = :e AND material_id = :m"
                ),
                {"e": eid, "m": mid},
            )
        ).scalar_one()
    assert filas == 1
    assert await _contar_eventos_referencia(session) == 1


async def test_req_ref_007_concurrencia_altas_cruzadas_sin_500(
    client: AsyncClient, client_factory: Any, session: AsyncSession
) -> None:
    """§6/P-3: dos altas concurrentes con los MISMOS materiales en distinto
    orden — la inserción por `material_id` ascendente evita interbloqueos;
    el perdedor responde 409 controlado (jamás 500) y la BD queda con las
    dos líneas exactas."""
    m_a = await crear_material(client, descripcion="Mat Cruz A")
    m_b = await crear_material(client, descripcion="Mat Cruz B")
    equipo = await crear_equipo(client, nombre="Unidad Cruzada")
    eid = equipo["equipo_id"]
    payload_ab = {
        "lineas": [
            {"material_id": m_a["id_lista"], "cantidad_semanal": 1},
            {"material_id": m_b["id_lista"], "cantidad_semanal": 2},
        ]
    }
    payload_ba = {
        "lineas": [
            {"material_id": m_b["id_lista"], "cantidad_semanal": 2},
            {"material_id": m_a["id_lista"], "cantidad_semanal": 1},
        ]
    }

    async def intentar(payload: dict) -> tuple[int, dict]:
        c = client_factory("qa")
        try:
            r = await c.post(_ruta(eid), json=payload)
            return r.status_code, r.json()
        finally:
            await c.aclose()

    r1, r2 = await asyncio.gather(intentar(payload_ab), intentar(payload_ba))
    assert sorted([r1[0], r2[0]]) == [201, 409]
    perdedor = r1 if r1[0] == 409 else r2
    assert perdedor[1]["error"]["code"] == "REFERENCIA_DUPLICADA"

    async with session.begin():
        filas = (
            await session.execute(
                text(
                    "SELECT material_id, cantidad_semanal "
                    "FROM referencia_materiales WHERE equipo_id = :e "
                    "ORDER BY material_id"
                ),
                {"e": eid},
            )
        ).all()
    assert [
        (f.material_id, Decimal(str(f.cantidad_semanal))) for f in filas
    ] == [
        (m_a["id_lista"], Decimal("1.000")),
        (m_b["id_lista"], Decimal("2.000")),
    ]
    assert await _contar_eventos_referencia(session) == 2


async def test_req_ref_015_deadlock_40p01_responde_409_nunca_500(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-REF-015/§6 (P-3): un interbloqueo residual (SQLSTATE 40P01) en el
    flush de la alta responde 409 `REFERENCIA_DUPLICADA` controlado con
    rollback completo — jamás 500 ni SQL expuesto."""
    from app.models import ReferenciaMaterial
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    material = await crear_material(client, descripcion="Mat Deadlock")
    equipo = await crear_equipo(client, nombre="Unidad Deadlock")
    eid = equipo["equipo_id"]
    mid = material["id_lista"]

    flush_original = _AsyncSession.flush

    async def flush_40p01(self: Any, objects: Any = None) -> None:
        if any(isinstance(o, ReferenciaMaterial) for o in self.new):
            orig = SimpleNamespace(sqlstate="40P01")
            raise DBAPIError("SELECT 1", {}, orig)  # type: ignore[arg-type]
        await flush_original(self, objects)

    monkeypatch.setattr(_AsyncSession, "flush", flush_40p01)

    resp = await client.post(
        _ruta(eid),
        json={"lineas": [{"material_id": mid, "cantidad_semanal": 5}]},
    )
    assert resp.status_code == 409, resp.text
    error = resp.json()["error"]
    assert set(error) == {"code", "message", "coordinates"}
    assert error["code"] == "REFERENCIA_DUPLICADA"
    assert "reintente" in error["message"].lower()

    # Rollback completo: sin fila y sin evento.
    async with session.begin():
        n = (
            await session.execute(
                text("SELECT count(*) FROM referencia_materiales")
            )
        ).scalar_one()
    assert n == 0
    assert await _contar_eventos_referencia(session) == 0
