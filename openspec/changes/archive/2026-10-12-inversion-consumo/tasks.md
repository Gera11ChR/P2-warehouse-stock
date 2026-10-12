# Tareas: 2026-10-12-inversion-consumo

> Ejecución secuencial. Frontend (T11-T15) bloqueado hasta cumplir T10. Backend solo en `backend/`, frontend solo en `frontend/`.

- [x] **T1** Crear `.openspec.yaml`, `spec.md`, `plan.md`, `tasks.md` y validar. (@arq-reviewer, @auditor)
  **Hecho cuando:** `openspec validate --strict` pasa y cada RF-n tiene tarea y test asignados.
- [x] **T2** Documentar el cuerpo vivo de `fn_cerrar_seguimiento` y dependencias de `seguimiento_items`. (@dba-guard)
  **Hecho cuando:** la lista de dependencias confirma que no hay vistas/triggers afectados. *(Evidencia: cuerpo vivo = 0020 recreado por 0024; no hay triggers ni vistas sobre `seguimiento_items`; los triggers de 0022 solo cubren `auditoria_eventos` y `actas_reportes`.)*

- [x] **T3** **GATE HUMANO**: aprobación de `spec.md`, `plan.md` y `tasks.md`.
  **Hecho cuando:** aprobación escrita. *(Aprobado 2026-10-12.)*
- [x] **T4** Tests backend en ROJO (RF-3..RF-13). (@tester)
  **Hecho cuando:** fallan por el motivo esperado y cada test cita su `REQ-CONSUMO`. *(Evidencia: `tests/test_inversion_consumo.py`, 21 tests; 17 fallaron en rojo por el motivo esperado antes de implementar.)*

- [x] **T5** Revisión de seguridad del DTO. (@sec-ops)
  **Hecho cuando:** confirma `extra="forbid"`, 422 para `sobrantes` y rollback sin efectos. *(Evidencia: `ConsumoLine` y `CerrarSeguimientoRequest` con `extra="forbid"`; tests 003 verifican 422 con `sobrantes` y con campo extra, sin cambio de inventario ni estado. Revisión por el orquestador con el checklist de @sec-ops, agente de invocación manual.)*

- [x] **T6** Migración 0025 + función. (@dba-guard, @coder)
  **Hecho cuando:** upgrade → downgrade → upgrade limpios; backfill y md5 verificados. *(Evidencia: `0025_consumo_directo.py`; upgrade→downgrade→upgrade limpios, md5 de la función tras downgrade idéntico al de 0024; backfill y downgrade verificados en BD aparte por `test_REQ_CONSUMO_011`.)*

- [x] **T7** Modelo, schemas, servicio, endpoint y mapeo de errores. (@coder)
  **Hecho cuando:** pasan los tests de T4 y el stock solo cambia vía la función. *(Evidencia: modelo, schemas, servicio, endpoint y mapeo `Consumo inválido`→400 / `Falta la cantidad consumida`→422; el stock solo cambia vía la función; test AST de cero aritmética de stock en Python sigue verde.)*

- [x] **T8** Reportes sin `cantidad_sobrante` y lectura de actas antiguas. (@coder)
  **Hecho cuando:** RF-10 y RF-12 pasan con snapshots antiguos y nuevos. *(Evidencia: `ActaItemOut` sin `cantidad_sobrante`; `test_REQ_CONSUMO_010` lee un acta histórica con la clave antigua.)*

- [x] **T9** Reescribir tests existentes; suite completa y mypy. (@tester, @qa-agent)
  **Hecho cuando:** pytest, sql_tests y mypy al 100% / 0 errores. *(Evidencia: pytest + sql_tests 377 passed = 356 línea base + 21 nuevos; mypy app 0 errores en 48 archivos.)*

- [x] **T10** Congelar contrato: diff OpenAPI revisado y `openspec.yaml` actualizado. (@arq-reviewer, @auditor)
  **Hecho cuando:** el único diff de OpenAPI es el esperado y hay aprobación humana. *(Evidencia previa a la aprobación: `openspec.yaml` actualizado; el diff OpenAPI HEAD vs árbol actual solo retira `SobranteLine`/`cantidad_sobrante`/`sobrantes` y añade `ConsumoLine`/`consumidos` obligatorio. Aprobado 2026-10-12.)*

- [x] **T11** Plan frontend. (@state-agent, @ux-agent)
  **Hecho cuando:** textos, estados del formulario y esquema Zod aprobados. *(Evidencia: textos, estados y esquema definidos: campo vacío `required`, error por material faltante, rango 0..tomada, `consumidos` min 1; la lista de archivos coincide con `plan.md` §5.)*

- [x] **T12** Formulario de cierre, Zod y tipos. (@form-agent, @state-agent)
  **Hecho cuando:** RF-1 verificado por vitest. *(Evidencia: `SeguimientoCierreForm`, `schemas/seguimiento.ts`, `types.ts`, `services/seguimientos.ts`; `SeguimientoCierreForm.test.tsx` cubre vacío inicial, faltantes, 0 explícito y payload.)*

- [x] **T13** Panel, tabla de reportes y barrido de "sobrante". (@ui-agent)
  **Hecho cuando:** RF-12 y RF-14 pasan. *(Evidencia: `ReporteConsumoTable` sin columna Sobrante; `SeguimientoPanel` sin "sobrantes"; barrido en `utils/__tests__/nomenclaturaUnidad.test.ts` sobre texto visible y sobre todo el código de producción.)*

- [x] **T14** Ajustar tests frontend. (@tester)
  **Hecho cuando:** los archivos afectados pasan. *(Evidencia: ajustados `seguimientos` (service/hooks), `SeguimientoPanel(+Flujo)`, `Reportes` y `SeguimientoCierreForm`.)*

- [x] **T15** Zero-Drift: vitest, `tsc -b`, eslint, build y `openspec validate --strict`. (@qa-agent)
  **Hecho cuando:** todo en verde y cierre probado contra el backend real. *(Evidencia: vitest 362/362, `tsc -b` 0, `eslint .` 0, `vite build` OK, `openspec validate` OK; cierre probado por HTTP contra uvicorn real: `sobrantes` 422, lista vacía 422, consumido 15 → 200 y stock de la unidad 50 → 35, sin "sobrante" en la respuesta.)*

- [x] **T16** Sincronizar README y specs. (@auditor)
  **Hecho cuando:** ningún documento vigente describe sobrantes. *(Evidencia: README actualizado; `openspec.yaml` ya actualizado en T10; las specs maestras no mencionan sobrantes.)*

- [x] **T17** Aceptación, commit local (incluye `docs/migracion-dms-telecom/1 Changes.docx`) y archivo del paquete. (@auditor)
  **Hecho cuando:** aprobación humana y commit hechos; sin merge. *(Aceptado 2026-10-12; commit local en `feature/p2-migracion-unidades-y-sdd`, sin merge.)*
