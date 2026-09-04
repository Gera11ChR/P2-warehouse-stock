from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import Sku, TeamInventory
from app.schemas.team import (
    TeamInventoryCreate,
    TeamInventoryListOut,
    TeamInventoryOut,
    TeamInventoryUpdate,
)
from app.security import ActorContext, assert_authenticated, get_current_actor
from app.services.audit import make_audit

router = APIRouter(prefix="/team-inventory", tags=["team-inventory"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


async def _description(session: AsyncSession, sku_code: str) -> str | None:
    sku = await session.get(Sku, sku_code)
    return sku.description if sku is not None else None


def _to_out(record: TeamInventory, descripcion: str | None) -> TeamInventoryOut:
    return TeamInventoryOut.model_validate(
        {
            "id": record.id,
            "equipo": record.equipo,
            "usuario": record.usuario,
            "codigo": record.sku,
            "descripcion": descripcion,
            "cantidad": record.cantidad,
            "ultima_modificacion": record.ultima_modificacion,
        }
    )


async def _require_sku(session: AsyncSession, codigo: str) -> None:
    if await session.get(Sku, codigo) is None:
        raise BusinessRuleError("SKU no encontrado", coordinates=[{"codigo": codigo}])


@router.get("", response_model=TeamInventoryListOut)
async def list_team_inventory(
    session: SessionDep, _actor: ActorDep
) -> TeamInventoryListOut:
    rows = (
        (
            await session.execute(
                select(TeamInventory, Sku.description)
                .outerjoin(Sku, Sku.sku == TeamInventory.sku)
                .order_by(TeamInventory.ultima_modificacion.desc())
            )
        )
        .all()
    )
    return TeamInventoryListOut.model_validate(
        {"items": [_to_out(record, description) for record, description in rows]}
    )


@router.post("", response_model=TeamInventoryOut, status_code=201)
async def create_team_inventory(
    payload: TeamInventoryCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TeamInventoryOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        await _require_sku(session, payload.codigo)
        record = TeamInventory(
            equipo=payload.equipo,
            usuario=payload.usuario,
            sku=payload.codigo,
            cantidad=payload.cantidad,
        )
        session.add(record)
        session.add(
            make_audit(
                action="TEAM_INVENTORY_CREATE",
                actor=actor_ctx.actor_id,
                details={"codigo": payload.codigo, "equipo": payload.equipo},
            )
        )
        await session.flush()
        return _to_out(record, await _description(session, payload.codigo))


@router.patch("/{record_id}", response_model=TeamInventoryOut)
async def update_team_inventory(
    record_id: int,
    payload: TeamInventoryUpdate,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TeamInventoryOut:
    assert_authenticated(actor_ctx)
    async with session.begin():
        record = await session.get(TeamInventory, record_id)
        if record is None:
            raise BusinessRuleError(
                "Registro no encontrado", coordinates=[{"id": record_id}]
            )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        record.ultima_modificacion = datetime.now(timezone.utc)
        session.add(
            make_audit(
                action="TEAM_INVENTORY_UPDATE",
                actor=actor_ctx.actor_id,
                details={"id": record_id},
            )
        )
        await session.flush()
        return _to_out(record, await _description(session, record.sku))


@router.delete("/{record_id}", status_code=204)
async def delete_team_inventory(
    record_id: int, session: SessionDep, actor_ctx: ActorDep, response: Response
) -> Response:
    assert_authenticated(actor_ctx)
    async with session.begin():
        record = await session.get(TeamInventory, record_id)
        if record is None:
            raise BusinessRuleError(
                "Registro no encontrado", coordinates=[{"id": record_id}]
            )
        await session.delete(record)
        session.add(
            make_audit(
                action="TEAM_INVENTORY_DELETE",
                actor=actor_ctx.actor_id,
                details={"id": record_id},
            )
        )
    response.status_code = 204
    return response
