# Tareas: 2026-10-saneamiento-2

> Secuencial por fases SDD. **Backend-First:** T5 (frontend) queda bloqueada hasta que T4 registre la **Congelación Contractual**. Cualquier cambio de contrato posterior invalida la congelación.
> Cada tarea cita los `RF-n` de `spec.md` y el agente responsable. Los agentes no amplían alcance: lo no listado en `spec.md` §3 (Fuera de Alcance) no se implementa.
> **Compuertas de ejecución:** pytest y `sql_tests` **en serie** (`p2_test` compartida; dos corridas simultáneas dan deadlock). Credenciales desde `backend/.env`, sin imprimirlas. **No se añaden ni se editan migraciones.**
> **Autorizaciones del solicitante (2026-10-16):** edición de `.agents.md` (L2) para retirar `FO_PAQUETE`/`FO_EN_USO`, baja de `docs/1 Changes.docx`, destrucción de `/tmp/opencode` y las decisiones D-1..D-7 de `spec.md` §1. La destrucción es irreversible y se confirma de nuevo antes de ejecutarse (T7).
> **Estado actual:** Fases 1-6 completas (artefactos escritos). **Aprobación humana otorgada (2026-10-16): T1/T2 y, si salen limpios, T3.** Fase 7 en curso.

---

## Fase 3/4 — Especificación y Clarificación

- [x] **T1 (Fase 3/4 · `@arq-reviewer`)** — Cubre: `RF-1`..`RF-6`.
  Validar el alcance del paquete: que es higiene sin deltas de spec (`skip_specs: true` justificado), que la eliminación de filtros en backend es un cambio de contrato consciente (R1) y no un cambio de dominio, que `.agents.md` §3 puede editarse con la autorización registrada, que no hay conflicto con la Constitución (§2.4 ledger: no se toca; §1.3 spec primero) y que la dispensa de `trazabilidad.md` es suficiente.
  **Hecho cuando:** dictamen registrado aquí y `spec.md` sin ambigüedades abiertas. *(Evidencia 2026-10-16: CON CONDICIONES C1-C6, todas documentales y aplicadas: justificación de `skip_specs`/sin alias, nota histórica sin rutas, `.agents.md` líneas 33/670 con la fila de tabla §3 conservada, `X-Actor` como desviación conocida de Constitución §3.1/§3.3 reconocida por el humano, RF-5 con DEFAULT de columna, escenario del salto de línea por ASGITransport, `find … shred` en lugar de `shred -u` sobre directorios, referencias al `.docx` limitadas a fuera del archivo.)*

## Fase 5 — Planificación (seguridad)

- [x] **T2 (Fase 5 · `@sec-ops`)** — Cubre: `RF-2`, `RF-3`. Depende de T1.
  (1) Reproducir en lectura el 500 de IDs fuera de INT4 y fijar el predicado exacto del handler (SQLSTATE `22003` y el rechazo del cliente psycopg para enteros > `bigint`), sin filtrar detalles internos de la base en el cuerpo del 400. (2) Verificar contra `p2` (solo lectura) y el seed que los actores existentes cumplen `1..100` y sin caracteres de control (R2). (3) Confirmar que el handler no enmascara otros SQLSTATE (R3) y que la validación de `X-Actor` ocurre antes de abrir sesión. (4) Ratificar que `X-Actor` sigue siendo no autenticado y que la autenticación real queda fuera de alcance.
  **Hecho cuando:** aprobación escrita del plan §1.1-§1.2 con las condiciones para T3. *(Evidencia 2026-10-16: CON CONDICIONES C1-C3 aplicadas. Reproducido: 8 rutas dan 500 con `10**12`…`2**63` (`DataError`/`NumericValueOutOfRange`, SQLSTATE `22003`, rechazo del servidor); `X-Actor` hoy admite 101 chars, vacío y salto de línea (200) y `\x00` da 500. Predicado exclusivo `orig.sqlstate == '22003'`, `JSONResponse` con kwargs y mensaje fijo, patrón de `X-Actor` endurecido. Actores de `p2` y del seed válidos (1..100, sin controles).)*

## Fase 7 — Implementación Backend

