# Tareas: 2026-10-purga-legacy-fo

> Secuencial por fases SDD. **Backend-First:** T6 (frontend) queda bloqueada hasta que T5 registre la Congelación Contractual (OpenAPI sin deriva más allá de `description`). Cualquier cambio de contrato posterior invalida la congelación.
> Cada tarea cita los `RF-n` de `spec.md` que cubre y el agente responsable. Los agentes no amplían alcance: lo no listado en `spec.md` §4 (Fuera de Alcance) no se implementa.
> **Compuertas de ejecución:** pytest y `sql_tests` **en serie** (`p2_test` compartida; dos corridas simultáneas dan deadlock). Credenciales desde `backend/.env`, sin imprimirlas. `0027` no se edita; todo el esquema va en `0028`.
> **Aprobación humana (E-1 y Fase 7):** otorgada por el solicitante el 2026-10-16 («los elementos Para aprobar son aprobados»: `downgrade()` solo de esquema (D-4), enmienda E-1 y criterio de borrado por clave JSON; arranque formal de la Fase 7).
> **Estado actual:** Fases 1-6 completas; Fase 7 en curso.

---

## Fase 3/4 — Especificación y Clarificación

- [x] **T1 (Fase 3/4 · `@arq-reviewer`)** — Cubre: `RF-1`..`RF-8`.
  Validar la enmienda constitucional acotada E-1 (`spec.md` §3.1) frente a §2.4, §6.2 y §8.1/§8.2 (incluida la lectura de que §2.4 habla de «API operations»); confirmar que no se debilitan saldo ≥ 0, atomicidad, default-deny ni `extra="forbid"`; ratificar el criterio de «legacy» de RF-1 (movimiento mixto, `FO_UNIFICADO`, eventos por `movimiento_id`/`acta_id`) y la reescritura de REQ-FO-002; verificar que `docs/constitution.md` no requiere cambio.
  **Hecho cuando:** `spec.md` esté aprobado sin ambigüedades abiertas, E-1 ratificada o corregida por escrito y el dictamen registrado aquí. *(Evidencia: dictamen T1 2026-10-16 — APROBADO CON CONDICIONES C1-C6 (H1-H11); aplicadas a `spec.md` (RF-1, RF-3, RF-6, RF-7, §3.1, E12-E13), `plan.md` (§1.1 pasos 0a/4/11/12, §1.4, R5/R7/R8) y a esta tarea: guardia técnica `current_database()`, evento `PURGA_LEGACY_FO`, puntero `ultimo_movimiento_id`→NULL, purga de idempotencia por `movimiento_id`, barrido diagnóstico no circular, REQ-FO-001/002 y `openspec.yaml` ampliados, `downgrade` con `RAISE NOTICE`.)*

## Fase 5 — Planificación (persistencia y seguridad)

- [x] **T2 (Fase 5 · `@dba-guard`)** — Cubre: `RF-1`, `RF-2`, `RF-3`, `RF-6`. Depende de T1.
  Diseñar e implementar `backend/alembic/versions/0028_purga_legacy_fo.py` (`plan.md` §1): guardia E-1 por `current_database()`, instantánea, `DISABLE`/`ENABLE` de **ambos** triggers de ledger, tablas temporales `ON COMMIT DROP`, borrado en orden (eventos → idempotencia → actas → líneas → cabeceras → scopes → secciones), guardia de saldos, `ultimo_movimiento_id`→NULL, purga de idempotencia por `movimiento_id`, evento `PURGA_LEGACY_FO`, `ck_secciones_tipo ('GENERAL','FO')`, republicación de `fn_procesar_movimiento`/`fn_cancelar_movimiento` sin ramas legacy, verificaciones 12(a)-(g) con aborto (incluido el barrido diagnóstico no circular d2), diff textual de las funciones contra 0027 y `downgrade()` solo de esquema con `RAISE NOTICE`. Entregar además el script de **vista previa** (solo lectura) y ejecutar el `pg_dump` de `p2` en `/tmp/opencode/p2_pre_0028.dump` **antes** de aplicar.
  **Hecho cuando:** (1) sobre `p2_test` con datos sembrados en 0027 la migración aplique y el ciclo `head → 0026 → head` funcione; (2) conteo purgado = vista previa; (3) `SUM` de stock idéntico y eventos no legacy idénticos por `id`; (4) ambos triggers `tgenabled = 'O'` y un `DELETE` posterior en cada ledger falla; (5) ninguna función contiene `FO_PAQUETE`/`FO_EN_USO`; (6) aplicada en `p2` con respaldo previo y verificada; (7) `@dba-guard` emite su visto bueno (integridad referencial, orden de borrado, bloqueos). *(Evidencia 2026-10-16: `0028_purga_legacy_fo.py` + `db/preview_purga_0028.sql`; 57 comprobaciones en `p2_test`, 0 fallos (conteos, stock fila a fila, md5 de eventos conservados, triggers `O`, abortos con rollback, diff de funciones solo `IN(...)`→`= 'FO'`, downgrade de esquema, ciclo `head→0026→head`); desviaciones: lock anticipado con `lock_timeout`, guardia E-1 por dependientes (una base nueva no aborta), no-op sin secciones legacy. `pg_dump` en `/tmp/opencode/p2_pre_0028.dump`. Aplicada en `p2`: vista previa 31 mov/69 líneas/13 actas/2 scopes/7 idem/34 punteros/129 eventos = resultado real; ledger 1016−129+1=888; secciones solo `GENERAL`,`FO`; triggers `O`; DELETE posterior bloqueado; 0 funciones con literales legacy.)*

