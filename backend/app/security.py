from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.errors import AuthorizationError
from app.models import ActorAlmacenScope, EquipoIntegrante

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


def require_admin(actor_ctx: ActorContext) -> None:
    """Operaciones administrativas (renombrado/eliminación de categorías y
    U.M.): exige `es_admin=True`; en caso contrario 403 AUTHORIZATION_FAILED
    con mensaje canónico 'Se requiere rol administrador'."""
    if not actor_ctx.es_admin:
        raise AuthorizationError(
            "Se requiere rol administrador",
            actor=actor_ctx.actor_id,
        )


async def assert_equipo_access(
    actor_ctx: ActorContext,
    session: AsyncSession,
    equipo_id: int,
) -> None:
    """Aislamiento por equipo (flujo DESPLIEGUE y configuración local): el
    administrador pasa directo; el actor regular debe ser integrante del
    equipo (`equipos_integrantes`). En caso contrario 403."""
    if actor_ctx.es_admin:
        return
    es_integrante = (
        await session.execute(
            select(EquipoIntegrante.id)
            .where(
                EquipoIntegrante.equipo_id == equipo_id,
                EquipoIntegrante.usuario == actor_ctx.actor_id,
            )
            .limit(1)
        )
    ).scalar()
    if not es_integrante:
        raise AuthorizationError(
            "El actor no tiene acceso a este equipo",
            actor=actor_ctx.actor_id,
        )


async def equipos_visibles(
    actor_ctx: ActorContext, session: AsyncSession
) -> set[int] | None:
    """Equipos visibles para lecturas aisladas (reportes): None = todos
    (administrador); para el actor regular, los equipos donde es
    integrante (puede ser un conjunto vacío)."""
    if actor_ctx.es_admin:
        return None
    rows = (
        await session.execute(
            select(EquipoIntegrante.equipo_id).where(
                EquipoIntegrante.usuario == actor_ctx.actor_id
            )
        )
    ).scalars()
    return set(rows)
