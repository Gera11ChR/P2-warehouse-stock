# Tareas — ETAPA 3/3: REFERENCIA DE MATERIALES POR UNIDAD

**Paquete:** `2026-10-referencia-materiales-unidades` · **Fase SDD:** 6 (Tareas) · **Estado:** redactadas, pendientes de aprobación del humano.
Derivadas de `spec.md` (`REQ-REF-001..018`) y `plan.md`. Zero-Drift (`.agents.md` §4): cada tarea cita los REQ que implementa o verifica.

## Reglas inquebrantables

1. **PARADA OBLIGATORIA tras cada tarea:** el orquestador resume la evidencia, registra `- **Estado:** COMPLETADA (...)` en esta tarea y espera la confirmación explícita del humano antes de iniciar la siguiente.
2. **Backend-First estricto:** T2-T7 (DB, servicio, router, pruebas y congelación del contrato) preceden a T8-T10 (frontend). Ningún archivo de `frontend/` se modifica antes de que T7 esté completada.
3. **Contrato congelado desde T7** (`frozen: true`, sha256 registrado en `.openspec.yaml`): solo un RFC aprobado puede cambiarlo. Antes de T7 el `openapi.snapshot.json` es un borrador.
4. **Sin refactor ajeno:** no se limpia ni reformatea código fuera del alcance de cada tarea; los hallazgos ajenos se registran como deuda.
5. **DDL solo en T2** (migración `0030`, tabla `referencia_materiales` y su trigger). Ninguna otra tarea altera el esquema.
6. **Aislamiento (REQ-REF-011):** no se modifican `app/api/v1/{equipos,catalog,inventario,fibra,actividades,reportes,reportes_actividades,seguimientos,movimientos}.py`, sus servicios ni modelos. Cambios permitidos fuera de archivos nuevos: registrar el router en `app/main.py`, las listas `TRUNCATE` de `backend/tests/conftest.py` y `backend/sql_tests/conftest.py`, los asserts de cabeza de migración estrictamente necesarios, `frontend/src/{types.ts,hooks/queryKeys.ts}` y `frontend/src/pages/InventarioPorEquipos.tsx` (cambio mínimo y localizado).
7. **No se consultan paquetes archivados** (`.agents.md` §2); las specs maestras se leen solo como punto de integración.
8. **Nomenclatura:** «Unidad» e «Inventario FO» en UI; `equipo`/`equipo_id` solo como identificadores técnicos (REQ-UNI-005).
9. **Hechos verificables:** ninguna tarea se marca completada sin ejecutar sus pruebas; los resultados se citan literalmente.
10. **Entorno de pruebas backend:** cargar `backend/.env`, `PGPASSWORD`, `P2_ADMIN_DATABASE_URL` y `P2_TEST_DATABASE_URL`; no ejecutar dos suites simultáneas contra `p2_test`.

## Definición de Done del paquete

`@auditor` = APPROVED; `@qa-agent` = PASS (trazabilidad 100 %); `@arq-reviewer` otorga visto bueno; el humano aprueba el cierre; suites backend y frontend al 100 %; `tsc -b`, lint y build sin errores ni warnings; `mypy` limpio; `openspec validate --specs --strict` con 0 violaciones; **verificación visual de T9 aprobada con Playwright Chromium** (390 px y 1280 px, árbol semántico, sin overflow, consola limpia).

---

## FASE 4 — CLARIFICACIÓN

### T1 — Clarificación de la especificación
- **Agente:** `@arq-reviewer`
- **REQ:** todos
- **Hacer:** revisar `proposal.md`, `spec.md` y `plan.md` contra la Constitución y `.agents.md`; detectar ambigüedades, conflictos de nomenclatura e invariantes en riesgo; dictaminar sobre C-1..C-13 (en particular C-2, C-3, C-4, C-12) y proponer correcciones; registrar `fase_4_clarificacion: completada` en `.openspec.yaml`.
- **Hecho cuando:** `spec.md` y `plan.md` sin ambigüedades abiertas; el humano ratifica o corrige cada clarificación y aprueba el paquete.
- **PARADA.**

---

## FASE 7 — IMPLEMENTACIÓN BACKEND

### T2 — Migración `0030` (DDL, trigger y modelo de datos)
- **Agente:** `@dba-guard`
- **REQ:** 011, 012, 018
- **Hacer:** crear `backend/alembic/versions/0030_referencia_materiales_unidad.py` (`revision="0030"`, `down_revision="0029"`) con la tabla `referencia_materiales` (PK compuesta, FK `RESTRICT`, `CHECK (cantidad_semanal > 0)`), `fn_auditar_referencia_materiales` y `tg_auditar_referencia_materiales` (INSERT/UPDATE/DELETE, sin evento si la cantidad no cambia) y un `downgrade()` que solo elimina los objetos del paquete. Sin cambios a tablas preexistentes.
- **Hecho cuando:** `alembic upgrade head` y `downgrade -1` funcionan en `p2_test`; `@dba-guard` confirma integridad, concurrencia y reversibilidad.
- **PARADA.**

