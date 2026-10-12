# Plan técnico (solo `frontend/src`)

**Change ID:** `2026-10-12-nomenclatura-transf` · **Spec:** `spec.md` (RF-1..RF-9)

- Sin impacto en BD, API ni OpenAPI; no aplica el gate de congelamiento de contrato.
- `types.ts`: `TIPOS_MOVIMIENTO` (hoy sin uso) pasa a `{ TEAMS: 'TRANSF', DEVOL: 'DEVOL' }` y se añade `etiquetaTipoMovimiento(tipo)`; `TIPOS_ACCION_AUDITORIA.TEAMS_TRANSFERENCIA` = "TRANSF — transferencia". `DEVOL_DEVOLUCION` se deja: DEVOL no cambia.
- `pages/Transferencias.tsx`: pestañas con la etiqueta; botón "Confirmar Transferencia" / "Confirmar Devolución" (en lugar de `Confirmar {tab}`); columna TIPO y modal de cancelación con la etiqueta. La clave interna `tab` sigue siendo `'TEAMS' | 'DEVOL'`.
- `components/ActaGeneradaAviso.tsx`: texto sin "movimiento TEAMS".
- `pages/Reportes.tsx`: descripción de la subsección Entrega.
- Tests: ajustar las aserciones de `Transferencias(.test/MultiOrigen)` y `ActaGeneradaAviso`; añadir `NomenclaturaTransf.test.tsx` y el barrido de "TEAMS" en `utils/__tests__/nomenclaturaUnidad.test.ts`.
- Riesgo: el barrido debe permitir el literal técnico `'TEAMS'` en código no visible; se acota a texto JSX y se prueba con un detector de ejemplo.
