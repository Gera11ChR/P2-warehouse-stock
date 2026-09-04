from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header
from sqlalchemy import select

from app.db import SessionLocal
from app.errors import AuthorizationError
from app.models import UserWarehouseScope

ActorHeader = Annotated[str, Header(alias="X-Actor")]


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    scoped_warehouse_ids: frozenset[str] = field(default_factory=frozenset)


async def get_current_actor(actor: ActorHeader) -> ActorContext:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(UserWarehouseScope.warehouse_id).where(
                    UserWarehouseScope.actor_id == actor
                )
            )
        ).scalars()
        return ActorContext(
            actor_id=actor, scoped_warehouse_ids=frozenset(rows)
        )


def assert_scope(actor_ctx: ActorContext, required: set[str]) -> None:
    missing = required - set(actor_ctx.scoped_warehouse_ids)
    if missing:
        raise AuthorizationError(
            "Actor lacks required warehouse scope",
            actor=actor_ctx.actor_id,
            required_scope=sorted(missing),
        )


def assert_authenticated(actor_ctx: ActorContext) -> None:
    if not actor_ctx.scoped_warehouse_ids:
        raise AuthorizationError(
            "Actor sin alcance de almacén asignado",
            actor=actor_ctx.actor_id,
        )