- [x] **T3 (Fase 7 · `@coder`)** — Cubre: `RF-2`, `RF-3`, `RF-4` (backend), `RF-5`. Depende de T2. **Requiere la aprobación humana de este paquete.**
  Antes de tocar código exportar el baseline `/tmp/opencode/openapi_s2_pre.json`. Después implementar (`plan.md` §1): pruebas que **reproducen** el defecto primero (`test_robustez_ids.py`, `test_actor_header.py`), handler global `22003 → 400` en `main.py`, validación de `X-Actor` en `security.py`, eliminación de los cuatro filtros en `catalog.py`/`catalogo.py`/`test_catalogo.py` y test guardián `test_convencion_resultado.py`. Sin migraciones; sin cambios en stored functions.
  **Hecho cuando:** las nuevas pruebas pasan, `mypy` 0 errores, `grep "desde_sku\|hasta_sku\|desde_id_lista\|hasta_id_lista" backend/` = 0 y el diff de `backend/app` se limita a lo previsto (sin tocar `Depends` de scopes ni `model_config`). *(Evidencia 2026-10-16: `main.py` (handler `DBAPIError`, predicado exclusivo `22003`, mensaje fijo), `security.py` (`ActorHeader` 1..100, sin controles, con `description`), `catalog.py`/`catalogo.py` (4 filtros fuera), `test_catalogo.py`; pruebas nuevas `test_robustez_ids.py` (30; 29 fallaban antes: 500), `test_actor_header.py` (25; 15 fallaban antes), `test_convencion_resultado.py` (8; 18 funciones revisadas, DEFAULT NULL, `{'EXITO'}`). Desviación: patrón de `X-Actor` con clase negada (`\S` dejaba pasar NUL/DEL/C1). `grep` de los 4 nombres en `backend/app` = 0 (solo `test_catalogo.py` los nombra para verificar que se ignoran). pytest 517, mypy 0/88.)*

- [x] **T4 (Fase 7 · `@qa-agent` + `@tester`)** — Cubre: `RF-2`..`RF-6`. Depende de T3.
  Ejecutar pytest completo, `sql_tests` y `mypy` **en serie**. Comparar el OpenAPI exportado con el baseline; regenerar `openspec.yaml › paths`. `@qa-agent` valida los casos límite E1-E6.
  **Hecho cuando:** compuertas verdes y se registra la **Congelación Contractual**: el diff de OpenAPI contiene únicamente (a) los cuatro query params de `GET /api/v1/catalogo` y (b) las restricciones/`description` de `X-Actor`. T5 desbloqueada. *(Evidencia 2026-10-16: pytest **517 passed**, `sql_tests` **25**, mypy **0/88**. **CONGELACIÓN CONTRACTUAL:** diff OpenAPI vs baseline = 236 diferencias de bajo nivel, todas de dos tipos: (a) eliminación de `desde_id_lista`/`hasta_id_lista`/`desde_sku`/`hasta_sku` en `GET /api/v1/catalogo` y (b) restricciones (`minLength`, `maxLength`, `pattern`) y `description` del header `X-Actor` en las operaciones; `components` sin cambios y ninguna ruta, campo, tipo, enum ni código de estado nuevos. `openspec.yaml` no documentaba esos params; se añadieron `domain_rules.actor_header`, `numeric_out_of_range` y `audit_result_convention`. `openspec validate --specs --strict` 3/3.)*

## Fase 7 — Implementación Frontend

- [x] **T5 (Fase 7 · `@state-agent` → `@ui-agent`; `@ux-agent`/`@form-agent` solo si se detecta impacto)** — Cubre: `RF-4`. Depende de T4 (Congelación Contractual).
  Podar el frontend (`plan.md` §2): `children` de `Sidebar.tsx`, `formatMxnConMoneda`, `parseCantidadDecimal` (con sus pruebas), los cuatro filtros de `catalog.ts` y alinear `ActaItem`. No tocar flujos vivos.
  **Hecho cuando:** `tsc -b`, `eslint`, `vitest run` y `vite build` en verde sin advertencias, y el `grep` de las cadenas eliminadas en `frontend/src` = 0. *(Evidencia 2026-10-16: `Sidebar.tsx` sin `children`, `formatMxnConMoneda` y `parseCantidadDecimal` eliminadas con sus pruebas, 4 filtros fuera de `catalog.ts`, `ActaItem` con `origen_almacen_id?`/`origen_nombre?`; `tsc -b` 0, eslint 0, vitest **529 passed / 43 files**, `vite build` sin advertencias.)*

## Fase 8 — Documentación y gobernanza (previa a la auditoría)

- [x] **T6 (Fase 8 · `@coder` con visto bueno de `@arq-reviewer`)** — Cubre: `RF-1`. Puede preparar `.agents.md`, `docs/` y `ddl.sql` en paralelo a T5, pero README y `ddl.sql` se cierran con cifras finales.
  (1) `.agents.md`: retirar `FO_PAQUETE`/`FO_EN_USO` de §3 (l. 33) y de la l. 670; verificar `69bca35`. (2) `git rm docs/1 Changes.docx` y verificar referencias. (3) Regenerar `backend/db/ddl.sql` (`plan.md` §3.2) con cabecera y script de verificación. (4) Actualizar el README (`plan.md` §3.1) con las cifras medidas en T4/T5.
  **Hecho cuando:** `grep "FO_PAQUETE\|FO_EN_USO" .agents.md` = 0, el DDL regenerado coincide con una base migrada a `0028` y el README coincide con `ls backend/alembic/versions` y los resúmenes de pytest/vitest. *(Evidencia 2026-10-16: `.agents.md` líneas 33/670 sin `FO_PAQUETE`/`FO_EN_USO` (fila de tabla §3 conservada; 0 coincidencias); `git rm docs/1 Changes.docx` sin referencias fuera del archivo; `ddl.sql` regenerado con `backend/scripts/generar_ddl.py` (3393 líneas, cabeza 0028, sin host/rol/credenciales; `--verificar` OK; sin `FO_PAQUETE`/`despliegues`; `modulo` solo en comentarios y `'CATALOGO'`); README: head 0028, 28 migraciones, pytest 517/34 archivos + sql_tests 25, vitest 529/43 archivos, mypy 88 archivos, Inventario FO unificado, §4.6 e historial.)*

