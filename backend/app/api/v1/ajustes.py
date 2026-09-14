from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.ajuste import (
    AjusteOut,
    AjusteStockAlmacenRequest,
    CargaInicialRequest,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import transaccional

router = APIRouter(prefix="/ajustes", tags=["ajustes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.post("/carga-inicial", response_model=AjusteOut)
async def carga_inicial(
    payload: CargaInicialRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> AjusteOut:
    """Alta única e idempotente de inventario vía fn_cargar_stock_inicial.

    Rechaza si el material ya posee registro activo en la sección."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.cargar_stock_inicial(
            session,
            almacen_id=payload.almacen_id,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            motivo=payload.motivo,
        )
    return AjusteOut(
        almacen_id=payload.almacen_id, material_id=payload.material_id
    )


@router.post("/stock-almacen", response_model=AjusteOut)
async def ajuste_almacen(
    payload: AjusteStockAlmacenRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> AjusteOut:
    """Ajuste administrativo vía fn_ajustar_stock_almacen: diferencial,
    validación de no-negatividad y auditoría calculados en PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.ajustar_stock_almacen(
            session,
            almacen_id=payload.almacen_id,
            material_id=payload.material_id,
            nuevo_stock=payload.nuevo_stock,
            motivo=payload.motivo,
        )
    return AjusteOut(
        almacen_id=payload.almacen_id, material_id=payload.material_id
    )
