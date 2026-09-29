"""Gestión administrativa del catálogo operativo — REQ-CATALOG-001/002/003.

Renombrado y eliminación lógica de Categorías y Unidades de Medida
(solo administradores, SEC-001), auditoría inmutable por triggers
(tg_auditar_categoria / tg_auditar_um con `app.actor`) y preservación
histórica de los materiales que referencian entradas eliminadas.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditoriaEvento
from tests.helpers.fabrica import crear_material


async def _categoria_id_via_material(
    client: AsyncClient, nombre: str
) -> int:
    """Crea una categoría incidental vía `nueva_categoria` y devuelve su id."""
    material = await crear_material(
        client, descripcion=f"Portador {nombre}", nueva_categoria=nombre
    )
    return material["categoria_id"]


async def _um_id(client: AsyncClient, nombre: str) -> int:
    resp = await client.get("/api/v1/catalogo/um")
    assert resp.status_code == 200, resp.text
    return next(u["id"] for u in resp.json() if u["nombre"] == nombre)


async def _nombres_categorias(client: AsyncClient) -> set[str]:
    resp = await client.get("/api/v1/catalogo/categorias")
    assert resp.status_code == 200, resp.text
    return {c["nombre"] for c in resp.json()}


@pytest.mark.critical
async def test_REQ_CATALOG_001_003_renombrar_categoria_200_y_auditoria(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """REQ-CATALOG-001, REQ-CATALOG-003: el administrador renombra una categoría (200),
    el listado refleja el nuevo nombre y el trigger audita
    CATEGORIA_MODIFICADA con actor `admin-qa` y contexto anterior/nuevo."""
    cat_id = await _categoria_id_via_material(client, "Cat Original")

    resp = await client_admin.put(
        f"/api/v1/catalogo/categorias/{cat_id}",
        json={"nombre": "Cat Renombrada"},
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Cat Renombrada"

    nombres = await _nombres_categorias(client)
    assert "Cat Renombrada" in nombres
    assert "Cat Original" not in nombres

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "CATEGORIA_MODIFICADA"
            )
        )
    ).scalars().one()
    assert evento.usuario == "admin-qa"
    detalles = evento.detalles or {}
    assert detalles["categoria_id"] == cat_id
    assert detalles["nombre_anterior"] == "Cat Original"
    assert detalles["nombre_nuevo"] == "Cat Renombrada"


async def test_REQ_CATALOG_001_renombrar_categoria_duplicada_409(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-CATALOG-001: renombrar hacia un nombre de categoría existente
    viola la unicidad y clasifica 409."""
    cat_a = await _categoria_id_via_material(client, "Cat Duplicada A")
    cat_b = await _categoria_id_via_material(client, "Cat Duplicada B")

    resp = await client_admin.put(
        f"/api/v1/catalogo/categorias/{cat_b}",
        json={"nombre": "Cat Duplicada A"},
    )
    assert resp.status_code == 409

    nombres = await _nombres_categorias(client)
    assert "Cat Duplicada B" in nombres


@pytest.mark.critical
async def test_REQ_CATALOG_002_003_eliminar_categoria_204_soft_y_historico(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """REQ-CATALOG-002, REQ-CATALOG-003: eliminación lógica (204), la categoría sale del
    selector activo, se audita CATEGORIA_ELIMINADA y los materiales
    históricos conservan legible el nombre de la categoría."""
    material = await crear_material(
        client,
        descripcion="Material histórico",
        nueva_categoria="Cat Histórica",
    )
    cat_id = material["categoria_id"]

    resp = await client_admin.delete(f"/api/v1/catalogo/categorias/{cat_id}")
    assert resp.status_code == 204

    nombres = await _nombres_categorias(client)
    assert "Cat Histórica" not in nombres

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "CATEGORIA_ELIMINADA"
            )
        )
    ).scalars().one()
    assert evento.usuario == "admin-qa"
    assert (evento.detalles or {})["categoria_id"] == cat_id

    resp = await client.get(f"/api/v1/catalogo/{material['id_lista']}")
    assert resp.status_code == 200
    assert resp.json()["categoria"] == "Cat Histórica"
    assert resp.json()["categoria_id"] == cat_id


