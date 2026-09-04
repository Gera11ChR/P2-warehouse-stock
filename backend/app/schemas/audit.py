from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    log_id: int
    action: str
    actor: str
    details: dict | None
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
