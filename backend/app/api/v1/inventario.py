from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.schemas.inventario import SeccionOut, SeccionStockOut
from app.security import ActorContext, get_current_actor
from app.services import inventario

router = APIRouter(prefix="/inventario", tags=["inventario"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/secciones", response_model=list[SeccionOut])
async def list_secciones(
    session: SessionDep, _actor: ActorDep
) -> list[SeccionOut]:
    return await inventario.listar_secciones(session)


@router.get("/secciones/{almacen_id}", response_model=list[SeccionStockOut])
async def stock_seccion(
    almacen_id: int, session: SessionDep, _actor: ActorDep
) -> list[SeccionStockOut]:
    seccion = await inventario.obtener_seccion(session, almacen_id)
    if seccion is None:
        raise BusinessRuleError(
            "Sección no encontrada",
            coordinates=[{"almacen_id": almacen_id}],
            status_code=404,
        )
    return await inventario.stock_seccion(session, almacen_id)