async def test_SEC_001_categoria_operaciones_no_admin_403(
    client: AsyncClient,
) -> None:
    """SEC-001: un actor regular recibe 403 en alta, renombrado y
    eliminación de categorías (operaciones solo administradores)."""
    cat_id = await _categoria_id_via_material(client, "Cat Prohibida")

    resp = await client.put(
        f"/api/v1/catalogo/categorias/{cat_id}", json={"nombre": "X"}
    )
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v1/catalogo/categorias/{cat_id}")
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/catalogo/categorias", json={"nombre": "Nueva no admin"}
    )
    assert resp.status_code == 403


async def test_REQ_CATALOG_001_um_semilla_10_y_alta_201_duplicada_409(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-CATALOG-001: el maestro activo de U.M. expone las 10 unidades
    sembradas; el administrador puede dar de alta nuevas y el duplicado
    clasifica 409."""
    resp = await client.get("/api/v1/catalogo/um")
    assert resp.status_code == 200
    assert len(resp.json()) == 10

    resp = await client_admin.post(
        "/api/v1/catalogo/um", json={"nombre": "KIT"}
    )
    assert resp.status_code == 201
    assert resp.json()["nombre"] == "KIT"

    resp = await client_admin.post(
        "/api/v1/catalogo/um", json={"nombre": "KIT"}
    )
    assert resp.status_code == 409


@pytest.mark.critical
async def test_REQ_CATALOG_001_003_renombrar_um_200_y_auditoria(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """REQ-CATALOG-001, REQ-CATALOG-003: renombrado administrativo de U.M. (200) con
    evento inmutable UM_MODIFICADA atribuido a `admin-qa`."""
    um_id = await _um_id(client, "ROLLO")

    resp = await client_admin.put(
        f"/api/v1/catalogo/um/{um_id}", json={"nombre": "ROLLO INDUSTRIAL"}
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "ROLLO INDUSTRIAL"

    resp = await client.get("/api/v1/catalogo/um")
    nombres = {u["nombre"] for u in resp.json()}
    assert "ROLLO INDUSTRIAL" in nombres
    assert "ROLLO" not in nombres

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "UM_MODIFICADA"
            )
        )
    ).scalars().one()
    assert evento.usuario == "admin-qa"
    detalles = evento.detalles or {}
    assert detalles["um_id"] == um_id
    assert detalles["nombre_anterior"] == "ROLLO"
    assert detalles["nombre_nuevo"] == "ROLLO INDUSTRIAL"


async def test_REQ_CATALOG_002_003_eliminar_um_204_y_auditoria(
    client: AsyncClient, client_admin: AsyncClient, session
) -> None:
    """REQ-CATALOG-002, REQ-CATALOG-003: eliminación lógica de U.M. (204), sale del
    selector activo y se audita UM_ELIMINADA con el actor."""
    um_id = await _um_id(client, "UNIDAD")

    resp = await client_admin.delete(f"/api/v1/catalogo/um/{um_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/v1/catalogo/um")
    nombres = {u["nombre"] for u in resp.json()}
    assert "UNIDAD" not in nombres

    evento = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "UM_ELIMINADA"
            )
        )
    ).scalars().one()
    assert evento.usuario == "admin-qa"
    assert (evento.detalles or {})["um_id"] == um_id


async def test_SEC_001_um_no_admin_403(client: AsyncClient) -> None:
    """SEC-001: alta, renombrado y eliminación de U.M. exigen rol
    administrador (403 para el actor regular)."""
    resp = await client.post("/api/v1/catalogo/um", json={"nombre": "KIT2"})
    assert resp.status_code == 403

    resp = await client.put(
        "/api/v1/catalogo/um/1", json={"nombre": "RENOMBRADA"}
    )
    assert resp.status_code == 403

    resp = await client.delete("/api/v1/catalogo/um/1")
    assert resp.status_code == 403


async def test_material_um_inactiva_422_y_valida_201(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-CATALOG-002, REQ-CATALOG-003 (validez U.M.): regresión de `_validar_um` — la fuente autoritativa del
    selector es la tabla `ums` — una unidad suprimida lógicamente se
    rechaza en el alta de material (422) y una activa sigue pasando (201)."""
    um_id = await _um_id(client, "LT")
    resp = await client_admin.delete(f"/api/v1/catalogo/um/{um_id}")
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/catalogo",
        json={"descripcion": "U.M. inactiva", "u_m": "LT"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/catalogo",
        json={"descripcion": "U.M. válida", "u_m": "PZ"},
    )
    assert resp.status_code == 201


async def test_REQ_CATALOG_002_eliminar_categoria_inexistente_404(
    client_admin: AsyncClient,
) -> None:
    """REQ-CATALOG-002: eliminar una categoría inexistente clasifica 404."""
    resp = await client_admin.delete("/api/v1/catalogo/categorias/99999")
    assert resp.status_code == 404


async def test_fix_nis_um_dinamica_aceptada_en_alta(
    client: AsyncClient, client_admin: AsyncClient
) -> None:
    """REQ-UM-001/002 (fix NIS): una U.M. creada dinámicamente por el
    administrador — fuera del Enum estático SUPPORTED_UNITS — es aceptada
    en el alta de material (201), sin error 422/400. La validación
    autoritativa es dinámica contra la tabla `ums`."""
    resp = await client_admin.post(
        "/api/v1/catalogo/um", json={"nombre": "METRO CUADRADO"}
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/catalogo",
        json={"descripcion": "Material U.M. dinámica", "u_m": "METRO CUADRADO"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["u_m"] == "METRO CUADRADO"


async def test_fix_nis_carga_inicial_destino_fo(client: AsyncClient, session) -> None:
    """REQ-CARGA-002/003 (fix NIS): la SECCIÓN DESTINO de la Carga Inicial
    admite las raíces FO — el stock inicial se rutea a inventario_fibra
    (PAQUETE/EN_USO) vía fn_cargar_stock_inicial_fibra, con auditoría
    inmutable STOCK_INICIAL_FO."""
    material_paquete = await crear_material(
        client,
        descripcion="Material FO Paquete inicial",
        stock_inicial=50,
        seccion_id=2,
    )
    material_en_uso = await crear_material(
        client,
        descripcion="Material FO En Uso inicial",
        stock_inicial=30,
        seccion_id=3,
    )

    resp = await client.get("/api/v1/fibra/PAQUETE")
    assert resp.status_code == 200, resp.text
    filas = {f["material_id"]: f for f in resp.json()}
    assert filas[material_paquete["id_lista"]]["stock_actual"] == 50

    resp = await client.get("/api/v1/fibra/EN_USO")
    assert resp.status_code == 200, resp.text
    filas = {f["material_id"]: f for f in resp.json()}
    assert filas[material_en_uso["id_lista"]]["stock_actual"] == 30

    # REQ-CARGA-003: el camino ruteado de crear_material emite la auditoría
    # STOCK_INICIAL_FO (una por raíz FO) con el módulo en `detalles`.
    eventos = (
        await session.execute(
            select(AuditoriaEvento).where(
                AuditoriaEvento.tipo_accion == "STOCK_INICIAL_FO"
            )
        )
    ).scalars().all()
    por_material = {e.material_id: e for e in eventos}
    assert material_paquete["id_lista"] in por_material
    assert (
        por_material[material_paquete["id_lista"]].detalles.get("modulo")
        == "PAQUETE"
    )
    assert material_en_uso["id_lista"] in por_material
    assert (
        por_material[material_en_uso["id_lista"]].detalles.get("modulo")
        == "EN_USO"
    )
