# Tareas: 2026-10-12-nomenclatura-transf

> Secuencial. Solo `frontend/`.

- [x] **T1** Crear `.openspec.yaml`, `spec.md`, `plan.md`, `tasks.md` y validar.
  **Hecho cuando:** `openspec validate --strict` pasa y cada RF tiene tarea y test.
- [x] **T2** **GATE HUMANO**: aprobación de los tres documentos.
  **Hecho cuando:** hay aprobación escrita. *(Aprobado 2026-10-12.)*
- [x] **T3** Tests en ROJO (etiquetas, botones, TIPO, modal, aviso, auditoría).
  **Hecho cuando:** fallan por el texto actual. *(Evidencia: `NomenclaturaTransf.test.tsx` (7 tests) y aserciones ajustadas; 17 tests fallaron en rojo por el texto antiguo antes de implementar.)*

- [x] **T4** Etiquetas centralizadas en `types.ts` y `Transferencias.tsx`.
  **Hecho cuando:** RF-1..RF-4 y RF-6 pasan. *(Evidencia: `etiquetaTipoMovimiento`/`TIPOS_MOVIMIENTO` en `types.ts`; pestaña TRANSF, botones "Confirmar Transferencia"/"Confirmar Devolución", columna TIPO y modal de cancelación en `Transferencias.tsx`; la pestaña DEVOL conserva su nombre.)*

- [x] **T5** Aviso del acta, Auditoría y Reportes.
  **Hecho cuando:** RF-5 pasa. *(Evidencia: `ActaGeneradaAviso` ("La transferencia hacia… fue CONFIRMADA"), `TIPOS_ACCION_AUDITORIA.TEAMS_TRANSFERENCIA` = "TRANSF — transferencia", descripción de Reportes y el texto de `FibraOptica.tsx` que el barrido detectó.)*

- [x] **T6** Ajustar tests existentes y añadir el barrido de "TEAMS".
  **Hecho cuando:** RF-8 pasa y el detector reconoce un caso positivo. *(Evidencia: barrido de "TEAMS" en `nomenclaturaUnidad.test.ts`; en su primera corrida detectó un texto visible en `FibraOptica.tsx` que se había escapado; el detector respeta literales técnicos y tiene caso positivo.)*

- [x] **T7** Zero-Drift: vitest, `tsc -b`, eslint, build, `openspec validate --strict`; el payload sigue enviando TEAMS/DEVOL.
  **Hecho cuando:** todo verde y RF-7 verificado por test. *(Evidencia: vitest 380/380, `tsc -b` 0, `eslint .` 0, `vite build` OK; RF-7: el payload sigue enviando `tipo_movimiento: 'TEAMS'`; no se tocó `backend/`.)*

- [x] **T8** README/specs si mencionan los botones; aceptación, commit local y archivo del paquete.
  **Hecho cuando:** aprobación humana y commit en `feature/p2-migracion-unidades-y-sdd`; sin merge. *(Aceptado 2026-10-12; commit local en `feature/p2-migracion-unidades-y-sdd`, sin merge.)*
