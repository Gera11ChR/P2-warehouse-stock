# Tareas — ETAPA 1/3: ACTIVIDADES (Registro)

**Paquete:** `2026-10-actividades-unidad` · **Fase SDD:** 6 (Tareas) · Trazabilidad: `proposal.md` ⇄ `spec.md` (REQ-ACT-NNN) ⇄ `plan.md` ⇄ esta lista.

## Reglas operacionales (inquebrantables)

1. **Parada obligatoria:** al terminar CADA tarea (T1..T12) el Orquestador se detiene por completo, reporta evidencia y pide confirmación al humano antes de continuar.
2. **Backend-First:** T2-T7 (BD → API → contrato) deben cerrarse antes de T8. El frontend (T8-T10) permanece bloqueado hasta el PASS de T7.
3. **Contrato:** T7 valida `spec.md` ⇄ OpenAPI ⇄ Pydantic y congela el contrato en `.openspec.yaml` (`contract.frozen: true`) antes de escribir frontend.
4. **Sin refactor ni limpieza** de código ajeno (Fase 7). Solo `@auditor` reporta código muerto (Fase 8); borrarlo requiere tarea aprobada.
5. Ninguna línea en `backend/` o `frontend/` cambia antes de la aprobación humana de este paquete.

## Resumen

| Tarea | Fase | Agente(s) | Capa | Depende de |
| --- | --- | --- | --- | --- |
| T1 | 4 | `@arq-reviewer` | Spec/Plan | — |
| T2 | 7 | `@dba-guard` + `@coder` | BD | T1 |
| T3 | 7 | `@tester` | BD | T2 |
| T4 | 7 | `@coder` | Backend | T3 |
| T5 | 7 | `@sec-ops` + `@coder` | Backend | T4 |
| T6 | 7 | `@tester` | Backend | T5 |
| T7 | 7 | `@qa-agent` | Contrato | T6 |
| T8 | 7 | `@state-agent` | Frontend | T7 (PASS) |
| T9 | 7 | `@form-agent`, `@ui-agent`, `@ux-agent` | Frontend | T8 |
| T10 | 7 | `@tester` | Frontend | T9 |
| T11 | 8 | `@auditor`, `@tester`, `@qa-agent`, `@arq-reviewer` | Validación | T10 |
| T12 | 9 | Orquestador (+ `@auditor` verifica condiciones) | Archivo | T11 |

---

### T1 — Clarificación y visto bueno arquitectónico (Fase 4)
- **Agente:** `@arq-reviewer`
- **REQ:** todos (REQ-ACT-001..020)
- **Hacer:** revisar `spec.md` y `plan.md` contra `docs/constitution.md` y `.agents.md`; clasificar Dominio vs. Bug; resolver C-1..C-6 de `spec.md` §9 (el humano decide); cotejar spec ⇄ plan ⇄ tasks (Zero-Drift); confirmar que no hay conflicto con REQ-UNI-005 ni con las specs maestras.
- **Hecho cuando:** hay informe sin ambigüedades abiertas; los cambios resultantes están aplicados a `proposal.md`/`spec.md`/`plan.md`/`tasks.md` con aprobación del humano; `.openspec.yaml` marca `fase_4_clarificacion: completada`.
- **Estado:** COMPLETADA (pendiente de confirmación del humano para pasar a T2).
- **PARADA.**

### T2 — Migración 0029: tabla, trigger y Stored Functions
- **Agentes:** `@dba-guard` (diseño/revisión) + `@coder` (implementación)
- **REQ:** 008, 009, 010, 011, 012, 015, 020
- **Hacer:** crear `backend/alembic/versions/0029_actividades_unidad.py` según plan §2 (tabla `actividades_reportes`, CHECKs, UNIQUE, FKs RESTRICT, índice, trigger `tg_ledger_actividades_inmutable`, `fn_crear_actividad`, `fn_actividad_pendiente` o consulta equivalente decidida por `@dba-guard`, `downgrade()`); regenerar `backend/db/ddl.sql` con `backend/scripts/generar_ddl.py`; agregar `actividades_reportes` a `TABLAS_DOMINIO` en `backend/tests/conftest.py`.
- **Hecho cuando:** `alembic upgrade head` y `downgrade -1` + `upgrade head` se ejecutan sin error en `p2` y `p2_test`; `generar_ddl.py --verificar` pasa; `fn_crear_actividad` usa `FOR UPDATE` y advisory lock; ninguna tabla preexistente fue modificada; `@dba-guard` emite APROBADO.
- **PARADA.**

