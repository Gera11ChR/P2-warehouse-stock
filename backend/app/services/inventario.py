"""Lecturas del inventario central (Inventario General) — SOLO LECTURA
(Invariantes 2 y 5).

Ámbito de este módulo: el maestro de secciones (`secciones`) y el stock por
sección (`inventario_almacen`, JOIN al catálogo activo con filtro estricto
`is_active` — REQ-API-001, cero fantasmas). Cero escrituras y cero
aritmética de stock.

Nota histórica: este módulo se llamaba `sparse_inventory` y era la puerta de
lectura del Modelo Sparse. Ese modelo y la vista
`vw_inventario_equipo_completo` quedaron deprecados con la migración 0012
(REQ-DOMAIN-001/002): el inventario autónomo de equipos se lee directamente
de `inventario_equipos` vía `api/v1/equipos.py`, y el de Fibra Óptica de
`inventario_fibra` vía `api/v1/fibra.py`. Este módulo conserva únicamente
las lecturas del inventario central.
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogoMaterial, InventarioAlmacen, Seccion
from app.schemas.inventario import SeccionOut, SeccionStockOut


async def listar_secciones(session: AsyncSession) -> list[SeccionOut]:
    stmt = select(Seccion).where(Seccion.is_active == True).order_by(  # noqa: E712
        Seccion.almacen_id.asc()
    )
    secciones = (await session.execute(stmt)).scalars().all()
    return [SeccionOut.model_validate(s) for s in secciones]


async def listar_secciones_transferibles(
    session: AsyncSession,
) -> list[dict]:
    """Secciones válidas como origen/destino de movimientos TEAMS/DEVOL
    (0014, enrutamiento aditivo FO): las secciones GENERAL activas MÁS los
    manejadores de ruteo FO_PAQUETE/FO_EN_USO (transferibles aunque
    is_active=FALSE, pues su stock vive en inventario_fibra). Las secciones
    GENERAL inactivas quedan excluidas. NO altera GET /inventario/secciones
    (contrato existente: solo GENERAL activa)."""
    stmt = (
        select(Seccion)
        .where(
            or_(
                Seccion.is_active == True,  # noqa: E712
                Seccion.tipo.in_(("FO_PAQUETE", "FO_EN_USO")),
            )
        )
        .order_by(Seccion.almacen_id.asc())
    )
    secciones = (await session.execute(stmt)).scalars().all()
    return [
        {
            "almacen_id": s.almacen_id,
            "nombre": s.nombre,
            "tipo": s.tipo,
            "transferible": True,
        }
        for s in secciones
    ]


async def obtener_seccion(
    session: AsyncSession, almacen_id: int
) -> SeccionOut | None:
    seccion = await session.get(Seccion, almacen_id)
    if seccion is None or not seccion.is_active:
        return None
    return SeccionOut.model_validate(seccion)


async def stock_seccion(
    session: AsyncSession, almacen_id: int
) -> list[SeccionStockOut]:
    stmt = (
        select(
            InventarioAlmacen.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            CatalogoMaterial.u_m,
            CatalogoMaterial.stock_minimo,
            InventarioAlmacen.stock_actual,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == InventarioAlmacen.material_id,
        )
        .where(
            InventarioAlmacen.almacen_id == almacen_id,
            # REQ-API-001 (Task 3.1): cero fantasmas también en stock por
            # sección — los materiales desactivados se omiten del payload.
            CatalogoMaterial.is_active == True,  # noqa: E712
        )
        .order_by(InventarioAlmacen.material_id.asc())
    )
    filas = (await session.execute(stmt)).all()
    return [
        SeccionStockOut(
            material_id=f.material_id,
            codigo=f.codigo,
            descripcion=f.descripcion,
            u_m=f.u_m,
            stock_minimo=f.stock_minimo,
            stock_actual=f.stock_actual,
            alerta_stock=(
                f.stock_actual <= f.stock_minimo
                if f.stock_minimo is not None
                else False
            ),
        )
        for f in filas
    ]
