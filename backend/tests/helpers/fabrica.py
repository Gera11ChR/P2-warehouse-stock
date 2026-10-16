"""Fábricas de dominio — Arrange compacto para todos los módulos de prueba.

Cada fábrica usa exclusivamente la API pública HTTP (cliente httpx ASGI),
de modo que todo fixture transita por el mismo camino de producción:
validación Pydantic -> routers -> services -> Stored Functions.

Cambio 2026-10-fo-unificado-valor-unitario (RF-1/RF-6): el Inventario FO
es ÚNICO por material (sin `modulo`) y las cantidades son decimales
(hasta 3 dp); los helpers FO dejaron de recibir `modulo`.
"""

from httpx import AsyncClient, Response

# Números serializados a JSON (la API los recibe como literales JSON; los
# Decimal de la respuesta se comparan por valor, no por tipo Python).
Cantidad = int | float

ALMACEN_GENERAL = 1
# La sección viva de ruteo FO es 'FO' (ver `seccion_fo`).


async def crear_material(
    client: AsyncClient,
    *,
    descripcion: str = "Material QA",
    codigo: str | None = None,
    u_m: str = "PZ",
    stock_minimo: int | None = None,
    categoria_id: int | None = None,
    nueva_categoria: str | None = None,
    stock_inicial: Cantidad | None = None,
    seccion_id: int | None = None,
    expect: int = 201,
) -> dict:
    payload: dict = {
        "descripcion": descripcion,
        "u_m": u_m,
    }
    if codigo is not None:
        payload["codigo"] = codigo
    if stock_minimo is not None:
        payload["stock_minimo"] = stock_minimo
    if categoria_id is not None:
        payload["categoria_id"] = categoria_id
    if nueva_categoria is not None:
        payload["nueva_categoria"] = nueva_categoria
    if stock_inicial is not None:
        payload["stock_inicial"] = stock_inicial
    if seccion_id is not None:
        payload["seccion_id"] = seccion_id
    resp = await client.post("/api/v1/catalogo", json=payload)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def crear_equipo(
    client: AsyncClient,
    *,
    nombre: str = "Equipo QA",
    integrantes: list[str] | None = None,
    expect: int = 201,
) -> dict:
    """Crea una unidad por API pública. Por defecto incluye al actor `qa`
    como integrante: los flujos con aislamiento por equipo (0014, SEC-003 /
    V1/V3) exigen que el actor operador sea integrante de la unidad."""
    payload: dict = {"nombre": nombre}
    if integrantes is None:
        integrantes = ["qa"]
    payload["integrantes"] = integrantes
    resp = await client.post("/api/v1/equipos", json=payload)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def carga_inicial(
    client: AsyncClient,
    *,
    almacen_id: int = ALMACEN_GENERAL,
    material_id: int,
    cantidad: Cantidad,
    expect: int = 200,
) -> dict:
    resp = await client.post(
        "/api/v1/ajustes/carga-inicial",
        json={
            "almacen_id": almacen_id,
            "material_id": material_id,
            "cantidad": cantidad,
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def borrador_teams(
    client: AsyncClient,
    *,
    almacen_id: int,
    equipo_id: int,
    material_id: int,
    cantidad: Cantidad,
    observaciones: str | None = None,
    expect: int = 201,
) -> dict:
    payload: dict = {
        "tipo_movimiento": "TEAMS",
        "origen_almacen_id": almacen_id,
        "destino_equipo_id": equipo_id,
        "detalle": [{"material_id": material_id, "cantidad": cantidad}],
    }
    if observaciones is not None:
        payload["observaciones"] = observaciones
    resp = await client.post("/api/v1/movimientos", json=payload)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def borrador_devol(
    client: AsyncClient,
    *,
    equipo_id: int,
    almacen_id: int,
    material_id: int,
    cantidad: Cantidad,
    expect: int = 201,
) -> dict:
    resp = await client.post(
        "/api/v1/movimientos",
        json={
            "tipo_movimiento": "DEVOL",
            "origen_equipo_id": equipo_id,
            "destino_almacen_id": almacen_id,
            "detalle": [{"material_id": material_id, "cantidad": cantidad}],
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def procesar(
    client: AsyncClient, movimiento_id: int, expect: int = 200
) -> dict:
    resp = await client.post(
        "/api/v1/movimientos/procesar",
        json={"movimiento_id": movimiento_id},
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def cancelar(
    client: AsyncClient,
    movimiento_id: int,
    *,
    motivo: str | None = None,
    expect: int = 200,
) -> dict:
    resp = await client.post(
        f"/api/v1/movimientos/{movimiento_id}/cancelar",
        json={"motivo": motivo} if motivo is not None else {},
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def ajustar_stock(
    client: AsyncClient,
    *,
    almacen_id: int,
    material_id: int,
    nuevo_stock: Cantidad,
    motivo: str = "Ajuste QA",
    expect: int = 200,
) -> dict:
    resp = await client.post(
        "/api/v1/ajustes/stock-almacen",
        json={
            "almacen_id": almacen_id,
            "material_id": material_id,
            "nuevo_stock": nuevo_stock,
            "motivo": motivo,
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def stock_seccion(
    client: AsyncClient, almacen_id: int
) -> dict[int, int]:
    """Mapa {material_id: stock_actual} de una sección (vía API pública)."""
    resp = await client.get(f"/api/v1/inventario/secciones/{almacen_id}")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f["stock_actual"] for f in resp.json()}


async def inventario_equipo(
    client: AsyncClient, equipo_id: int
) -> dict[int, dict]:
    """Mapa {material_id: fila} del inventario AUTÓNOMO de la unidad
    (GET /api/v1/equipos/{id}/inventario, REQ-DOMAIN-001/002).

    Solo filas físicas de `inventario_equipos` con stock real originado en
    movimientos TEAMS/DEVOL auditados: cero filas fantasma (stock 0) y cero
    materiales inactivos. Una unidad nueva devuelve [] (200)."""
    resp = await client.get(f"/api/v1/equipos/{equipo_id}/inventario")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f for f in resp.json()}


async def inventario_fo(client: AsyncClient) -> dict[int, dict]:
    """Mapa {material_id: fila} del Inventario FO unificado
    (GET /api/v1/fibra, RF-1)."""
    resp = await client.get("/api/v1/fibra")
    assert resp.status_code == 200, resp.text
    return {f["material_id"]: f for f in resp.json()}


async def seccion_fo(client: AsyncClient) -> dict:
    """Sección de ruteo única `FO` (RF-1/RF-9) vía el endpoint
    `/inventario/secciones/transferibles` (id dinámico: la tabla secciones
    no se trunca entre tests)."""
    resp = await client.get("/api/v1/inventario/secciones/transferibles")
    assert resp.status_code == 200, resp.text
    fo = [s for s in resp.json() if s["tipo"] == "FO"]
    assert len(fo) == 1, resp.text
    return fo[0]


async def fibra_carga_inicial(
    client: AsyncClient,
    *,
    material_id: int,
    cantidad: Cantidad,
    motivo: str | None = "Carga inicial FO QA",
    expect: int = 200,
) -> dict:
    """Alta única de inventario en el Inventario FO unificado
    (fn_cargar_stock_inicial_fibra, RF-1): SIN `modulo`."""
    payload: dict = {
        "material_id": material_id,
        "cantidad": cantidad,
    }
    if motivo is not None:
        payload["motivo"] = motivo
    resp = await client.post("/api/v1/fibra/carga-inicial", json=payload)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def fibra_ajuste(
    client: AsyncClient,
    *,
    material_id: int,
    nuevo_stock: Cantidad,
    motivo: str = "Ajuste FO QA",
    expect: int = 200,
) -> dict:
    """Ajuste administrativo del Inventario FO unificado
    (fn_ajustar_stock_fibra, RF-1): SIN `modulo`."""
    resp = await client.post(
        "/api/v1/fibra/ajuste",
        json={
            "material_id": material_id,
            "nuevo_stock": nuevo_stock,
            "motivo": motivo,
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


async def patch_material(
    client: AsyncClient,
    id_lista: int,
    **campos,
) -> Response:
    """PATCH /api/v1/catalogo/{id_lista} con campos arbitrarios.

    Devuelve la respuesta cruda httpx (sin assert de status) para que cada
    test decida el código esperado y valide tanto status como payload."""
    resp = await client.patch(f"/api/v1/catalogo/{id_lista}", json=campos)
    return resp
