# FASE 5 — Backend Verification & Contract Freeze (Sign-off)

**Change:** `2026-09-28-equipos-despliegue-management`
**Fecha:** 2026-09-28
**Estado:** CONTRATO CONGELADO — autoridad para el desarrollo de Frontend (FASE 6+)

---

## 1. Verificación de cadena (Database → Stored Functions → SQLAlchemy → Pydantic → FastAPI → OpenAPI)

| Capa | Veredicto |
| ---- | --------- |
| Database (migración 0014) | PASS — ums, equipo_material_config, despliegues, despliegue_items; CHECKs, FKs RESTRICT, índice único parcial |
| Stored Functions | PASS — fn_crear_despliegue / fn_cerrar_despliegue; routing FO aditivo en fn_procesar/cancelar_movimiento; 100% aritmética de stock en PostgreSQL |
| SQLAlchemy | PASS — modelos espejo del DDL; `cantidad_consumida` Computed persisted |
| Pydantic | PASS — `extra="forbid"` en todas las entradas; validadores de cantidades y duplicados |
| FastAPI | PASS — routers delegan solo a services.transaccional; `session.begin()` atómico; aislamiento por equipo |
| OpenAPI | PASS — 27 paths generados; request/response shapes verificados |

## 2. Suite

- `pytest tests/ -q` → **192 passed** (130 preexistentes + 62 nuevos mapeados a EARS)
- Cobertura EARS: 18/18 con referencia explícita de test (incl. REQ-VIEW-001)

## 3. Contrato congelado (consumo exclusivo del Frontend)

| Endpoint | Método | Request | Response |
| -------- | ------ | ------- | -------- |
| `/api/v1/equipos/{equipo_id}/despliegues` | POST | `{observaciones?, items[{material_id>0, cantidad_tomada>0}]}` (sin duplicados) | 201 `DespliegueOut`; 400/403/404/409/422 |
| `/api/v1/equipos/{equipo_id}/despliegues` | GET | — | `{despliegues: [DespliegueOut]}` |
| `/api/v1/equipos/{equipo_id}/despliegues/{despliegue_id}` | GET | — | `DespliegueOut`; 404 |
| `/api/v1/equipos/{equipo_id}/despliegues/{despliegue_id}/cerrar` | POST | `{sobrantes[{material_id, cantidad_sobrante≥0}], observaciones_cierre?}` (líneas omitidas = sobrante 0) | 200 `DespliegueOut`; 400/403/404/409 |
| `/api/v1/equipos/{equipo_id}/inventario` | GET | — (vista segura REQ-VIEW-001, integrante/admin) | `[InventarioEquipoOut]` con efectivos COALESCE |
| `/api/v1/equipos/{equipo_id}/inventario/{material_id}` | PATCH | `{stock_minimo_local≥0?, categoria_local_id>0?, um_local_id>0?}` (≥1 campo; `stock_actual`/`codigo`/`descripcion` → 422) | 200 `EquipoConfigLocalOut`; 403/404/422 |
| `/api/v1/catalogo/categorias/{categoria_id}` | PUT / DELETE | `{nombre}` / — | 200 / 204; admin-only; 409 duplicado |
| `/api/v1/catalogo/um/{um_id}` | PUT / DELETE | `{nombre}` / — | 200 / 204; admin-only; 409 duplicado |
| `/api/v1/catalogo/um` | GET / POST | `{nombre}` (POST admin-only) | lista activa / 201 |
| `/api/v1/reportes/despliegues` | GET | `?equipo_id&desde&hasta&format=json|csv` | JSON o `text/csv` sanitizado (aislamiento por equipo) |
| `/api/v1/inventario/secciones/transferibles` | GET | — | GENERAL activas + handles FO (transferible=true) |
| `/api/v1/movimientos` | POST | TEAMS/DEVOL con secciones GENERAL o FO (scope de sección + membresía de equipo) | 201 borrador |

**DTOs clave:** `DespliegueOut {id, equipo_id, fecha, observaciones, usuario, estado('ABIERTA'|'CERRADA'), created_at, updated_at, closed_at?, items[{id, material_id, cantidad_tomada, cantidad_sobrante?, cantidad_consumida?}]}`; `InventarioEquipoOut` extendido con `stock_minimo_local/categoria_local_id/um_local_id/stock_minimo_efectivo/categoria_efectiva/um_efectivo` (alerta contra mínimo efectivo).

**Prohibiciones del Frontend (flujo FASE 7):** cero cálculo autoritativo de stock, cero persistencia directa de inventario, cero bypass del contrato, cero reproducción de lógica transaccional PostgreSQL.

## 4. Desviaciones documentadas (heredan a FASE 10)

1. `MOVIMIENTO_CANCELADO` atribuido a `CURRENT_USER` (comportamiento preexistente; flujos nuevos atribuyen X-Actor vía `app.actor`).
2. MFA no cableado para operaciones privilegiadas (SEC-014, Constitution 3.3) — desviación registrada.
3. `operationId` OpenAPI auto-generados por FastAPI (los declarados en openspec.yaml son referencia semántica).

## 5. Aprobaciones

- @arq-reviewer: APPROVE FREEZE
- @auditor: APPROVED (contract freeze)
- @sec-ops (FASE 3): postura SEC-001..012 PASS; desviaciones V4/SEC-014 documentadas
- Suite: 192/192
