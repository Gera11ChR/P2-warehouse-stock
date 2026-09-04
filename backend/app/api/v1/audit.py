from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditLog
from app.schemas.audit import AuditLogListOut, AuditLogOut
from app.security import ActorContext, get_current_actor

router = APIRouter(prefix="/audit", tags=["audit"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=AuditLogListOut)
async def list_audit(
    session: SessionDep,
    _actor: ActorDep,
    limit: int = Query(default=200, ge=1, le=1000),
) -> AuditLogListOut:
    rows = (
        (
            await session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return AuditLogListOut.model_validate(
        {
            "items": [
                AuditLogOut.model_validate(
                    {
                        "log_id": row.log_id,
                        "action": row.action,
                        "actor": row.actor,
                        "details": row.details,
                        "created_at": row.created_at,
                    }
                )
                for row in rows
            ]
        }
    )
