# Implementation Tasks: 2026-09-29-fo-delete-fix

> RESTRICCIÓN DE EJECUCIÓN: cero subagentes en paralelo (evitar deadlocks
> en PostgreSQL). Todas las fases se ejecutan de forma estrictamente
> secuencial en la sesión principal.

## Fase 0: Reproducción y diagnóstico
- [x] **0.1 Reproducir el 500**: verificado sobre la BD real `p2`.
  **CAUSA RAÍZ**: la base de datos `p2` estaba en alembic 0014 — la
  migración **0015** (`fn_eliminar_inventario_fibra`) nunca se aplicó.
  Todo DELETE FO ejecutaba una función inexistente → SQLSTATE **42883**
  (undefined_function) → `DBAPIError` sin mapeo → HTTP 500 en PAQUETE y
  EN_USO (fo_report_1.md §2). Secundario: una violación FK por DELETE
  dentro de una stored function se reporta como SQLSTATE **23001**
  (restrict_violation), no 23503.
- [x] **0.2 Auditoría de firma**: `eliminar_material_fibra` desempaqueta
  correctamente el path parameter `material_id: int` y el query parameter
  `motivo: str | None` (verificado; fijado con test REQ-DEL-FIX-001). —
  [REQ-DEL-FIX-001]

## Fase 1: Fix backend (exclusivo)
- [x] **1.0 Base de datos**: `alembic upgrade head` aplicado sobre `p2`
  (0014 → 0015): `fn_eliminar_inventario_fibra` ahora existe en el
  despliegue real (verificado con `SELECT fn_eliminar_inventario_fibra(...)`
  en transacción revertida).
- [x] **1.1 `app/services/transaccional.py`** — [REQ-DEL-FIX-002/003]:
  - Nuevo `mapear_error_delete_fibra(exc, *, modulo, material_id)`:
    SQLSTATE 23503/23001 (FK) → `BusinessRuleError` 409
    `FO_DELETE_INTEGRITY_CONFLICT` con mensaje de dominio claro ("No se
    puede eliminar porque existen movimientos o transferencias asociadas")
    y coordenadas `{modulo, material_id}`; 42883 (función no aplicada) →
    409 `FO_DELETE_UNAVAILABLE`; cualquier otro error de BD → 409
    controlado (fail-closed, jamás 500).
  - `eliminar_inventario_fibra` ejecuta el statement directamente y aplica
    el mapeo de dominio (P0001 conserva 404/422 vía
    `_mapear_raise_exception`). El mapeo genérico SEC-012 de `_ejecutar`
    permanece intacto para el resto de los flujos.
- [x] **1.2 `app/api/v1/fibra.py`** — [REQ-DEL-FIX-002]:
  - `eliminar_material_fibra` captura `DBAPIError` alrededor de
    `session.begin()` (vector commit-time) y lo traduce vía
    `mapear_error_delete_fibra` al mismo 409 de dominio.

## Fase 2: Tests de backend (secuencial, sesión principal)
- [x] **2.1 (`tests/test_fibra.py`)** — [REQ-DEL-FIX-002/003]:
  - `test_REQ_DEL_FIX_002_mapeo_fk_23503_409_mensaje_claro` (unitario del
    mapeo 23503 → 409 + coordenadas).
  - `test_REQ_DEL_FIX_002_mapeo_fk_restrict_23001_409_mensaje_claro`
    (unitario del mapeo 23001).
  - `test_REQ_DEL_FIX_002_mapeo_funcion_inexistente_42883_409` (unitario
    del mapeo 42883).
  - `test_REQ_DEL_FIX_002_delete_con_historial_fk_409_fila_intacta`
    (integración: guarda referencial transitoria `fo_delete_guard` →
    DELETE HTTP → 409 con mensaje claro y coordenadas; fila intacta; cero
    eventos ELIMINACION_FO).
  - `test_REQ_DEL_FIX_001_path_y_query_params_resueltos` — [REQ-DEL-FIX-001]:
    DELETE EN_USO con motivo → 204 y snapshot ELIMINACION_FO con
    modulo/material_id/motivo correctos.
- [x] **2.2 Regresión happy path** — [REQ-DEL-FIX-004]:
  - REQ-DEL-001/003/004 existentes (204 con motivo, 204 stock 0, 422 sin
    motivo, 404 fila inexistente) verdes sin cambios.

## Fase 3: Regresión completa (secuencial)
- [x] **3.1 pytest backend completo**: **209/209 passed** — cero 500 en
  las rutas de Fibra Óptica. — [REQ-DEL-FIX-007]
- [x] **3.2 vitest frontend**: **45/45 passed** (10 archivos) — frontend
  intacto y verde. — [REQ-DEL-FIX-005]
- [x] **3.3 mypy**: `Success: no issues found in 45 source files`.

## Fase 4: QA y consolidación
- [x] **4.1 Zero-Drift QA**: proposal/EARS/tasks referencian
  `docs/fo_report_1.md`; cada tarea referencia su EARS.
- [x] **4.2 Verificación de invariantes**: TEAMS/DEVOL, catálogo general
  y Ver Detalle/Modificar FO verdes dentro de la suite completa —
  ecosistema FO preservado. — [REQ-DEL-FIX-006]

## Notas
- Sin cambios en: frontend (`src/`), `backend/db/ddl.sql`, funciones
  TEAMS/DEVOL, catálogo general, PATCH/GET de fibra.
- Sin migraciones nuevas: se aplicó la migración existente 0015 al
  despliegue real `p2` (procedimiento estándar documentado en README).
- Los SQLSTATE 23503 y 23001 comparten rama de integridad: 23503 es la
  violación clásica INSERT/UPDATE; 23001 es la que PostgreSQL reporta para
  DELETE con FK ON DELETE RESTRICT dentro de una stored function.
