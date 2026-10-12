# Tareas: 2026-10-12-transferencias-multi-origen

> Ejecución secuencial. Frontend (T11-T15) bloqueado hasta cumplir T10. Backend solo en `backend/`, frontend solo en `frontend/`.

- [x] **T1** Crear `.openspec.yaml`, `spec.md`, `plan.md`, `tasks.md` y validar. (@arq-reviewer, @auditor)
  **Hecho cuando:** `openspec validate --strict` pasa y cada RF-n tiene tarea y test.
- [x] **T2** Documentar cuerpos vivos de las 3 funciones y consumidores del origen de cabecera. (@dba-guard)
  **Hecho cuando:** la lista de dependencias (acta, auditoría, scope, historial) está confirmada. *(Evidencia: cuerpos vivos de `fn_procesar_movimiento`, `fn_cancelar_movimiento` y `fn_generar_acta_entrega` (0025) capturados con `pg_get_functiondef`; consumidores del origen de cabecera: servicio de borradores, trigger `tg_acta_entrega`, auditoría por sección y `assert_scope`; el único trigger sobre las tablas de movimientos es `tg_acta_entrega`.)*

- [x] **T3** **GATE HUMANO**: aprobación de `spec.md`, `plan.md` y `tasks.md`.
  **Hecho cuando:** hay aprobación escrita. *(Aprobado 2026-10-12, con la aclaración sobre material único por línea.)*
- [x] **T4** Tests backend en ROJO (RF-2..RF-14). (@tester)
  **Hecho cuando:** fallan por el motivo esperado y cada test cita su `REQ-TRFM`. *(Evidencia: `tests/test_transferencias_multi_origen.py`, 17 tests; 13 fallaron en rojo por el motivo esperado antes de implementar y 4 (los 422) ya pasaban.)*

- [x] **T5** Revisión de seguridad: scope por origen y DTO. (@sec-ops)
  **Hecho cuando:** confirma 403 por cualquier origen sin scope y `extra="forbid"`. *(Evidencia: `DetalleLine` mantiene `extra="forbid"`; `assert_scope` se aplica sobre el CONJUNTO de orígenes (test 006: sin scope en un origen → 403 y ningún borrador creado); el PATCH de borradores también valida scope. Revisión por el orquestador con el checklist de @sec-ops, agente de invocación manual.)*

- [x] **T6** Migración 0026 + funciones. (@dba-guard, @coder)
  **Hecho cuando:** upgrade → downgrade → upgrade limpios; md5 y backfill verificados; downgrade aborta con mixtos. *(Evidencia: `0026_transferencias_multi_origen.py`; upgrade cambia exactamente las 3 funciones, downgrade devuelve md5 idéntico a 0025, re-upgrade idéntico; backfill, CHECK relajado y aborto del downgrade con movimiento mixto verificados en BD aparte por `test_REQ_TRFM_013`.)*

- [x] **T7** Modelo, schemas y servicio de borradores. (@coder)
  **Hecho cuando:** pasan los tests de T4 y el stock solo cambia vía las funciones. *(Evidencia: modelo, schemas y servicio; cabecera = origen común o NULL; el stock solo cambia vía las funciones y el test AST de cero aritmética de stock en Python sigue verde; mypy 0.)*

- [x] **T8** Acta y reportes con origen por línea. (@coder)
  **Hecho cuando:** RF-11 pasa y el XLSX no cambia. *(Evidencia: snapshot con `items[].origen` y `origenes`; `ActaItemOut.origen_almacen_id/origen_nombre`; `test_REQ_TRFM_011`: una sola acta con 3 líneas y 3 orígenes; XLSX sin cambios.)*

- [x] **T9** Ajustar tests existentes; suite completa y mypy. (@tester, @qa-agent)
  **Hecho cuando:** pytest, sql_tests y mypy al 100% / 0 errores. *(Evidencia: pytest + sql_tests 394 passed = 377 línea base + 17 nuevos, sin tocar ningún test existente; mypy app 0 errores en 48 archivos.)*

- [x] **T10** Congelar contrato: diff OpenAPI y `openspec.yaml`. (@arq-reviewer, @auditor)
  **Hecho cuando:** el único diff es `DetalleLine`/`DetalleOut`/`ActaItemOut` y hay aprobación humana. *(Evidencia: `openspec.yaml` actualizado (bloque `transferencias_multi_origen` y `POST /api/v1/movimientos`); diff OpenAPI HEAD vs árbol actual solo ADITIVO: `DetalleLine.origen_almacen_id`, `DetalleOut.origen_almacen_id`, `ActaItemOut.origen_almacen_id/origen_nombre`; `/movimientos/procesar` idéntico. Aprobado 2026-10-12.)*

- [x] **T11** Plan frontend: carrito, columna Origen y estados. (@state-agent, @ux-agent)
  **Hecho cuando:** diseño aprobado, sin contexto nuevo. *(Evidencia: diseño aplicado sin contexto nuevo: carrito local; el selector pasa a "Sección Origen (consulta)"; cada línea fija su origen al agregarse; `extremosValidos` TEAMS = unidad destino + todas las líneas con origen.)*

- [x] **T12** Tipos, servicio y payload por línea. (@state-agent, @form-agent)
  **Hecho cuando:** el payload lleva origen por línea y RF-16 pasa en vitest. *(Evidencia: `types.ts` (`CartLine`, `DetalleMovimiento` con `origen_almacen_id`); payload TEAMS sin origen de cabecera y con origen por línea.)*

- [x] **T13** Carrito multi-origen, historial e invalidaciones. (@ui-agent)
  **Hecho cuando:** RF-1 y RF-15 pasan; el carrito sobrevive al cambio de origen. *(Evidencia: `pages/Transferencias.tsx`: el carrito conserva líneas al cambiar de sección, línea con "Origen:" rotulado, historial con todos los orígenes en una sola fila, invalidación de todos los orígenes al cancelar.)*

- [x] **T14** Ajustar tests frontend. (@tester)
  **Hecho cuando:** Transferencias y afines pasan. *(Evidencia: `TransferenciasMultiOrigen.test.tsx` (9 tests, RF-1/11/12/15/16); los 362 tests previos pasan sin modificarse.)*

- [x] **T15** Zero-Drift: vitest, `tsc -b`, eslint, build y `openspec validate --strict`. (@qa-agent)
  **Hecho cuando:** todo verde y transferencia mixta probada por HTTP contra el backend real. *(Evidencia: vitest 371/371, `tsc -b` 0, `eslint .` 0, `vite build` OK, `openspec validate` OK; HTTP contra uvicorn real: el payload antiguo (origen General + línea FO) reproduce el 400 "Stock insuficiente en Origen (Sección ID 1)… Disponible: 0" de la captura; el payload nuevo da 200 con General 100→90, FO Paquete 50→30, unidad 10/20, cabecera con origen NULL y UNA acta con el origen de cada línea.)*

- [x] **T16** Sincronizar README y specs. (@auditor)
  **Hecho cuando:** documentos vigentes describen origen por línea. *(Evidencia: README actualizado; `openspec.yaml` ya actualizado en T10; las specs maestras no describen el origen único de cabecera.)*

- [x] **T17** Aceptación y commit local; archivo del paquete. (@auditor)
  **Hecho cuando:** aprobación humana y commit hechos; sin merge. *(Aceptado 2026-10-12; commit local en `feature/p2-migracion-unidades-y-sdd`, sin merge.)*
