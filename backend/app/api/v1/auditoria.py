from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditoriaEvento
from app.schemas.auditoria import AuditoriaListOut, AuditoriaOut
from app.security import ActorContext, get_current_actor

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=AuditoriaListOut)
async def list_eventos(
    session: SessionDep,
    _actor: ActorDep,
    material_id: int | None = None,
    tipo_accion: str | None = None,
    usuario: str | None = None,
    limit: int = 100,
) -> AuditoriaListOut:
    """Ledger inmutable append-only: solo lectura, sin endpoints de mutación."""
    stmt = select(AuditoriaEvento)
    if material_id is not None:
        stmt = stmt.where(AuditoriaEvento.material_id == material_id)
    if tipo_accion:
        stmt = stmt.where(AuditoriaEvento.tipo_accion == tipo_accion)
    if usuario:
        stmt = stmt.where(AuditoriaEvento.usuario == usuario)
    stmt = stmt.order_by(AuditoriaEvento.id.desc()).limit(min(limit, 500))
    eventos = (await session.execute(stmt)).scalars().all()
    return AuditoriaListOut(
        eventos=[AuditoriaOut.model_validate(e) for e in eventos]
    )
