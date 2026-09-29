# Implementation Tasks: 2026-09-29-fo-crud-management

> RESTRICCIÓN DE EJECUCIÓN (obligatoria): NO ejecutar subagentes en
> paralelo (riesgo de deadlocks en PostgreSQL). Las pruebas (pytest y
> vitest) se ejecutan de forma ESTRICTAMENTE SECUENCIAL en la sesión
> principal: primero `pytest` completo y, al terminar, `vitest`.

## Fase 1: Gobernanza y Sign-off
- [x] **1.1 Architecture Sign-off (`@arq-reviewer`)**: verificar que proposal/EARS preservan los invariantes del sistema (CERO aritmética de stock en Python, autoridad transaccional PostgreSQL, aislamiento por módulo FO, invariante de transferencias TEAMS/DEVOL). — Governance work. Resultado: SIGN-OFF APPROVED (8 enmiendas aplicadas y re-verificadas).
- [x] **1.2 Specification Audit (`@auditor`)**: confirmar cero drift entre `docs/fo_report.md` y los EARS, y que cada tarea referencia su EARS. — Governance work. Resultado: APPROVED (4 observaciones LOW no bloqueantes documentadas).

## Fase 2: Backend
- [x] **2.1 PATCH atómico FO (`@coder`)** — [REQ-CATFO-001/002, REQ-STOCK-001/002/003]: implementado en `schemas/inventario.py` (FibraMaterialUpdateRequest/Out), `api/v1/fibra.py` (PATCH con pre-check 404, catálogo vía exclude_unset + ajuste fn_ajustar_stock_fibra en el mismo session.begin()).
  - `app/schemas/inventario.py`: nuevos `FibraMaterialUpdateRequest` (descripcion, codigo, categoria_id, nueva_categoria, u_m, stock_minimo, stock_actual, motivo; `extra="forbid"`) y `FibraMaterialOut`; validator que exija `motivo` no vacío SI `stock_actual` está presente (espejo de `_check_stock_motivo` de MaterialUpdate).
  - `app/api/v1/fibra.py`: `PATCH /{modulo}/materiales/{material_id}` — valida U.M. dinámica y categoría vía `services/catalogo`, aplica los campos de catálogo (el stock NUNCA pasa por setattr) y, si `stock_actual` cambia, invoca `transaccional.ajustar_stock_fibra` dentro del MISMO `session.begin()` (atomicidad 4.1; si el ajuste falla, la edición revierte).
- [x] **2.2 DELETE por módulo FO (`@coder`/`@dba-guard`)** — [REQ-DEL-001/002/003/004]: implementado — migración `0015_fo_crud_management` + `ddl.sql` (fn_eliminar_inventario_fibra con FOR UPDATE, motivo obligatorio si stock>0, auditoría ELIMINACION_FO con snapshot jsonb completo y atribución app.actor), wrapper `transaccional.eliminar_inventario_fibra` y `DELETE /{modulo}/materiales/{material_id}` → 204 (motivo por query param).
  - Migración alembic `0015_fo_crud_management` + actualización canónica de `backend/db/ddl.sql`: stored function `fn_eliminar_inventario_fibra(modulo, material_id, motivo)` que elimina SOLO la fila de `inventario_fibra` del módulo y audita `ELIMINACION_FO` con `detalles` jsonb COMPLETO (`modulo`, `material_id`, `stock_eliminado`, `motivo`) — CERO escritura directa de `inventario_fibra` en Python (Invariante 5). Atribución del actor vía `set_config('app.actor', ...)` (patrón `_set_actor` de services/catalogo.py, Constitution 6.2); si `stock_actual > 0` y el motivo está vacío → RAISE (422).
  - `app/services/transaccional.py`: `eliminar_inventario_fibra(session, *, modulo, material_id, motivo)` que invoca la función con pre-chequeo 404 y mapeo de errores (el `motivo` se reenvía a la función PG; obligatorio si stock > 0, REQ-DEL-004).
  - `app/api/v1/fibra.py`: `DELETE /{modulo}/materiales/{material_id}` → 204.
- [x] **2.3 Contrato (`@coder`)** — [REQ-CATFO-001, REQ-DEL-001, REQ-STOCK-002]: implementado — paths PATCH/DELETE registrados en `openspec/openspec.yaml` y `fn_ajustar_stock_fibra` + `fn_eliminar_inventario_fibra` añadidas a `mandatory_functions`.
  - `openspec/openspec.yaml`: registrar los paths `/api/v1/fibra/{modulo}/materiales/{material_id}` (PATCH 200/422/404, DELETE 204/404) y añadir a `domain_rules.transaction_delegation.mandatory_functions` las funciones `fn_eliminar_inventario_fibra` (nueva) y `fn_ajustar_stock_fibra` (preexistente omitida — cierre del gap del contrato).

