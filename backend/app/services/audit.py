from app.db import SessionLocal
from app.models import AuditLog
from app.telemetry import current_trace_id


def make_audit(*, action: str, actor: str, details: dict | None = None) -> AuditLog:
    payload = dict(details or {})
    payload["trace_id"] = current_trace_id() or "-"
    return AuditLog(action=action, actor=actor, details=payload)


async def record_durable_audit(
    *, action: str, actor: str, details: dict | None = None
) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            session.add(make_audit(action=action, actor=actor, details=details))