### T3 — Pruebas de migración y `sql_tests`
- **Agente:** `@tester`
- **REQ:** 011, 012, 018
- **Hacer:** `backend/tests/test_migracion_0030.py` (upgrade → downgrade → upgrade, constraints, trigger, eventos preservados, tablas preexistentes intactas); `backend/sql_tests/test_fase_referencia.py` (PK/FK/CHECK, `RESTRICT`, 3 eventos de auditoría con `app.actor`, sin evento por UPDATE sin cambio, sin efecto sobre tablas de negocio); añadir `referencia_materiales` a las listas `TRUNCATE` de las dos `conftest.py`; ajustar solo los asserts de cabeza de migración que lo requieran y registrarlo.
- **Hecho cuando:** `pytest backend/tests/test_migracion_0030.py` y `pytest backend/sql_tests` al 100 %; suite completa sin regresión de las migraciones previas.
- **PARADA.**

### T4 — Modelo ORM, esquemas y servicio
- **Agente:** `@coder` (con consulta a `@sec-ops` para los esquemas)
- **REQ:** 005, 006, 007, 008, 009, 010, 011
- **Hacer:** `app/models/referencia.py`, `app/schemas/referencia.py` (`extra="forbid"`, `CantidadMovimiento`, 1..50 líneas) y `app/services/referencia.py` (listar con JOIN al catálogo activo y orden `descripcion, material_id`; alta todo-o-nada; modificar y eliminar con `FOR UPDATE`; traducción de `IntegrityError` a 409; errores `BusinessRuleError` con códigos y `coordinates`). Sin Stored Functions de stock ni escritura fuera de `referencia_materiales`.
- **Hecho cuando:** `mypy` limpio sobre los módulos nuevos; las pruebas de servicio de T6 pueden escribirse sobre esta API.
- **PARADA.**

### T5 — Router, registro y revisión de seguridad
- **Agentes:** `@coder`, `@sec-ops`
- **REQ:** 006-010, 015
- **Hacer:** `app/api/v1/referencia.py` (GET/POST/PATCH/DELETE con la precedencia 422 → 404 → 403 → resto, `set_config('app.actor', …)`, una transacción por petición) y registrarlo en `app/main.py`; `@sec-ops` revisa default-deny, alcance por Unidad, `extra="forbid"`, errores sin SQL y ausencia de efectos fuera de la tabla.
- **Hecho cuando:** `@sec-ops` aprueba; el OpenAPI vivo expone las cuatro operaciones; `mypy` limpio.
- **PARADA.**

### T6 — Pruebas de API (HTTP + BD)
- **Agente:** `@tester`
- **REQ:** 005-012, 015
- **Hacer:** `backend/tests/test_referencia.py` con pruebas que aserten HTTP y BD por SQL directo: listado ordenado y con datos vivos, material inactivo oculto y reaparición, alta todo-o-nada, todas las validaciones (422/404/409/400), carrera de altas, modificar, eliminar, aislamiento (403, 404 antes de 403, Unidad inactiva, `X-Actor`), snapshot de tablas de negocio intacto, listado sin eventos y 3 eventos de auditoría con valores previos y nuevos, rollback sin evento. Una prueba `test_req_ref_NNN_*` por requisito.
- **Hecho cuando:** `pytest` completo del backend y `sql_tests` al 100 %; `mypy` limpio; sin regresión de Etapas 1 y 2.
- **PARADA.**

### T7 — Congelación del contrato
- **Agente:** `@qa-agent`
- **REQ:** 015
- **Hacer:** validar de forma independiente el backend contra `spec.md`; regenerar `openapi.snapshot.json` desde `app.openapi()` restringido a las cuatro operaciones y sus esquemas; calcular el sha256; marcar `contract.frozen: true` en `.openspec.yaml` y registrar el hash; documentar hallazgos.
- **Hecho cuando:** `@qa-agent` = PASS; contrato congelado; **el frontend queda desbloqueado**.
- **PARADA.**

---

## FASE 7 — IMPLEMENTACIÓN FRONTEND (solo tras T7)

### T8 — Estado: tipos, servicio, claves y hooks
- **Agente:** `@state-agent`
- **REQ:** 004, 005, 013, 014, 017
- **Hacer:** tipos en `types.ts` espejo del contrato congelado; `services/referencia.ts`; `queryKeys.referencia(equipoId)` con invalidación acotada; `hooks/useReferencia.ts` (consulta y mutaciones con toasts); hooks de solo lectura del origen del selector («Inventario General» desde secciones GENERAL activas sin duplicar `material_id`; «Inventario FO» desde `listFibraStock`); sin recalcular datos en el cliente.
- **Hecho cuando:** `tsc -b` y lint limpios; pruebas de servicio y hooks pasan; ninguna invalidación toca inventario, catálogo, reportes ni actividades.
- **PARADA.**