### T3 — Pruebas de base de datos
- **Agente:** `@tester`
- **REQ:** 008, 009, 010, 011, 012, 015, 020
- **Hacer:** `backend/tests/test_migracion_0029.py` (upgrade/downgrade en esquema aislado vía `helpers/migraciones.py`); pruebas SQL en `backend/sql_tests/` para: folio correlativo, folio sin huecos, concurrencia de 2 sesiones sobre el mismo seguimiento (una gana, la otra «ya tiene una actividad»), inmutabilidad (UPDATE/DELETE → P0001), snapshot congelado ante cambio posterior de `valor_unitario`, seguimiento ABIERTO rechazado, seguimiento de otra Unidad rechazado, seguimiento con consumo vacío aceptado, evento `ACTIVIDAD_CONFIRMADA` en `auditoria_eventos`, `inventario_equipos`/`seguimientos`/`actas_reportes` sin cambios.
- **Hecho cuando:** todas las pruebas pasan (100 %) y la suite backend previa sigue en verde; evidencia de salida de `pytest` registrada.
- **PARADA.**

### T4 — Modelos, DTOs y servicio
- **Agente:** `@coder` (valida con `@dba-guard` la alineación ORM ⇄ DDL)
- **REQ:** 002, 003, 004, 008, 009, 010, 016, 018, 019
- **Hacer:** `backend/app/models/actividad.py`, `backend/app/schemas/actividad.py` (DTOs exactos del plan §3.2, `extra="forbid"`), `backend/app/services/actividades.py` (lecturas), wrapper `crear_actividad` en `services/transaccional.py` y nuevas entradas de `_mapear_raise_exception` (plan §3.3). Cero aritmética de stock/valor en Python; folio formateado solo como presentación.
- **Hecho cuando:** `ruff`/`mypy` (si el repo los usa) sin errores nuevos; los modelos coinciden con el DDL; los DTOs coinciden campo a campo con plan §3.2; errores SQL mapeados a 404/409/422 (nunca 500).
- **PARADA.**

### T5 — Router, RBAC y seguridad de entrada
- **Agentes:** `@sec-ops` (controles y revisión) + `@coder` (implementación)
- **REQ:** 013, 014, 015, 019
- **Hacer:** `backend/app/api/v1/actividades.py` con `GET /pendiente`, `POST ""`, `GET ""` bajo `/equipos/{equipo_id}/actividades`; registrar en `app/main.py`; `assert_authenticated`, `prechequear_equipo` (404 antes de 403) y `assert_equipo_access`; validadores de caracteres de control y límites; docstrings OpenAPI.
- **Hecho cuando:** los 3 endpoints aparecen en `/openapi.json` con los DTOs del plan; `@sec-ops` confirma default-deny, `extra="forbid"`, ausencia de secretos y de mass assignment (folio/fecha/materiales/usuario no aceptados).
- **PARADA.**

### T6 — Pruebas de API
- **Agente:** `@tester`
- **REQ:** 001-004, 008-016, 019
- **Hacer:** `backend/tests/test_actividades.py` con una prueba por requisito (`test_req_act_NNN_*`) que aserte respuesta HTTP **y** estado de BD: GET pendiente con/sin seguimiento, POST 201 (folio `R0001`, fecha, snapshot), 409 (abierto/duplicado/reintento), 404 (unidad/seguimiento ajeno), 403 (`client_sin_scope`), admin e integrante, 422 (extras, límites, vacíos, caracteres de control, IDs inválidos), 400 (ID fuera de INT4), POST concurrente, GET lista ordenada, inventario intacto.
- **Hecho cuando:** pytest completo pasa al 100 % y cada REQ-ACT de backend tiene al menos una prueba que pasa.
- **PARADA.**

### T7 — Compuerta de contrato (congelación Backend → Frontend)
- **Agente:** `@qa-agent`
- **REQ:** 018, 019 (y verificación transversal)
- **Hacer:** validación independiente `spec.md` ⇄ plan §3.2 ⇄ `/openapi.json` ⇄ Pydantic: campos faltantes/inventados, nomenclatura, tipos, métodos y códigos HTTP; Zero-Drift Scan; ejecutar la suite backend completa; escribir `openapi.snapshot.json` del paquete; actualizar `.openspec.yaml` (`contract.frozen: true`, `openapi_snapshot`).
- **Hecho cuando:** salida **PASS** con cumplimiento de contrato 100 %; en caso de **FAIL** se emite el informe estructurado (Finding → Severity → File/Line → Violated Rule → Evidence → Recommended Correction) y se vuelve a T4-T6. **El frontend sigue bloqueado hasta el PASS.**
- **PARADA.**

