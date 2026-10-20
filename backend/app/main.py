import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.api.v1 import (
    ajustes,
    auditoria,
    cancelaciones,
    catalog,
    equipos,
    fibra,
    inventario,
    movimientos,
    reportes,
    reportes_actividades,
    seguimientos,
    actividades,
)
from app.errors import (
    AuthorizationError,
    BusinessRuleError,
    MovimientoNotFoundError,
    MovimientoStateError,
)
from app.telemetry import emit_log, new_trace_id, trace_id_var

app = FastAPI(title="DMS - TELECOM Inventory API", version="1.0.0")

# Origen del dev server Vite (sin ["*"] por default-deny, Constitution 3.1;
# la autenticación viaja en X-Actor, no en cookies).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Descarga de actas XLSX: expone el nombre del adjunto para que el
    # frontend pueda leer Content-Disposition también en origen cruzado.
    expose_headers=["Content-Disposition"],
)

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(inventario.router, prefix="/api/v1")
app.include_router(movimientos.router, prefix="/api/v1")
app.include_router(cancelaciones.router, prefix="/api/v1")
app.include_router(ajustes.router, prefix="/api/v1")
app.include_router(equipos.router, prefix="/api/v1")
app.include_router(fibra.router, prefix="/api/v1")
app.include_router(auditoria.router, prefix="/api/v1")
app.include_router(seguimientos.router, prefix="/api/v1")
app.include_router(actividades.router, prefix="/api/v1")
app.include_router(reportes.router, prefix="/api/v1")
app.include_router(reportes_actividades.router, prefix="/api/v1")


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


SQLSTATE_NUMERIC_VALUE_OUT_OF_RANGE = "22003"


@app.exception_handler(DBAPIError)
async def dbapi_error_handler(
    request: Request, exc: DBAPIError
) -> JSONResponse:
    """RF-2: un identificador/valor entero fuera del rango de la columna que
    PostgreSQL rechaza en el servidor (SQLSTATE 22003, NumericValueOutOfRange)
    responde HTTP 400 con el cuerpo de error canónico, en lugar de un 500.

    El predicado es EXCLUSIVO por SQLSTATE (sin fallback por mensaje ni por
    `psycopg.DataError`). Cualquier otro error de base de datos se relanza y
    conserva su tratamiento actual. El mensaje es fijo: no interpola la
    excepción ni expone SQL, parámetros o nombres internos."""
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    if sqlstate != SQLSTATE_NUMERIC_VALUE_OUT_OF_RANGE:
        raise exc
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "NUMERIC_OUT_OF_RANGE",
                "message": "Un valor numérico de la solicitud excede el "
                "rango soportado",
                "coordinates": [],
            }
        },
    )


def _sanitizar_floats_no_finitos(valor: Any) -> Any:
    """Recorre recursivamente el payload de errores de validación y
    convierte cualquier float no finito (NaN/±Infinity) a su representación
    de cadena.

    Necesario porque `JSONResponse` serializa con `json.dumps(...,
    allow_nan=False)`: si el detalle del 422 hiciera eco del `input`
    inválido (`nan`/`inf`), la serialización lanzaría `ValueError` y el 422
    exigido por RF-8 se degradaría a 500 (Drift T5-2); lo mismo ocurre con
    cadenas que contienen sustitutos Unicode sueltos. Dicts, listas y
    tuplas se recorren recursivamente; el resto de los tipos y la
    estructura `{loc, type, msg, input}` se conservan intactos.
    """
    if isinstance(valor, float) and not math.isfinite(valor):
        return str(valor)
    if isinstance(valor, str):
        # Mismo riesgo para cadenas con sustitutos Unicode sueltos
        # (U+D800..U+DFFF): no son codificables en UTF-8 y el eco del `input`
        # degradaría el 422 a 500 al serializar la respuesta (T7/F-1,
        # REQ-ACT-013/019). Se escapan textualmente (`\\ud800`).
        try:
            valor.encode("utf-8")
        except UnicodeEncodeError:
            return valor.encode("utf-8", "backslashreplace").decode("utf-8")
        return valor
    if isinstance(valor, dict):
        return {
            clave: _sanitizar_floats_no_finitos(v) for clave, v in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_sanitizar_floats_no_finitos(v) for v in valor]
    return valor


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Espejo del handler por defecto de FastAPI (422 con `detail` como
    lista `{loc, type, msg, input}`), con los valores no finitos
    sanitizados a cadena ANTES de la serialización JSON para que entradas
    como `NaN`/`Infinity` respondan 422 con detalle bien formado, nunca
    500 (RF-8)."""
    errores = jsonable_encoder(_sanitizar_floats_no_finitos(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": errores})
