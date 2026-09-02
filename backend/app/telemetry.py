import logging
import uuid
from contextvars import ContextVar

logger = logging.getLogger("p2.inventory")

trace_id_var: ContextVar[str | None] = ContextVar("p2_trace_id", default=None)


def current_trace_id() -> str | None:
    return trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    trace_id_var.set(trace_id)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def emit_log(event: str, **fields) -> None:
    logger.info(
        event,
        extra={"trace_id": current_trace_id() or "-", **fields},
    )