- [x] **T3 (Fase 5 · `@sec-ops`)** — Cubre: `RF-6`, `RF-4`. Depende de T1 (en paralelo con T2 hasta la aplicación en `p2`).
  Verificar que la suspensión de los triggers es local a la transacción y se verifica reactivada (incluida la ruta de error), que la migración no cambia permisos/roles ni deja objetos nuevos, que el predicado de borrado no alcanza datos vivos (unidad `PAQUETE (100 PZ)`, `CATALOGO`, `DESPLIEGUE_*`), que el rechazo de `modulo` (`extra="forbid"`) y el default-deny de scopes no se debilitan, y que no hay secretos en el volcado/rutas propuestas.
  **Hecho cuando:** `@sec-ops` emita aprobación escrita del plan y de la migración implementada. *(Evidencia: dictamen T3 2026-10-16 — CON CONDICIONES C1-C4 sin bloqueantes: C2 (locks antes de la guardia + idempotencia en `n_dependientes`) y C3 (`chmod 600` de scripts en `/tmp/opencode`) aplicados; C1 (test de `DESPLIEGUE_*`/`UM_*` conservados; métrica 21 añadida al preview) pasa a T5; C4 (diff de T4 solo comentarios/docstrings/`description`, sin tocar `Depends`/scopes/`model_config`) vigente en T4/T5.)*

## Fase 7 — Implementación Backend

- [x] **T4 (Fase 7 · `@coder`)** — Cubre: `RF-4`. Depende de T2 y T3. **Requiere la aprobación humana de este paquete.**
  Podar el backend (`plan.md` §2): `models/inventario.py` (`CHECK` solo `GENERAL`/`FO`), `services/movimientos.py` (comentario/lógica de enrutamiento sin E8), docstrings y descripciones en `services/inventario.py`, `services/transaccional.py`, `schemas/inventario.py`, `schemas/operadores.py`, `api/v1/fibra.py` y `api/v1/inventario.py`. Cero lógica nueva; no editar `0027`. Antes de tocar código: exportar `openapi.json` baseline a `/tmp/opencode/openapi_pre.json`.
  **Hecho cuando:** `grep -rnE "FO_PAQUETE|FO_EN_USO" backend/app` no devuelva coincidencias, `mypy` pase y un `almacen_id` purgado responda 422 «Sección … inexistente» sin efectos secundarios. *(Evidencia 2026-10-16: poda de `models/inventario.py` (CHECK `GENERAL`/`FO`), `services/movimientos.py`, `services/inventario.py`, `services/transaccional.py`, `schemas/inventario.py`, `api/v1/fibra.py`, `api/v1/inventario.py`; solo comentarios/docstrings/CHECK (C4 de @sec-ops: sin tocar `Depends`/scopes/`model_config`); `grep` de `FO_PAQUETE|FO_EN_USO` en `backend/app` = 0; mypy 0 en 85 archivos.)*