## Fase 3: Frontend
- [x] **3.1 Servicios y tipos (`@ui-agent`)** — [REQ-CRUD-001]: implementado — `updateFibraMaterial`/`eliminarFibraMaterial` en `services/fibra.ts` (DELETE con query param motivo), tipos nuevos en `types.ts` y etiqueta `ELIMINACION_FO` en `TIPOS_ACCION_AUDITORIA`.
- [x] **3.2 Formulario FO (`@ui-agent`)** — [REQ-CATFO-001, REQ-STOCK-001]: implementado — nuevo `components/FibraMaterialForm.tsx` (modo solo edición, U.M. dinámica con fallback, proyección visual del diferencial sin enviar el delta, motivo obligatorio al cambiar stock).
- [x] **3.3 Página FO con CRUD (`@ui-agent`/`@state-agent`)** — [REQ-CRUD-001/002, REQ-DEL-001, REQ-TRF-INV-002]: implementado — `pages/FibraOptica.tsx` con selección de fila, botones Ver Detalle/Modificar/Eliminar, `MaterialDetailDrawer`, `Modal` + `FibraMaterialForm`, delete con textarea de motivo si stock>0 (`ConfirmDialog` si stock=0); invalidaciones `['fibra', modulo]` + `['catalogo']`/`['categorias']` (update) y `['auditoria']` (delete). Typecheck `tsc -b --noEmit` OK.

## Fase 4: Tests (SECUENCIAL — sesión principal, SIN paralelismo)
- [x] **4.1 Backend (`@tester`)** — [REQ-CATFO-001/002, REQ-STOCK-001/002/003, REQ-DEL-001/002/003/004]: 9 tests nuevos en `tests/test_fibra.py` (PATCH catálogo sin tocar stock, 422 sin motivo, ajuste auditado con diferencial, atomicidad con U.M. inválida, DELETE 422/204/404 con aserción de detalles ELIMINACION_FO). Suite completa: **204 passed**.
  - `tests/test_fibra.py`: PATCH edita campos de catálogo sin tocar stock; cambio de stock sin motivo → 422; con motivo → diferencial en PostgreSQL + evento `AJUSTE_INVENTARIO_FO`; atomicidad (ajuste inválido revierte la edición); DELETE elimina SOLO la fila del módulo y audita `ELIMINACION_FO` asertando el contenido de `detalles` (modulo, material_id, stock_eliminado, motivo); 404 si no existe; eliminación con `stock_actual > 0` sin motivo → 422, con motivo → 204; el material sigue visible en el otro módulo y en el catálogo.
- [x] **4.2 Regresión de transferencias (`@tester`)** — [REQ-TRF-INV-001/003]: regresión completa verde + nuevo test `test_REQ_TRF_INV_003_devol_post_eliminacion_recrea_fila_upsert` (DEVOL recrea la fila eliminada vía UPSERT, traza ELIMINACION_FO → DEVOL_DEVOLUCION).
  - `tests/test_fo_transferencias.py` (regresión completa, sin cambios de lógica): TEAMS desde FO descuenta `inventario_fibra`; DEVOL hacia FO acredita `inventario_fibra`; auditoría `modulo_fo` intacta. Nuevo test: DEVOL posterior a una eliminación FO recrea la fila vía UPSERT sin corrupción (REQ-TRF-INV-003).
- [x] **4.3 Frontend (`@tester`)** — [REQ-CRUD-001/002, REQ-TRF-INV-002]: nuevo `FibraOptica.test.tsx` (4 tests: botones+drawer, guardar+invalidación, stock sin motivo bloquea, eliminar con motivo+invalidación). Vitest: **45 passed (10 files)**.
  - Ejecución secuencial en la sesión principal realizada: `pytest` completo (204 passed) → luego `npm run test` (45 passed).

## Fase 5: QA y consolidación
- [x] **5.1 Zero-Drift QA (`@qa-agent`)**: verificar consumo frontend contra contrato backend (secuencial, sin subagentes en paralelo). — Governance work. Resultado: **READY** (contrato/trazabilidad 100 %, 4 hallazgos LOW documentados en `qa-report.md`).
- [x] **5.2 Final Integration (`@auditor`)**: regresión completa y cierre del paquete. — Governance work. Resultado: **APPROVED** (pytest 204 ✓, vitest 45 ✓, `openspec validate` ✓, cero drift; reporte en `qa-report.md`, sign-off en `sign-off.md`).

## Desviaciones y consecuencias documentadas (heredadas / aceptadas)
- La eliminación FO es física sobre `inventario_fibra` (no soft-delete): la traza forense queda en el evento `ELIMINACION_FO` con snapshot completo (`stock_eliminado`, motivo, actor) — ledger inmutable (Constitution 6.2). Reintroducir stock requiere una nueva Carga Inicial FO.
- Resurrección por UPSERT (REQ-TRF-INV-003): una devolución DEVOL posterior recrea silenciosamente la fila eliminada (`INSERT … ON CONFLICT (modulo, material_id) DO UPDATE` en `fn_procesar_movimiento`). Comportamiento preexistente y auditable (ELIMINACION_FO → DEVOL_DEVOLUCION); se documenta y se cubre con regresión en 4.2.
- `catalogo_materiales` es compartido entre módulos: editar Descripción/Código/U.M./Stock Mínimo desde FO se refleja en todas las vistas del material (misma semántica que la edición desde Inventario General). El aislamiento se mantiene exclusivamente en el stock (`inventario_fibra` por módulo).