### T8 — Tipos, servicio, hooks y esquemas (frontend)
- **Agente:** `@state-agent`
- **REQ:** 002, 003, 016, 017, 018
- **Hacer:** `types.ts` (tipos del contrato congelado y etiqueta `ACTIVIDAD_CONFIRMADA`), `services/actividades.ts`, `hooks/useActividades.ts`, claves e invalidadores en `queryKeys.ts` (pendiente, lista, auditoría), `schemas/actividad.ts` (zod). Sin lógica de stock/valor local; sin campos fuera del contrato.
- **Hecho cuando:** `tsc` sin errores; tipos idénticos al snapshot de OpenAPI; regla de invalidación post-mutación implementada; pruebas de servicio/hook (vitest) en verde.
- **PARADA.**

### T9 — Pestaña y formulario ACTIVIDADES
- **Agentes:** `@form-agent` (workflow/validación), `@ui-agent` (componentes), `@ux-agent` (ergonomía/estados)
- **REQ:** 001, 005, 006, 007, 017 (y presentación de 002, 003, 004, 009)
- **Hacer:** `components/ActividadesPanel.tsx` (+ subcomponentes) y pestaña `'actividades'` en `pages/InventarioPorEquipos.tsx` tras CONSUMO; materiales consumidos de solo lectura; Fecha «Automatizado» (hora local tras confirmar); Vehículo, Cliente(s), Dirección(es) con los placeholders exactos; celdas de actividad con «+ Agregar» (máx. 30); Comentarios (enviar `comentarios: null` cuando el campo quede vacío, observación T7); «Confirmar» con `ConfirmDialog`; estados pendiente/éxito (folio)/rechazado con datos conservados; nomenclatura «Unidad».
- **Hecho cuando:** el flujo completo funciona contra el backend real (verificación manual guiada) y los estados del REQ-ACT-017 son visibles; `@ux-agent` y `@ui-agent` emiten conformidad; `tsc` y `vite build` sin errores ni warnings.
- **PARADA.**

### T10 — Pruebas de frontend
- **Agente:** `@tester`
- **REQ:** 001, 005, 006, 007, 017
- **Hacer:** vitest para `ActividadesPanel` (pestaña visible, sin seguimiento pendiente → «Confirmar» deshabilitado, placeholders exactos, «+ Agregar», límite de celdas, descarte de vacías, éxito con folio, error del backend), hooks, servicio y schema; seguir el patrón `vi.mock('../../services/*')` + `QueryClientProvider` + `ToastProvider`.
- **Hecho cuando:** vitest completo pasa al 100 % (incluida la suite previa).
- **PARADA.**

### T11 — Validación y auditoría (Fase 8)
- **Agentes:** `@auditor` (Drift Report), `@tester` (suite final y Matriz de Trazabilidad), `@qa-agent` (conformidad final), `@arq-reviewer` (visto bueno arquitectónico)
- **REQ:** todos
- **Hacer:** Drift Report (Entity/Logic/Exception/Traceability, incluido código muerto, solo reporte); Matriz de Trazabilidad REQ-ACT-001..020 con prueba que pasa y aserta HTTP + BD; regresión completa (pytest, vitest, build, `openspec validate --specs --strict`); verificación de que Etapas 2 y 3 no fueron adelantadas.
- **Hecho cuando:** `@auditor` = APPROVED; `@qa-agent` = PASS (cobertura de trazabilidad 100 %); `@arq-reviewer` otorga visto bueno; el humano aprueba el cierre.
- **PARADA.**

### T12 — Evolución y archivado (Fase 9)
- **Agente:** Orquestador (condiciones de archivado verificadas por `@auditor`)
- **Hacer:** promover REQ-ACT y la regla `actividades_registro` a `openspec/specs/` y `openspec/openspec.yaml`: `domain_rules` (`mandatory_functions`: `fn_crear_actividad`; eventos: `ACTIVIDAD_CONFIRMADA`; glosario: Actividad, Folio) **y** `paths`/`components` con los 3 endpoints y DTOs de actividades tomados del `openapi.snapshot.json`; mover el paquete a `openspec/changes/archive/2026-10-actividades-unidad/`; no registrar en `.agents.md` enlaces al paquete archivado.
- **Hecho cuando:** el paquete está en `archive/`, las specs maestras actualizadas y `openspec validate --specs --strict` pasa.
- **PARADA.** Solo entonces el humano solicita el SDD de la **Etapa 2**.

---

## Trazabilidad REQ → Tarea

| REQ | Implementa | Verifica |
| --- | --- | --- |
| 001 | T9 | T10 |
| 002, 003, 004 | T2, T4, T9 | T3, T6, T10 |
| 005, 006, 007 | T8, T9 | T10 |
| 008, 009, 010 | T2 | T3, T6 |
| 011 | T2 | T3, T6 |
| 012 | T2 | T3, T6 |
| 013, 014 | T4, T5 | T6 |
| 015 | T2 | T3, T6 |
| 016 | T4, T5 | T6 |
| 017 | T8, T9 | T10 |
| 018, 019 | T4, T5 | T7 |
| 020 | T2 | T3, T11 |
