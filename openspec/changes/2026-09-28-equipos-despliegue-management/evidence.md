# FASE 11 — Final Evidence

**Change:** `2026-09-28-equipos-despliegue-management`
**Fecha:** 2026-09-28
**Estado:** Evidencia consolidada — lista para aceptación humana (FASE 12)

---

## 1. Resumen de verificación

| Gate | Resultado |
| ---- | --------- |
| Backend tests (`pytest tests/ -q`) | **192/192 PASS** (130 preexistentes + 62 nuevos EARS-mapped) |
| Frontend tests (`vitest run`) | **38/38 PASS** (8 archivos) |
| Frontend build (`tsc -b && vite build`) | 0 errores TS, 0 warnings, 2076 módulos |
| Frontend lint (`eslint .`) | 0 errores / 0 warnings |
| `openspec validate --changes` | 1 passed, 0 failed |
| `openspec validate 2026-09-28-equipos-despliegue-management` | válido (`skip_specs: true`) |
| npm audit (`--omit=dev`) | 0 vulnerabilidades |
| Migración 0014 | aplicada en `p2`; ciclo downgrade/upgrade verificado pre-escritura |
| Zero-Drift QA (FASE 8) | 39/39 paths frontend↔OpenAPI MATCH; 45/45 aserciones flujo vivo |
| DApp Operational Acceptance (FASE 9) | 6/6 workflows operativos reproducidos; 8/8 principios con evidencia |

---

## 2. Matriz de trazabilidad (EARS → Implementación → Test → Evidencia)

| EARS | Implementación (backend / frontend) | Test automatizado | Evidencia viva (FASE 9) | Resultado |
| ---- | ----------------------------------- | ----------------- | ----------------------- | --------- |
| REQ-CATALOG-001 | `PUT /catalogo/categorias/{id}`, `PUT /catalogo/um/{id}` (`api/v1/catalog.py:160,216`) / `CatalogManagementPanel.tsx` | `test_catalogo_admin.py` (:40,:73,:148,:171) | rename 200 + duplicado 409 + listados reflejan cambio | ✅ |
| REQ-CATALOG-002 | soft-delete (`services/catalogo.py:281,351`) / ConfirmDialog | `test_catalogo_admin.py` (:92,:203,:266) | keep AND remove de categoría sin materiales; históricos legibles | ✅ |
| REQ-CATALOG-003 | triggers `tg_auditar_categoria`/`tg_auditar_um` + `app.actor` | `test_catalogo_admin.py` (audit asserts :62,:114,:192,:220) | eventos 128–132 con actor `demo-operador` y contexto anterior/nuevo | ✅ |
| REQ-FO-001 | `GET /inventario/secciones/transferibles` + routing `secciones.tipo` (0014) / `Transferencias.tsx` dropdowns | `test_fo_transferencias.py` (:64,:99,:263) | 3 opciones transferibles; TEAMS desde PAQUETE, DEVOL a EN_USO | ✅ |
| REQ-FO-002 | ramas FO en `fn_procesar/cancelar_movimiento` (0014) | `test_fo_transferencias.py` (:130,:158,:198,:232,…) | conservación 60+15+25=100; `modulo_fo` en auditoría | ✅ |
| REQ-TEAM-001 | código/descripción sin columna configurable; `extra=forbid` / `ConfigLocalForm.tsx` solo-lectura | `test_config_local.py` (:113,:373) | PATCH con codigo/descripcion → 422; valores del maestro | ✅ |
| REQ-TEAM-002 | `stock_actual` excluido del PATCH (422); stock solo por movimientos | `test_config_local.py` (:113) | PATCH `{stock_actual}` → 422; stock 30 intacto | ✅ |
| REQ-TEAM-003 | `PATCH /equipos/{id}/inventario/{material_id}` (upsert config) / pestaña Configuración | `test_config_local.py` (:74,:130,…) | local gana (mínimo 10, categoría, U.M.); fallback maestro | ✅ |
| REQ-TEAM-004 | tabla `equipo_material_config` separada; maestro intacto | `test_config_local.py` (:194) | `GET /catalogo/{id}` conserva categoría/U.M./mínimo maestros | ✅ |
| REQ-DEPLOY-001 | `POST /equipos/{id}/despliegues` → `fn_crear_despliegue` / `DesplieguePanel.tsx` | `test_despliegues.py` (:90,:148,:486,:530,:615) | 201 ABIERTA; segundo abierto 409; aislamiento 403 | ✅ |
| REQ-DEPLOY-002 | items en `despliegue_items` (fn_crear, 0014:284) | `test_despliegues.py` (:90,:396) | items con cantidad_tomada registrados | ✅ |
| REQ-DEPLOY-003 | `despliegues.observaciones` + `observaciones_cierre` | `test_despliegues.py` (:117) | observaciones capturadas y devueltas | ✅ |
| REQ-DEPLOY-004 | `POST .../cerrar` con sobrantes 0..tomada (fn_cerrar) / `DespliegueCierreForm` | `test_despliegues.py` (:171,:300-372,:446) | sobrante 8 registrado; línea omitida = 0; 400/422 inválidos | ✅ |
| REQ-DEPLOY-005 | ajuste automático en PG + auditoría por línea | `test_despliegues.py` (:202,:411,:561,:642) | stock 30→18 (=30−(20−8)); doble cierre 409; carrera → un ganador | ✅ |
| REQ-DEPLOY-006 | eventos `DESPLIEGUE_CREADO`/`DESPLIEGUE_CERRADO` con `p_usuario` | `test_despliegues.py` (:242) | eventos 138/139 con actor y consumos | ✅ |
| REQ-VIEW-001 | `GET /equipos/{id}/inventario` read-only + aislamiento / pestaña Consulta sin acciones | `test_equipos.py::test_REQ_VIEW_001…`, `test_config_local.py::test_SEC_003…` | 200 integrante; 403 no-integrante; 200 admin | ✅ |
| REQ-REPORT-001 | `GET /reportes/despliegues` exclusivo / `Reportes.tsx` sin KPI/catálogo | `test_reportes.py` (:109,:203,…) | JSON filtrado por equipo/fechas; grep KPI=0 | ✅ |
| REQ-REPORT-002 | CSV stream + sanitización OWASP / `descargarReporteCsv` | `test_reportes.py` (:150,:246) | CSV 17 columnas; `=HYPERLINK(...)` → `'=` (vivo) | ✅ |

