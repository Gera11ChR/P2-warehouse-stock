"""Lecturas de inventario — SOLO LECTURA (Invariantes 2 y 5).

Las secciones se leen de inventario_almacen (JOIN catálogo); el catálogo
completo por equipo se lee de la vista vw_inventario_equipo_completo, que
renderiza stock = 0 para materiales sin registro físico (Sparse Model).
Cero escrituras y cero aritmética de stock en este módulo.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CatalogoMaterial,
    InventarioAlmacen,
    Seccion,
    vw_inventario_equipo_completo,
)
from app.schemas.inventario import CatalogoEquipoOut, SeccionOut, SeccionStockOut


async def listar_secciones(session: AsyncSession) -> list[SeccionOut]:
    stmt = select(Seccion).where(Seccion.is_active == True).order_by(  # noqa: E712
        Seccion.almacen_id.asc()
    )
    secciones = (await session.execute(stmt)).scalars().all()
    return [SeccionOut.model_validate(s) for s in secciones]


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
        .where(InventarioAlmacen.almacen_id == almacen_id)
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


async def catalogo_equipo(
    session: AsyncSession, equipo_id: int
) -> list[CatalogoEquipoOut]:
    """Catálogo completo del equipo vía vista (stock 0 donde no hay fila)."""
    stmt = (
        select(vw_inventario_equipo_completo)
        .where(vw_inventario_equipo_completo.c.equipo_id == equipo_id)
        .order_by(vw_inventario_equipo_completo.c.id_lista.asc())
    )
    filas = (await session.execute(stmt)).mappings().all()
    return [CatalogoEquipoOut.model_validate(dict(f)) for f in filas]
