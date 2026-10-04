# Implementation Tasks: 2026-10-04-eliminar-buscador-a-granel

> RESTRICCIÓN DE EJECUCIÓN: cero subagentes en paralelo. Las fases se
> ejecutaron de forma estrictamente secuencial: tester (ROJO) → coder
> (GREEN) → tester (verificación).

## Fase 0: Artefactos OpenSpec
- [x] **0.1** `proposal.md` + `EARS.md` + `.openspec.yaml` + `tasks.md`
  creados — [REQ-SIMPL-001..006]
- [x] **0.2** `openspec/openspec.yaml` revisado: sin reglas de UI ni esquemas
  desalineados (no documenta rangos de `GET /catalogo`).

## Fase 1: Contrato y Componentes
- [x] **1.1** Touchpoints mapeados: `BulkSearch.tsx`, `SeccionGeneral.tsx`
  (import/estado `tab`/barra de tabs/condicional/comentario),
  `services/catalog.ts` (`CatalogFilters` bulk), `types.ts` (comentario
  `start_index`). Backend y `App.tsx` sin referencias.

## Fase 2: Pruebas en ROJO
- [x] **2.1** Nuevo `components/__tests__/SeccionGeneral.test.tsx`
  (vitest): la pestaña "Buscador a granel" y la barra de tabs no se
  renderizan; el buscador principal sí — [REQ-SIMPL-001/002/006]
- [x] **2.2** Suite ejecutada: **rojo confirmado** — 2 fallos (botones
  "2 Buscador a granel" y "1 Buscador" presentes) + 1 verde de saneamiento
  ("Mostrando 0 de 0 registros"); `tsc -b` exit 0.

## Fase 3: Implementación (Green)
- [x] **3.1** `components/BulkSearch.tsx` eliminado (214 líneas) — [REQ-SIMPL-003]
- [x] **3.2** `pages/SeccionGeneral.tsx`: import/estado `tab`/barra de
  pestañas/ternario eliminados; `InventoryTable` + paginación directos;
  comentario de `deleteMut` actualizado — [REQ-SIMPL-001/002/004]
- [x] **3.3** `services/catalog.ts`: campos bulk de `CatalogFilters`
  eliminados (legacy `@deprecated` conservado; comentario deprecado
  actualizado) — [REQ-SIMPL-003]
- [x] **3.4** `types.ts`: comentario de `MaterialList.start_index`
  actualizado (campo conservado: contrato real) — [REQ-SIMPL-005]
- [x] **3.5** Verificación puntual GREEN: vitest 3 passed, `tsc -b` exit 0,
  eslint limpio.

## Fase 4: Verificación Zero-Drift
- [x] **4.1** Frontend: `npm run test` — **334 passed (30 files, 100 %)**
  (baseline 331 + 3 nuevos); `npm run build` (`tsc -b` + vite) exit 0
  (único warning de chunk-size preexistente; el bundle se redujo ~5 kB);
  `npm run lint` limpio.
- [x] **4.2** Backend: `pytest tests/` — **303 passed** (sin cambios; el
  fallo ambiental inicial de `fe_sendauth` se resolvió exportando las URLs
  de BD del README, ajeno al cambio).
- [x] **4.3** `openspec validate --specs --strict` → exit 0;
  `openspec validate --all --strict` → 4 passed / 1 failed, único fallo
  preexistente documentado (`2026-10-01-reportes-consumo-management`, sin
  `.openspec.yaml`/deltas, ajeno a este cambio). El change
  `2026-10-04-eliminar-buscador-a-granel` valida ✓.
- [x] **4.4** Residuos: `BulkSearch`/`bulk` = 0 coincidencias en
  `frontend/src`; `granel` solo en aserciones negativas del test nuevo.
  Backend (`test_busqueda_granel.py`) fuera de alcance por contrato.

## Fase 5: Registro y Commit
- [x] **5.1** `tasks.md` completo con resultados.
- [x] **5.2** Commit en `feat/ergonomia-justificacion-opcional`, árbol limpio.
