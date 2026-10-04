# Implementation Tasks: 2026-10-04-eliminar-breadcrumb-dashboard

> RESTRICCIÓN DE EJECUCIÓN: cero subagentes en paralelo. Las fases se
> ejecutaron de forma estrictamente secuencial: artefactos → ROJO → GREEN →
> verificación.

## Fase 0: Artefactos OpenSpec
- [x] **0.1** `proposal.md` + `EARS.md` + `.openspec.yaml` + `tasks.md`
  creados — [REQ-BREAD-001..006]
- [x] **0.2** `openspec/openspec.yaml` revisado: sin reglas de UI de
  breadcrumb; `skip_specs: true` (precedente `eliminar-buscador-a-granel`).

## Fase 1: Contrato y Componentes
- [x] **1.1** Touchpoint mapeado: `components/Header.tsx:27` (`<span>Dashboard</span>`
  + separador). `MainLayout.tsx` ya genera la ruta limpia; Sidebar y páginas
  sin referencias a "Dashboard".

## Fase 2: Pruebas en ROJO
- [x] **2.1** Nuevo `components/__tests__/Header.test.tsx` (vitest):
  "Dashboard" no se renderiza; ruta limpia sí; buscador operativo —
  [REQ-BREAD-001/002/004/006]
- [x] **2.2** Suite ejecutada: **rojo confirmado** — 4 fallos esperados
  ("Dashboard" presente) + 3 verdes de saneamiento del buscador.

## Fase 3: Implementación (Green)
- [x] **3.1** `components/Header.tsx`: eliminados `<span>Dashboard</span>` y
  separador "/"; el `<nav>` renderiza solo el breadcrumb limpio —
  [REQ-BREAD-001/002]
- [x] **3.2** Verificación puntual GREEN: Header.test.tsx 7 passed.

## Fase 4: Verificación Zero-Drift
- [x] **4.1** Frontend: `npm run test` — **341 passed (100 %)**
  (baseline 334 + 7 nuevos); `npm run build` (`tsc -b` + vite) exit 0
  (único warning de chunk-size preexistente); `npm run lint` limpio.
- [x] **4.2** `openspec validate --all --strict` → 5 passed / 1 failed, único
  fallo preexistente documentado (`2026-10-01-reportes-consumo-management`,
  sin `.openspec.yaml`, ajeno a este cambio). El change
  `2026-10-04-eliminar-breadcrumb-dashboard` valida ✓.
- [x] **4.3** Residuos: "Dashboard" en `frontend/src` = 0 coincidencias en
  código de producción; solo comentarios/aserciones negativas del test nuevo.

## Fase 5: Registro y Commit
- [x] **5.1** `tasks.md` completo con resultados.
- [x] **5.2** Commit en `feat/ergonomia-justificacion-opcional`, árbol limpio.