**Cobertura: 18/18 EARS con implementación + test explícito + evidencia viva.**

---

## 3. Veredictos de revisión (todas las fases)

| Fase | Agente | Veredicto |
| ---- | ------ | --------- |
| FASE 0/1 | @arq-reviewer, @auditor, @sec-ops, @dba-guard | Aprobado con enmiendas (ejecutadas) + 6 decisiones humanas ratificadas |
| FASE 2 | @dba-guard | Migración 0014 verificada (downgrade/upgrade, 129 tests) |
| FASE 3 | @coder + @auditor + @sec-ops | Hallazgos V1–V5 corregidos y verificados |
| FASE 4 | @tester | 62 tests nuevos; 192/192 |
| FASE 5 | @arq-reviewer + @auditor | **APPROVE FREEZE** (sign-off.md) |
| FASE 8 | @qa-agent | **Zero-Drift PASS** (39/39 contrato, 45/45 flujo vivo) |
| FASE 9 | @qa-agent | **DApp Acceptance PASS** (6 workflows, 8 principios) |
| FASE 10 (seguridad) | @sec-ops | **CONDITIONAL** — aprobable con firma de desviaciones D2/D3 |
| FASE 10 (arquitectura) | @arq-reviewer | **APPROVE** (2 hallazgos LOW no bloqueantes) |
| FASE 10 (compliance) | @auditor | **CONDITIONAL → resuelto** (D-5 spec-maestra corregido en `openspec.yaml`; `openspec validate` 1/0) |

---

## 4. Registro de desviaciones (documentadas, no bloqueantes)

| ID | Desviación | Severidad | Estado |
| -- | ---------- | --------- | ------ |
| V4 | `MOVIMIENTO_CANCELADO` atribuido a `CURRENT_USER` (preexistente) | LOW | Documentada; flujos nuevos atribuyen X-Actor |
| SEC-014 | MFA sin cablear para operaciones privilegiadas (Const 3.3) | MEDIUM (vs Constitución) | Registrada; requiere firma humana en FASE 12 |
| X-Actor | Identidad client-asserted (header) sin firma | HIGH si se expone fuera de red confiable | Registrada; requiere reverse-proxy antes de exposición |
| D-1 | Orden de locks en loops de movimientos sin ORDER BY (heredado del freeze GENERAL) | LOW | Detectado; PG aborta sin corrupción (4.3); mejora futura |
| D-2 | Alta de categoría/U.M. sin evento de auditoría (triggers UPDATE/DELETE; REQ-CATALOG-003 cubre modify/remove) | LOW | Conforme al spec congelado; mejora futura |
| N4 | `pip check`: `h11` desactualizado en venv (higiene) | LOW | Limpieza de entorno programada, no afecta el repo |
| D-6 | `docs/Old_flujo_operacional.md` untracked (artefacto del usuario) | INFO | Recomendado mover a `docs/archive/` |
| start_index | No declarado como `required` en OpenAPI (siempre devuelto) | LOW | Documental |

---

## 5. DoD — Constitution 7.2

1. ✅ Suites automatizadas 100% (192 backend + 38 frontend)
2. ✅ Builds sin errores ni warnings de tipos
3. ✅ `openspec validate --changes` 1/0; `--specs --strict` N/A (`skip_specs: true`)
4. ✅ Invariantes de dominio probadamente no violados (CHECKs PG + tests de regresión)

---

## 6. Cobertura de evidencia exigida por FASE 11 (flujo)

- ✅ Database tests (`test_esquemas`, migración 0014 aplicada y validada)
- ✅ API tests (62 nuevos + 130 regresión)
- ✅ Frontend tests (38 vitest)
- ✅ Integration tests (concurrencia, rollback, aislamientos)
- ✅ E2E (FASE 9 flujo operativo completo por API viva)
- ✅ DApp acceptance (FASE 9 PASS)
- ✅ Security checks (SEC-001..013 PASS, desviaciones registradas)
- ✅ Migration validation (upgrade/downgrade + smoke)
- ✅ Regression validation (TEAMS/DEVOL GENERAL byte-idéntico; suites preexistentes verdes)
- ✅ Architecture validation (FASE 10 APPROVE)
