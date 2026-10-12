# Tareas: 2026-10-12-equipo-a-unidad

> Ejecución estrictamente secuencial. Override de nomenclatura vigente en cada delegación (Unidad / TRANSF / Confirmar Devolución / Inventario FO).
> Frontend (T11-T15) bloqueado hasta cumplir T10. Trazabilidad: ver `spec.md`.

## Fase 1-2: Gobierno y contexto

- [x] **T1** Alinear `.agents.md` (Override, nomenclatura, 9 fases, artefactos `spec/plan/tasks`). (@auditor)
  **Hecho cuando:** `.agents.md` cita la Cláusula de Override y ya no usa "Equipos" como término vigente. *(Verificado: ya estaba alineado.)*

## Fase 3-6: Especificación, clarificación, plan y tareas

- [x] **T2** Crear `.openspec.yaml`, `spec.md`, `plan.md`, `tasks.md` y pasar revisión de dominio. (@arq-reviewer, @auditor)
  **Hecho cuando:** `openspec validate` no reporta errores y cada RF tiene tarea y test asignados.
- [x] **T3** **GATE HUMANO**: aprobación explícita de `spec.md`, `plan.md` y `tasks.md`.
  **Hecho cuando:** hay aprobación escrita en la conversación. Sin ella no se modifica `backend/` ni `frontend/`. *(Aprobado 2026-10-12.)*

## Fase 7a: Backend

- [x] **T4** Escribir tests backend en ROJO para RF-6, RF-7 y RF-8. (@tester) — [REQ-UNI-006/007/008]
  **Hecho cuando:** fallan por el motivo esperado y cada test cita su `REQ-UNI-NNN`.
- [x] **T5** Revisión de seguridad. (@sec-ops) — [REQ-UNI-008]
  **Hecho cuando:** confirma por escrito que RBAC (`assert_equipo_access`) y `extra="forbid"` no varían. *(Evidencia: `git diff backend/app/schemas backend/app/models` vacío; en `security.py` solo cambia el literal del mensaje 403. Revisión realizada por el orquestador siguiendo el checklist de @sec-ops, cuyo agente es de invocación solo manual.)*
- [x] **T6** Cambiar `detail` a "Unidad" y actualizar el mapeo por subcadena (aceptando ambas variantes). (@coder) — [REQ-UNI-006/007]
  **Hecho cuando:** los tests de RF-6 pasan y los códigos 404/400 no cambian.
- [x] **T7** Migración `0024_unidad_textos_raise` con `downgrade`, basada en `pg_get_functiondef`. (@dba-guard, @coder) — [REQ-UNI-007]
  **Hecho cuando:** `alembic upgrade head` → `downgrade -1` → `upgrade head` ejecutan limpio y el diff de `pg_get_functiondef` solo muestra los literales del plan. *(Evidencia: upgrade cambia exactamente las 5 funciones previstas; downgrade restaura los md5 originales; re-upgrade idéntico.)*
- [x] **T8** Ajustar tests con el texto antiguo. (@tester) — [REQ-UNI-007]
  **Hecho cuando:** `tests/test_fo_transferencias.py:371` y `sql_tests/test_fase1_consumo.py:697` pasan con el texto nuevo, y `:751` queda revisado y documentado.
- [x] **T9** Suite backend completa y tipado. (@tester, @qa-agent) — [REQ-UNI-020]
  **Hecho cuando:** `pytest`, `sql_tests` y `mypy` pasan al 100% / 0 errores, sin regresión respecto de la línea base. *(Evidencia: 356 passed = 330 de línea base + 26 nuevos `test_unidad_nomenclatura.py`; mypy app: 0 errores en 48 archivos.)*
- [x] **T10** Congelar el contrato backend. (@arq-reviewer, @auditor) — [REQ-UNI-008]
  **Hecho cuando:** el OpenAPI no tiene diff de rutas ni DTOs, y hay aprobación humana. Desbloquea el frontend. *(Evidencia: OpenAPI idéntico HEAD vs árbol actual; aprobado 2026-10-12.)*

## Fase 7b: Frontend

- [x] **T11** Plan frontend: lista de textos a renombrar, lista blanca (RF-5), tipos y query keys sin cambios, estados del select. (@state-agent, @ux-agent) — [REQ-UNI-001..005]
  **Hecho cuando:** la lista de textos y la lista blanca están aprobadas. *(Evidencia: inventario de textos visibles por barrido de literales y JSX; lista blanca = U.M. `EQUIPO` y categoría "Equipos"; tipos, query keys y rutas sin cambios.)*

- [x] **T12** Renombrar textos visibles y `EquipoForm`; añadir el test de barrido. (@ui-agent, @form-agent) — [REQ-UNI-001..004, 021]
  **Hecho cuando:** RF-1..RF-4 verificados y el test de RF-18 pasa. *(Evidencia: 16 archivos de `frontend/src` actualizados; test de barrido `utils/__tests__/nomenclaturaUnidad.test.ts`.)*

- [x] **T13** Select de Consulta: 3 vistas, valor por defecto, vacíos, reset al cambiar de unidad, solo lectura. (@ui-agent) — [REQ-UNI-010..017]
  **Hecho cuando:** RF-9..RF-16 están cubiertos por vitest y Consulta no emite peticiones de escritura. *(Evidencia: `components/UnidadConsultaDetalle.tsx`, `utils/consultaUnidad.ts`; 9 tests en `components/__tests__/InventarioPorUnidad.test.tsx` cubren RF-9..RF-16.)*

- [x] **T14** Ajustar tests frontend existentes. (@tester) — [REQ-UNI-001/006]
  **Hecho cuando:** `Transferencias`, `Reportes`, `SeguimientoNuevaListaForm`, `ActaGeneradaAviso` y `ReporteExportFeedback` pasan. *(Evidencia: ajustados `SeguimientoNuevaListaForm`, `ReporteExportFeedback` y `ActaGeneradaAviso`; `Transferencias`/`Reportes` no requirieron cambios.)*

- [x] **T15** Validación Zero-Drift. (@qa-agent) — [REQ-UNI-020]
  **Hecho cuando:** `vitest`, `tsc -b`, `eslint .`, build y `openspec validate --specs --strict` pasan sin warnings (Constitución §7.2).

## Fase 8-9: Validación y evolución *(Evidencia: vitest 356/356, `tsc -b` 0 errores, `eslint .` 0, `vite build` OK, `openspec validate` change y specs strict OK.)*

- [x] **T16** Sincronizar `README.md`, `openspec/specs/003_inventory_dashboard/spec.md` y `openspec/openspec.yaml`; completar la matriz de trazabilidad. (@auditor)
  **Hecho cuando:** ningún documento vigente usa "Equipo" como término de dominio (salvo la lista blanca). *(Evidencia: README y spec 003 sincronizados; `openspec.yaml` no cambia: rutas y campos intactos.)*

- [x] **T17** Aceptación humana, commit en rama `feat/` y archivo del paquete. (@auditor)
  **Hecho cuando:** hay aprobación humana, commit realizado y paquete movido a `openspec/changes/archive/`. *(Aceptado 2026-10-12; commit local en `feature/p2-migracion-unidades-y-sdd`, sin merge.)*
