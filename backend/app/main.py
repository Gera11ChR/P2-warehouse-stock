from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import stock_transfers
from app.errors import (
    AuthorizationError,
    BusinessRuleError,
    TransferIdempotencyConflictError,
    TransferNotFoundError,
    TransferStateConflictError,
)
from app.services.audit import record_durable_audit
from app.telemetry import current_trace_id, emit_log, new_trace_id, trace_id_var

app = FastAPI(title="P2 Inventory API", version="0.1.0")

app.include_router(stock_transfers.router, prefix="/api/v1")


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
    token = trace_id_var.set(trace_id)
    try:
        response = await call_next(request)
    finally:
        trace_id_var.reset(token)
    response.headers["X-Trace-Id"] = trace_id
    emit_log(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


@app.exception_handler(AuthorizationError)
async def authorization_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    await record_durable_audit(
        action="AUTHZ_DENIED",
        actor=exc.actor or "-",
        details={
            "path": request.url.path,
            "code": exc.code,
            "required_scope": exc.required_scope,
        },
    )
    emit_log(
        "authorization_denied",
        code=exc.code,
        actor=exc.actor,
        path=request.url.path,
    )
    return JSONResponse(status_code=403, content=exc.to_http_detail())


@app.exception_handler(BusinessRuleError)
async def business_rule_handler(request: Request, exc: BusinessRuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content=exc.to_http_detail())


@app.exception_handler(TransferIdempotencyConflictError)
async def idempotency_conflict_handler(
    request: Request, exc: TransferIdempotencyConflictError
) -> JSONResponse:
    return JSONResponse(status_code=409, content=exc.to_http_detail())


@app.exception_handler(TransferStateConflictError)
async def state_conflict_handler(
    request: Request, exc: TransferStateConflictError
) -> JSONResponse:
    return JSONResponse(status_code=409, content=exc.to_http_detail())


@app.exception_handler(TransferNotFoundError)
async def not_found_handler(
    request: Request, exc: TransferNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content=exc.to_http_detail())