### T9 — Interfaz y verificación visual con Playwright Chromium
- **Agentes:** `@ui-agent`, `@ux-agent`, `@form-agent`
- **REQ:** 001, 002, 003, 004, 013, 014, 016
- **Hacer:** botón «Referencia» en el extremo derecho de la barra de subsecciones (Consulta y Configuración) con `aria-expanded`; `ReferenciaPanel`, `ReferenciaAgregarForm` y `MaterialSelect` según `plan.md` §6.2; estados de carga, error y vacío; modo lectura en Consulta y acciones en Configuración; textos «Unidad» e «Inventario FO»; aviso «La cantidad no afecta el inventario». **Verificación visual obligatoria** según `plan.md` §6.3, con Playwright Chromium de `frontend/` contra `http://localhost:5173` y el backend real en `:8000`:
  1. flujo completo en Consulta (solo lectura) y Configuración (agregar, modificar, eliminar con confirmación);
  2. snapshot del árbol semántico del DOM de cada estado;
  3. medición de overflow horizontal a **390 px** y **1280 px** (`scrollWidth <= innerWidth`);
  4. consola del navegador sin errores ni warnings y sin respuestas HTTP inesperadas;
  5. capturas e informe en `/tmp/opencode/visual/`; datos de prueba eliminados y procesos detenidos al terminar.
- **Hecho cuando:** `tsc -b`, lint y `npm run build` sin errores ni warnings; vitest completo en verde; **la verificación visual pasa en ambos viewports con evidencia citada**; `@ux-agent` y `@form-agent` sin objeciones.
- **PARADA.**

### T10 — Pruebas de frontend
- **Agente:** `@tester`
- **REQ:** 001-004, 013, 014, 016, 017
- **Hacer:** pruebas vitest de botón (presencia en Consulta/Configuración, ausencia en CONSUMO/ACTIVIDADES, `aria-expanded`), panel (columnas, vacío, carga, error con reintento, solo lectura en Consulta), cambio de Unidad, formulario (origen → material dependiente, exclusión de materiales ya presentes, validación, varias líneas, conservar datos ante rechazo), modificar, eliminar con confirmación, invalidación acotada, servicio y hooks; repetir la verificación visual de T9 como regresión final sobre el árbol completo.
- **Hecho cuando:** vitest completo y `tsc -b`/lint/build al 100 % sin warnings; verificación visual repetida sin hallazgos.
- **PARADA.**

---

## FASE 8 — VALIDACIÓN Y AUDITORÍA

### T11 — Validación y auditoría
- **Agentes:** `@auditor` (Drift Report), `@tester` (suite final y Matriz de Trazabilidad), `@qa-agent` (conformidad final), `@arq-reviewer` (visto bueno arquitectónico)
- **REQ:** todos
- **Hacer:** Drift Report (Entity/Logic/Exception/Traceability, código muerto, solo reporte); Matriz de Trazabilidad `REQ-REF-001..018` con pruebas que pasan (HTTP + BD en backend); regresión completa (`pytest`, `sql_tests`, vitest, `tsc`/build/lint, `mypy`, `openspec validate --specs --strict`); contratos de las Etapas 1 y 2 sin drift; verificación de que el paquete no tocó inventarios, catálogo ni archivos de aislamiento (REQ-REF-011) y de que no se adelantó trabajo fuera del alcance (sin conversiones de U.M.).
- **Hecho cuando:** `@auditor` = APPROVED; `@qa-agent` = PASS (cobertura de trazabilidad 100 %); `@arq-reviewer` otorga visto bueno; el humano aprueba el cierre.
- **PARADA.**

---

## FASE 9 — EVOLUCIÓN Y ARCHIVADO

### T12 — Promoción y archivado
- **Agente:** Orquestador (condiciones de archivado verificadas por `@auditor`)
- **REQ:** todos
- **Hacer:** promover `REQ-REF-001..018` a `openspec/specs/003_inventory_dashboard/spec.md` (formato `Requirement`/`Scenario`, «SHALL»); añadir a `openspec/openspec.yaml` la regla de dominio `referencia_materiales` (tabla propia, sin efecto sobre inventarios, auditoría, límites) y los `paths` de las cuatro operaciones tomados del `openapi.snapshot.json`, sin duplicar `components` existentes; documentar la migración `0030` en el README si corresponde; mover el paquete a `openspec/changes/archive/2026-10-referencia-materiales-unidades/`; no registrar enlaces al paquete archivado en `.agents.md`.
- **Hecho cuando:** paquete en `archive/`, specs maestras actualizadas, `openspec validate --specs --strict` en verde y árbol de Git limpio.
- **PARADA.** Cierra la Etapa 3.

---

## Trazabilidad REQ → Tarea

| REQ | Implementa | Verifica |
| --- | --- | --- |
| 001, 002, 003, 016 | T9 | T9, T10 |
| 004 | T8, T9 | T10 |
| 005 | T4, T5 | T6 |
| 006, 007, 008, 009 | T4, T5 | T6 |
| 010 | T4, T5 | T6 |
| 011 | T2, T4 | T3, T6 |
| 012 | T2 | T3, T6 |
| 013, 014 | T8, T9 | T9, T10 |
| 015 | T5 | T6, T7 |
| 017 | T8 | T10 |
| 018 | T2 | T3, T11 |