- [x] **T5 (Fase 7 · `@tester` + `@qa-agent`)** — Cubre: `RF-1`..`RF-4`, `RF-6`, `RF-8`. Depende de T4.
  Implementar `tests/test_migracion_0028.py` (plan §4), ajustar `test_migracion_0027.py` (`upgrade head` → `upgrade 0027`), retirar los tests de compatibilidad legacy de `test_fo_unificado.py`/`test_fo_transferencias.py` y limpiar `test_fo_valor_casos_limite.py`, `test_catalogo_admin.py`, `helpers/fabrica.py` y `sql_tests/`. Ejecutar pytest, `sql_tests` y `mypy` **en serie**. `@qa-agent` valida los E1-E11 de `spec.md` §5. Comparar el OpenAPI exportado con el baseline.
  **Hecho cuando:** pytest, `sql_tests` y `mypy` en verde; el diff de OpenAPI solo contenga `description`/`summary`; y se registre la **Congelación Contractual** (condición para iniciar T6). *(Evidencia 2026-10-16: `tests/test_migracion_0028.py` (9 pruebas: purga/conservación, esquema/triggers, 3 abortos con rollback, trigger previo deshabilitado, guardia E-1, E7, downgrade de esquema, ciclo head↔0026), `test_migracion_0027.py` (resiembra legacy en 0026; `head`→`0027`), retirados los tests de compatibilidad legacy de `test_fo_unificado`/`test_fo_transferencias`/`test_fo_valor_casos_limite` y añadido `test_RF_4_origen_purgado_responde_422_sin_efectos`; pytest **453 passed**, sql_tests **25 passed**, mypy **0/85**. **CONGELACIÓN CONTRACTUAL:** diff OpenAPI vs baseline = 3 cambios, todos `description` (`GET /inventario/secciones/transferibles`, `SeccionOut`, `SeccionTransferibleOut`); ninguna ruta, campo, tipo, enum ni código de estado. T6 desbloqueada.)*

## Fase 7 — Implementación Frontend