## Fase 8-9 — Auditoría, QA, Evolución y Archivado

- [x] **T7 (Fase 8-9 · `@auditor` + `@qa-agent` + `@arq-reviewer` + `@sec-ops`)** — Cubre: `RF-1`..`RF-6`. Depende de T5 y T6.
  1. `@auditor`: Drift Report (código vs `spec.md`), con barrido de las cadenas eliminadas y de `'OK'` como `resultado`.
  2. `@qa-agent`: compuertas finales en serie (pytest, `sql_tests`, `mypy`, `tsc -b`, `eslint`, `vitest`, `vite build`, `openspec validate --specs --strict` y `openspec validate 2026-10-saneamiento-2 --strict`).
  3. `@arq-reviewer`/`@sec-ops`: dictamen final.
  4. `trazabilidad.md` (matriz RF → implementación → prueba, dispensas formales de `plan.md` §3.3) y commit.
  5. `git mv` a `openspec/changes/archive/`; `ls openspec/changes` = solo `archive/`.
  6. **Último paso, tras confirmación humana:** `find /tmp/opencode -type f -exec shred -u {} +` y retiro de subdirectorios vacíos (`plan.md` §3.4; `shred` es de mejor esfuerzo en FS con journaling/CoW); registrar qué se destruyó.
  **Hecho cuando:** Drift Report sin hallazgos bloqueantes, compuertas verdes, paquete archivado y `/tmp/opencode` sin respaldos ni scripts. *(Evidencia 2026-10-16: `@auditor` WITH CONDITIONS (2 MEDIUM, 4 LOW) → cerrados: badges del README (519/529/88), notas «Historical» en §4.1/§4.5.1, test del POST con `10**30` y control positivo del espía de sesión; `@sec-ops` APROBADO (C1-C3 cumplidas, patrón de `X-Actor` verificado con pydantic: sin ReDoS —motor `regex` lineal y `max_length` antes de `pattern`—; observación: un cliente que envíe UTF-8 crudo con mayúsculas acentuadas produce un byte C1 y recibe 422, aceptable y documentado). Compuertas finales en serie: pytest **519**, `sql_tests` **25**, mypy **0/88**, `tsc -b` 0, eslint 0, vitest **529/43**, `vite build` sin advertencias, `generar_ddl.py --verificar` OK, `openspec validate --specs --strict` 3/3. Paso 6 (destrucción de `/tmp/opencode`): ver «Registro de destrucción» abajo.)*

---

## Orden y dependencias

`T1 → T2 → T3 → T4 [Congelación Contractual] → T5 → T6 → T7`

## Matriz RF → Tarea

| RF | T1 | T2 | T3 | T4 | T5 | T6 | T7 |
| :-- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| RF-1 Gobernanza y docs | ✔ | | | | | ✔ | ✔ |
| RF-2 IDs INT4 → 400 | ✔ | ✔ | ✔ | ✔ | | | ✔ |
| RF-3 `X-Actor` | ✔ | ✔ | ✔ | ✔ | | | ✔ |
| RF-4 Poda de código | ✔ | | ✔ | ✔ | ✔ | | ✔ |
| RF-5 Convención `EXITO` | ✔ | | ✔ | ✔ | | | ✔ |
| RF-6 No regresión | ✔ | | | ✔ | ✔ | ✔ | ✔ |

## Registro de resoluciones de diseño

- **D-1** `EXITO` + test guardián (sin migración). **D-2** handler global `22003 → 400` (sin cotas `le=`). **D-3** `X-Actor` con validación mínima; autenticación real fuera de alcance. **D-4** filtros eliminados en frontend y backend. **D-5** `ActaItem` alineado con el backend. **D-6** `ddl.sql` regenerado con `pg_dump --schema-only`. **D-7** dispensas consolidadas y destrucción de `/tmp/opencode` al final.

## Registro de destrucción (D-7)

Confirmada por el solicitante el 2026-10-16. Ejecutado: `find /tmp/opencode -xdev -type f -exec shred -u {} +` y `find /tmp/opencode -depth -mindepth 1 -type d -empty -delete`.

- Destruidos: 92 archivos regulares (0 symlinks) — el `pg_dump` previo a `0028` (`p2_pre_0028.dump`), los scripts auxiliares de las compuertas y de verificación, los baselines/volcados de OpenAPI y los logs de ejecución. No se registra su contenido.
- Resultado: `/tmp/opencode` conservado, vacío (0 archivos, 0 subdirectorios).
- La purga de `p2` ejecutada por `0028` ya no es recuperable. `/tmp` es tmpfs: `shred` es de mejor esfuerzo.
