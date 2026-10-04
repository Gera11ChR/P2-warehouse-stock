# Implementation Tasks: 2026-10-04-ergonomia-justificacion-opcional

> RESTRICCIÓN DE EJECUCIÓN: cero subagentes en paralelo (evitar deadlocks
> en PostgreSQL). Todas las fases se ejecutan de forma estrictamente
> secuencial en la sesión principal.

## Fase 0: Artefactos OpenSpec
- [x] **0.1** `proposal.md` + `EARS.md` + `.openspec.yaml` creados — [REQ-ERG-001/002]
- [x] **0.2** `openspec/openspec.yaml`: nueva `domain_rule.justificacion_opcional`;
  `/api/v1/ajustes/stock-almacen` sin `motivo` obligatorio; 422 de PATCH FO sin
  "stock_actual sin motivo no vacío".

## Fase 1: Contrato y Schemas Pydantic
- [x] **1.1** `app/schemas/material.py`: eliminado `_check_stock_motivo` — [REQ-ERG-003]
- [x] **1.2** `app/schemas/inventario.py`: `FibraAjusteRequest.motivo` opcional +
  eliminado `_check_stock_motivo` de `FibraMaterialUpdateRequest` — [REQ-ERG-004/005]
- [x] **1.3** `app/schemas/ajuste.py`: `AjusteStockAlmacenRequest.motivo` opcional — [REQ-ERG-005]
- [x] **1.4** `app/services/transaccional.py`: firmas `motivo: str | None` — [REQ-ERG-003/004/005]
- [x] **1.5** `app/api/v1/catalog.py` + `app/api/v1/fibra.py`: asserts eliminados — [REQ-ERG-003/004]

## Fase 2: Pruebas en ROJO
- [x] **2.1** Backend: invertidos los tests de motivo obligatorio
  (`test_ajuste_desde_material.py`, `test_fibra.py`, `test_ajustes.py`,
  `test_esquemas.py`); nuevos tests TEAMS/DEVOL con observaciones
  null/""/omitida (`test_teams.py`, `test_devol.py`) y cancelación sin motivo
  (`test_cancelaciones.py`) — [REQ-ERG-003..008]
- [x] **2.2** Frontend: nuevos tests vitest "Confirmar TEAMS/DEVOL con motivo
  vacío", "cancelación sin motivo" (`Transferencias.test.tsx`), "edición de
  stock sin motivo" (`MaterialForm.test.tsx`, `FibraOptica.test.tsx`) — [REQ-ERG-006/007/008]
- [x] **2.3** Suites ejecutadas: **rojo confirmado** — 4 fallos backend (RAISE
  SQL → 422) y 5 fallos frontend (bloqueo de UI); los tests de contrato
  TEAMS/DEVOL/cancelación ya verdes (el backend nunca exigió motivo).

## Fase 3: Implementación (Green)
- [x] **3.1** `db/ddl.sql`: RAISE de motivo eliminado en `fn_ajustar_stock_almacen`
  y `fn_ajustar_stock_fibra` — [REQ-ERG-003/004/005]
- [x] **3.2** Migración Alembic `0023_justificacion_opcional.py` (upgrade +
  downgrade exacto) aplicada: `p2` 0021→0023 y `p2_test` → head — [REQ-ERG-003/004/005]
- [x] **3.3** `pages/Transferencias.tsx`: motivo opcional en TEAMS/DEVOL y en
  cancelación (etiquetas "(opcional)", sin `required`, payload `null`) — [REQ-ERG-006/007/008]
- [x] **3.4** `components/MaterialForm.tsx` + `components/FibraMaterialForm.tsx`:
  motivo opcional en edición de stock (`motivo: null` si vacío) — [REQ-ERG-003/004]
- [x] **3.5** Comentarios de contrato actualizados en `services/{catalog,fibra}.ts`,
  `types.ts` y `pages/FibraOptica.tsx`.

## Fase 4: Verificación Zero-Drift
- [x] **4.1** Backend: `pytest tests/` — **303 passed** (100 %).
- [x] **4.2** Frontend: `vitest run` — **331 passed**; `tsc -b` (build) sin
  errores de tipos; `eslint .` limpio. `mypy` sobre los 6 módulos tocados:
  Success (los 5 errores restantes del repo son preexistentes en
  reportes/auditoria/plantilla, fuera de este cambio).
- [x] **4.3** `openspec validate --specs --strict` → exit 0 (gate DoD
  Constitution 7.2). `openspec validate --all --strict`: el cambio
  `2026-10-04-ergonomia-justificacion-opcional` valida ✓ (el fallo de
  `2026-10-01-reportes-consumo-management` es preexistente y ajeno a este
  cambio: le falta `skip_specs`/deltas en su propio `.openspec.yaml`).

## Fase 5: Registro y Commit
- [x] **5.1** `tasks.md` completo con resultados.
- [x] **5.2** Commit en `feat/ergonomia-justificacion-opcional`, árbol limpio.