- [x] **T6 (Fase 7 · `@state-agent` → `@ui-agent`, con `@ux-agent`/`@form-agent` solo si se detecta impacto)** — Cubre: `RF-5`. Depende de T5 (Congelación Contractual).
  Podar el frontend (`plan.md` §3): `types.ts` (`Seccion.tipo: 'GENERAL' | 'FO'`), `utils/seccionLabel.ts` (sin ramas legacy; id desconocido → `Sección #id`), eliminar `utils/auditoriaPresentacion.ts` y su uso en `Auditoria.tsx`, comentarios en `Transferencias.tsx`/`operadorPayload.ts`/`services/fibra.ts`, y los tests (`NomenclaturaFo`, `Transferencias`, `OperadoresRapidosDialogs`, `operadorPayload`). No tocar `DESPLIEGUE_*` ni `PAQUETE (100 PZ)`.
  **Hecho cuando:** `tsc -b`, `eslint`, `vitest run` y `vite build` en verde; el barrido de residuos de `FO_PAQUETE|FO_EN_USO|PAQUETE|EN_USO` en `frontend/src` (excluida la unidad `PAQUETE (100 PZ)`) esté vacío; sin cambios en flujos vivos. *(Evidencia 2026-10-16: `Seccion.tipo` = `'GENERAL' | 'FO'`; `seccionLabel.ts` reducido (id desconocido → «Sección #id»); `auditoriaPresentacion.ts` eliminado (`git rm`) y su uso en `Auditoria.tsx`; comentarios podados en `Transferencias.tsx`/`operadorPayload.ts`; tests `NomenclaturaFo`, `Transferencias`, `TransferenciasMultiOrigen`, `OperadoresRapidosDialogs`, `operadorPayload`, `operadoresHooks`, `MaterialForm` ajustados; `tsc -b` 0, `eslint` 0, `vitest` 531 passed, `vite build` sin advertencias; barrido `FO_PAQUETE|FO_EN_USO` en `frontend/src` = 0; `EN_USO` solo en aserciones negativas de `queryKey` (retiradas las de `operadoresHooks`).)*

## Fase 8-9 — Auditoría, QA, Evolución y Archivado

- [x] **T7 (Fase 8-9 · `@auditor` + `@qa-agent` + `@arq-reviewer` + `@sec-ops`)** — Cubre: `RF-1`..`RF-8`. Depende de T6.
  1. `@auditor`: Drift Report (código vs `spec.md`) con barrido global de `FO_PAQUETE`, `FO_EN_USO`, `PAQUETE`/`EN_USO` como módulo, y `modulo` en `backend/`, `frontend/` y `openspec/` (excluidos `0027` y `archive/`, que conservan el historial).
  2. `@qa-agent`: conformidad final contra E1-E11 y compuertas completas en serie.
  3. `@arq-reviewer`/`@sec-ops`: dictamen final; confirmar que E-1 se agotó con `0028` y que el trigger permanece activo en `p2` y `p2_test`.
  4. Fase 9: promover a `openspec/specs/` (REQ-FO-002 reescrito, `REQ-PURGA-*`), actualizar `openspec.yaml › domain_rules` (`historical_technical_values`, `audit_ledger_immutability`) y `paths` si hubo cambios, `trazabilidad.md`, commit, `git mv` a `openspec/changes/archive/`.
  **Hecho cuando:** el Drift Report quede en cero hallazgos bloqueantes; `openspec validate --specs --strict` 3/3 y `openspec validate 2026-10-purga-legacy-fo --strict` válidos antes del archivado; `openspec/changes/` contenga solo `archive/`; y se presenten al usuario, para aprobación humana, los puntos de `.agents.md` §3 y de la baja de `docs/1 Changes.docx` (no se editan sin aprobación). *(Evidencia 2026-10-16: `@auditor` WITH CONDITIONS (2 MEDIUM, 5 LOW) → cerrados: tests añadidos (E6, E8, secuencias, NOTICE, ids 2/3 y DEVOL destino), docstrings y etiquetas huérfanas (`FO_UNIFICADO`/`MIGRACION_FO` retiradas; `PURGA_LEGACY_FO` etiquetada), `.agents.md` excluido del commit; `@arq-reviewer` APROBADO CON OBSERVACIONES (mapeo RF→REQ, D-4 en spec, redacción E-1 y barrido RF-5 corregidos); `@sec-ops` APROBADO (C1-C4 cumplidas, sin hallazgos ≥ MEDIUM). Compuertas finales en serie: pytest 453, sql_tests 25, mypy 0/85, tsc 0, eslint 0, vitest 531, `vite build` OK; `openspec validate --specs --strict` 3/3. Specs maestras: REQ-FO-001 (escenario), REQ-FO-002 (reescrito, ID conservado), REQ-FO-003, REQ-PURGA-001..003; `openspec.yaml › domain_rules` actualizado. Aprobaciones humanas pendientes (no editadas): `.agents.md` §3 y §5 (cambio previo del usuario, fuera de este commit), baja de `docs/1 Changes.docx`, destrucción del `pg_dump` de `/tmp/opencode` al cerrar.)*

---

## Orden y dependencias

`T1 → (T2 ∥ T3) → T4 → T5 [Congelación Contractual] → T6 → T7`

## Matriz RF → Tarea

| RF | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
| :-- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| RF-1 Purga de datos | ✔ | ✔ | ✔ | | ✔ | | ✔ |
| RF-2 Esquema solo FO | ✔ | ✔ | | | ✔ | | ✔ |
| RF-3 Preservación | ✔ | ✔ | | | ✔ | | ✔ |
| RF-4 Backend sin puente | ✔ | | ✔ | ✔ | ✔ | | ✔ |
| RF-5 Frontend sin legado | ✔ | | | | | ✔ | ✔ |
| RF-6 Migración segura | ✔ | ✔ | ✔ | | ✔ | | ✔ |
| RF-7 Gobernanza | ✔ | | | | | | ✔ |
| RF-8 No regresión | ✔ | | | | ✔ | ✔ | ✔ |

## Registro de resoluciones de diseño (Fases 1-6)

- **D-1:** borrado físico (no remapeo). **D-2:** enmienda acotada en el paquete, sin tocar `docs/constitution.md`. **D-3:** eventos con `modulo` legacy se borran solo si son de dominio FO, por clave JSON (refinada: no hay nada que quitar en `MATERIAL_MODIFICADO`).
- **D-4:** `downgrade()` revierte solo esquema y no aborta (la infraestructura de pruebas degrada desde la cabeza); los datos solo se recuperan del `pg_dump`.
