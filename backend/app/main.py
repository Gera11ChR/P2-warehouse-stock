from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import (
    ajustes,
    auditoria,
    cancelaciones,
    catalog,
    equipos,
    inventario,
    movimientos,
)
from app.errors import (
    AuthorizationError,
    BusinessRuleError,
    MovimientoNotFoundError,
    MovimientoStateError,
)
from app.telemetry import emit_log, new_trace_id, trace_id_var

app = FastAPI(title="DMS - TELECOM Inventory API", version="1.0.0")

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(inventario.router, prefix="/api/v1")
app.include_router(movimientos.router, prefix="/api/v1")
app.include_router(cancelaciones.router, prefix="/api/v1")
app.include_router(ajustes.router, prefix="/api/v1")
app.include_router(equipos.router, prefix="/api/v1")
app.include_router(auditoria.router, prefix="/api/v1")


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
    emit_log(
        "authorization_denied",
        code=exc.code,
        actor=exc.actor,
        path=request.url.path,
    )
    return JSONResponse(status_code=403, content=exc.to_http_detail())


@app.exception_handler(BusinessRuleError)
async def business_rule_handler(
    request: Request, exc: BusinessRuleError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content=exc.to_http_detail()
    )


@app.exception_handler(MovimientoNotFoundError)
async def movimiento_not_found_handler(
    request: Request, exc: MovimientoNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content=exc.to_http_detail())


@app.exception_handler(MovimientoStateError)
async def movimiento_state_handler(
    request: Request, exc: MovimientoStateError
) -> JSONResponse:
    return JSONResponse(status_code=409, content=exc.to_http_detail())
