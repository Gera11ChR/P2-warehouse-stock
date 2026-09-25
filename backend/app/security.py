from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header
from sqlalchemy import select, text

from app.db import SessionLocal
from app.errors import AuthorizationError
from app.models import ActorAlmacenScope

ActorHeader = Annotated[str, Header(alias="X-Actor")]


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    scoped_almacen_ids: frozenset[int] = field(default_factory=frozenset)
    es_admin: bool = False


async def get_current_actor(actor: ActorHeader) -> ActorContext:
    """Resolución de identidad vía header X-Actor (mecanismo sin cambios).

    Además de los scopes de `actor_almacen_scopes`, consulta la tabla
    `administradores` (migración 0012, actor_id VARCHAR(100) PRIMARY KEY):
    si el actor figura allí, `es_admin=True` habilita acceso transversal a
    cualquier sección/equipo con cero fricción burocrática (directriz
    operativa del cliente).

    Nota de diseño: la rigidez de integridad (motivo obligatorio, stock
    no-negativo, ledger inmutable) vive en PostgreSQL —stored functions y
    CHECK constraints—, no en el RBAC de aplicación; por ello el rol
    administrador es permisivo SIN debilitar las invariantes
    constitucionales 2.1/2.4."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(ActorAlmacenScope.almacen_id).where(
                    ActorAlmacenScope.actor_id == actor
                )
            )
        ).scalars()
        es_admin = bool(
            (
                await session.execute(
                    text(
                        "SELECT EXISTS("
                        "SELECT 1 FROM administradores WHERE actor_id = :actor"
                        ")"
                    ),
                    {"actor": actor},
                )
            ).scalar()
        )
        return ActorContext(
            actor_id=actor,
            scoped_almacen_ids=frozenset(rows),
            es_admin=es_admin,
        )


def assert_scope(actor_ctx: ActorContext, required: set[int]) -> None:
    """Default-deny (Constitution 3.1) para actores regulares: valida el
    alcance por sección. El administrador (es_admin=True) recibe pase
    directo: acceso transversal a cualquier sección/equipo, cero fricción
    al gestionar inventarios o ejecutar ajustes."""
    if actor_ctx.es_admin:
        return
    missing = required - set(actor_ctx.scoped_almacen_ids)
    if missing:
        raise AuthorizationError(
            "Actor sin alcance sobre las secciones requeridas",
            actor=actor_ctx.actor_id,
            required_scope=[str(m) for m in sorted(missing)],
        )


def assert_authenticated(actor_ctx: ActorContext) -> None:
    """Identidad válida: el administrador pasa directo incluso sin filas de
    scope; el actor regular requiere al menos un alcance asignado."""
    if actor_ctx.es_admin:
        return
    if not actor_ctx.scoped_almacen_ids:
        raise AuthorizationError(
            "Actor sin alcance de sección asignado",
            actor=actor_ctx.actor_id,
        )
