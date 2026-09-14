"""Fábricas de dominio — Arrange compacto para todos los módulos de prueba.

Cada fábrica usa exclusivamente la API pública HTTP (cliente httpx ASGI),
de modo que todo fixture transita por el mismo camino de producción:
validación Pydantic -> routers -> services -> Stored Functions.
"""

from httpx import AsyncClient

ALMACEN_GENERAL = 1
ALMACEN_PAQUETE = 2
ALMACEN_EN_USO = 3


async def crear_material(
    client: AsyncClient,
    *,
    descripcion: str = "Material QA",
    codigo: str | None = None,
    u_m: str = "PZ",
    stock_minimo: int | None = None,
    categoria_id: int | None = None,
    nueva_categoria: str | None = None,
    stock_inicial: int | None = None,
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
    payload: dict = {"nombre": nombre}
    if integrantes is not None:
        payload["integrantes"] = integrantes
    resp = await client.post("/api/v1/equipos", json=payload)
    assert resp.status_code == expect, resp.text
    return resp.json()


async def carga_inicial(
    client: AsyncClient,
    *,
    almacen_id: int = ALMACEN_GENERAL,
    material_id: int,
    cantidad: int,
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
    cantidad: int,
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
    cantidad: int,
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
    nuevo_stock: int,
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


async def catalogo_equipo(
    client: AsyncClient, equipo_id: int
) -> dict[int, dict]:
    """Mapa {id_lista: fila} del catálogo sparse del equipo (vía API pública)."""
    resp = await client.get(f"/api/v1/inventario/equipos/{equipo_id}")
    assert resp.status_code == 200, resp.text
    return {f["id_lista"]: f for f in resp.json()}
