from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header
from sqlalchemy import select

from app.db import SessionLocal
from app.errors import AuthorizationError
from app.models import ActorAlmacenScope

ActorHeader = Annotated[str, Header(alias="X-Actor")]


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    scoped_almacen_ids: frozenset[int] = field(default_factory=frozenset)


async def get_current_actor(actor: ActorHeader) -> ActorContext:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(ActorAlmacenScope.almacen_id).where(
                    ActorAlmacenScope.actor_id == actor
                )
            )
        ).scalars()
        return ActorContext(
            actor_id=actor, scoped_almacen_ids=frozenset(rows)
        )


def assert_scope(actor_ctx: ActorContext, required: set[int]) -> None:
    missing = required - set(actor_ctx.scoped_almacen_ids)
    if missing:
        raise AuthorizationError(
            "Actor sin alcance sobre las secciones requeridas",
            actor=actor_ctx.actor_id,
            required_scope=[str(m) for m in sorted(missing)],
        )


def assert_authenticated(actor_ctx: ActorContext) -> None:
    if not actor_ctx.scoped_almacen_ids:
        raise AuthorizationError(
            "Actor sin alcance de sección asignado",
            actor=actor_ctx.actor_id,
        )
