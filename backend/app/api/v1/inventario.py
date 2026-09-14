from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.inventario import CatalogoEquipoOut, SeccionOut, SeccionStockOut
from app.security import ActorContext, get_current_actor
from app.services import sparse_inventory

router = APIRouter(prefix="/inventario", tags=["inventario"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/secciones", response_model=list[SeccionOut])
async def list_secciones(
    session: SessionDep, _actor: ActorDep
) -> list[SeccionOut]:
    return await sparse_inventory.listar_secciones(session)


@router.get("/secciones/{almacen_id}", response_model=list[SeccionStockOut])
async def stock_seccion(
    almacen_id: int, session: SessionDep, _actor: ActorDep
) -> list[SeccionStockOut]:
    seccion = await sparse_inventory.obtener_seccion(session, almacen_id)
    if seccion is None:
        raise BusinessRuleError(
            "Sección no encontrada",
            coordinates=[{"almacen_id": almacen_id}],
            status_code=404,
        )
    return await sparse_inventory.stock_seccion(session, almacen_id)


@router.get(
    "/equipos/{equipo_id}", response_model=list[CatalogoEquipoOut]
)
async def catalogo_equipo(
    equipo_id: int, session: SessionDep, _actor: ActorDep
) -> list[CatalogoEquipoOut]:
    """Sparse Model: catálogo completo del equipo vía vw_inventario_equipo_completo
    con stock 0 donde no existe registro físico en inventario_equipos."""
    filas = await sparse_inventory.catalogo_equipo(session, equipo_id)
    if not filas:
        raise BusinessRuleError(
            "Equipo no encontrado o sin catálogo activo",
            coordinates=[{"equipo_id": equipo_id}],
            status_code=404,
        )
    return filas
