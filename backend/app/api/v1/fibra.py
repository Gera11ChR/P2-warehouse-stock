"""Fibra Óptica — inventarios independientes PAQUETE / EN_USO (REQ-DOMAIN-003/004/005).

Las raíces de inventario FO dejaron de ser secciones del Inventario General:
`inventario_fibra` es la fuente física autónoma (esquema estándar gobernado
por `u_m`). Toda mutación de stock se delega a las stored functions
`fn_cargar_stock_inicial_fibra` / `fn_ajustar_stock_fibra` vía
services.transaccional — CERO aritmética de stock y CERO escritura directa
en Python (Invariantes 2 y 5 del proyecto).
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import CatalogoMaterial, InventarioFibra
from app.schemas.inventario import (
    FibraAjusteRequest,
    FibraCargaInicialRequest,
    FibraModulo,
    FibraOperacionOut,
    FibraStockOut,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services import transaccional

router = APIRouter(prefix="/fibra", tags=["fibra"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("/{modulo}", response_model=list[FibraStockOut])
async def stock_fibra(
    modulo: FibraModulo, session: SessionDep, _actor: ActorDep
) -> list[FibraStockOut]:
    """Stock del inventario FO independiente con el esquema estándar
    (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK).

    Solo filas físicas de `inventario_fibra` (registros reales creados por
    la carga inicial); los materiales inactivos del catálogo se omiten
    (REQ-API-001: cero fantasmas). La métrica la gobierna `u_m`."""
    stmt = (
        select(
            InventarioFibra.modulo,
            InventarioFibra.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            CatalogoMaterial.u_m,
            CatalogoMaterial.stock_minimo,
            InventarioFibra.stock_actual,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == InventarioFibra.material_id,
        )
        .where(
            InventarioFibra.modulo == modulo,
            CatalogoMaterial.is_active == True,  # noqa: E712
        )
        .order_by(InventarioFibra.material_id.asc())
    )
    filas = (await session.execute(stmt)).all()
    return [
        FibraStockOut(
            modulo=f.modulo,
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


@router.post("/carga-inicial", response_model=FibraOperacionOut)
async def carga_inicial_fibra(
    payload: FibraCargaInicialRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FibraOperacionOut:
    """Alta única e idempotente de inventario FO.

    Delega a `fn_cargar_stock_inicial_fibra`: rechaza si la fila
    (modulo, material_id) ya existe y audita 'STOCK_INICIAL_FO' en
    PostgreSQL."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.cargar_stock_inicial_fibra(
            session,
            modulo=payload.modulo,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            motivo=payload.motivo,
        )
    return FibraOperacionOut(
        modulo=payload.modulo, material_id=payload.material_id
    )


@router.post("/ajuste", response_model=FibraOperacionOut)
async def ajuste_fibra(
    payload: FibraAjusteRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FibraOperacionOut:
    """Ajuste administrativo de stock FO.

    Motivo obligatorio y no vacío (validator del schema); el diferencial,
    el bloqueo FOR UPDATE y la auditoría ('AJUSTE_INVENTARIO_FO') se
    calculan en PostgreSQL vía `fn_ajustar_stock_fibra`
    (Constitution 2.4: ledger inmutable)."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.ajustar_stock_fibra(
            session,
            modulo=payload.modulo,
            material_id=payload.material_id,
            nuevo_stock=payload.nuevo_stock,
            motivo=payload.motivo,
        )
    return FibraOperacionOut(
        modulo=payload.modulo, material_id=payload.material_id
    )
