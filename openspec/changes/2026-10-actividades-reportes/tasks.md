# Tareas — ETAPA 2/3: ACTIVIDADES (Reportes y Exportación)

**Paquete:** `2026-10-actividades-reportes` · **Fase SDD:** 6 (Tareas) · Trazabilidad: `proposal.md` ⇄ `spec.md` (REQ-REP-NNN) ⇄ `plan.md` ⇄ esta lista.

## Reglas operacionales (inquebrantables)

1. **Parada obligatoria:** al terminar CADA tarea (T1..T12) el Orquestador se detiene por completo, reporta evidencia y pide confirmación explícita al humano antes de continuar.
2. **Backend-First:** T2-T7 (plantilla → consulta → API → contrato) deben cerrarse antes de T8. El frontend (T8-T10) permanece bloqueado hasta el PASS de T7.
3. **Contrato:** T7 valida `spec.md` ⇄ OpenAPI ⇄ implementación y congela el contrato en `.openspec.yaml` (`contract.frozen: true`, snapshot y sha256) antes de escribir frontend. Cambios posteriores exigen RFC (spec/plan primero).
4. **Sin refactor ni limpieza** de código ajeno (Fase 7). Solo `@auditor` reporta código muerto (Fase 8); borrarlo requiere tarea aprobada.
5. **Aislamiento de lo existente:** no se modifican `plantilla_reporte.py`, `reportes.py`, `api/v1/reportes.py`, `services/actividades.py`, las plantillas XLSX ni el contrato de Entrega/Consumo ni el de la Etapa 1 (plan D-9). Los cambios en `ReporteSubseccion.tsx`, `Reportes.tsx`, `ActividadesPanel.tsx`, `queryKeys.ts`, `MainLayout.tsx` y `NavigationTarget` se limitan a lo descrito en `plan.md` §5 y deben ser retrocompatibles.
6. **Sin DDL:** ninguna migración Alembic ni función SQL nueva; un eventual índice se tramita por RFC (plan D-5).
7. **Solo lectura:** ninguna tarea agrega escrituras, eventos de auditoría ni cambios de stock (REQ-REP-016).
8. **Pruebas de backend:** cada `test_req_rep_NNN_*` debe aseverar la respuesta HTTP **y** el estado persistido por consulta SQL directa (incluidos los rechazos: «no se escribió nada»). Aprendizaje de la Etapa 1 (T11).
9. Ninguna línea en `backend/` o `frontend/` cambia antes de la aprobación humana de este paquete.

## Resumen

| Tarea | Fase | Agente(s) | Capa | Depende de |
| --- | --- | --- | --- | --- |
| T1 | 4 | `@arq-reviewer` | Spec/Plan | — |
| T2 | 7 | `@coder` + `@sec-ops` | Backend (plantilla XLSX) | T1 |
| T3 | 7 | `@tester` | Backend (plantilla XLSX) | T2 |
| T4 | 7 | `@coder` + `@dba-guard` | Backend (consulta) | T3 |
| T5 | 7 | `@sec-ops` + `@coder` | Backend (router, config) | T4 |
| T6 | 7 | `@tester` | Backend (API) | T5 |
| T7 | 7 | `@qa-agent` | Contrato | T6 |
| T8 | 7 | `@state-agent` | Frontend (estado) | T7 (PASS) |
| T9 | 7 | `@form-agent`, `@ui-agent`, `@ux-agent` | Frontend (UI) | T8 |
| T10 | 7 | `@tester` | Frontend (pruebas) | T9 |
| T11 | 8 | `@auditor`, `@tester`, `@qa-agent`, `@arq-reviewer` | Validación | T10 |
| T12 | 9 | Orquestador (+ `@auditor` verifica condiciones) | Archivo | T11 |

---

### T1 — Clarificación y visto bueno arquitectónico (Fase 4)
- **Agente:** `@arq-reviewer`
- **REQ:** todos (REQ-REP-001..017)
- **Hacer:** revisar `spec.md` y `plan.md` contra `docs/constitution.md`, `.agents.md` y las specs maestras (`003_inventory_dashboard`, REQ-ACT-001..020); clasificar Dominio vs. Bug; resolver C-1..C-7 de `spec.md` §9 (**el humano decide C-1: zona de negocio**; verificar que `America/Mexico_City` exista en `pg_timezone_names`); cotejar spec ⇄ plan ⇄ tasks (Zero-Drift); confirmar que `plan.md` D-9 no contradice la Etapa 1 ni REQ-UNI-005; confirmar que el modelo 1 hoja = 1 folio y los tamaños de la plantilla (§3.2) coinciden con el archivo real.
- **Hecho cuando:** hay informe sin ambigüedades abiertas; los cambios resultantes están aplicados a `proposal.md`/`spec.md`/`plan.md`/`tasks.md` con aprobación del humano; `.openspec.yaml` marca `fase_4_clarificacion: completada`.
- **Estado:** COMPLETADA (2026-10-20): APROBADO CON CORRECCIONES; correcciones de clase A aplicadas; humano decidió B-1(a)=C-8, B-2=C-2..C-7, B-3(a)=C-10; paquete re-aprobado. `fase_4_clarificacion: completada`.
- **PARADA.**

### T2 — Servicio de plantilla XLSX de actividades
- **Agentes:** `@coder` (implementación) + `@sec-ops` (revisión de entrada y XLSX)
- **REQ:** 006, 007, 008, 009, 010
- **Hacer:** crear `backend/app/services/plantilla_reporte_actividades.py` según plan §3.2-§3.3: **spike inicial del logo** (capturar los bytes UNA vez con `ref.getvalue()`; prohibido `Image._data()` por ser de un solo uso; paridad de ancla/tamaño en hojas copiadas, merges, alturas, anchos, `fitToPage`, márgenes); generación de una hoja por folio (titulada con el folio, orden ascendente, sin `Sheet1`); inyección de campos con `sanitizar_celda` y limpieza de caracteres ilegales; desborde de materiales y actividades (reutilizando `_desplazar_filas`); alturas de actividades y comentarios con heurística calibrada; `nombre_archivo_actividades`. No tocar `plantilla_reporte.py` ni la plantilla en disco.
- **Hecho cuando:** `mypy`/`ruff` (si el repo los usa) sin errores nuevos; el spike documenta paridad del logo; un libro de ejemplo se abre con openpyxl con las celdas de plan §3.2 correctas; `@sec-ops` confirma neutralización de fórmulas, nombre de archivo y ausencia de rutas derivadas de usuario.
- **PARADA.**

### T3 — Pruebas de la plantilla
- **Agente:** `@tester`
- **REQ:** 006, 007, 008, 009, 010
- **Hacer:** `backend/tests/test_plantilla_reporte_actividades.py` con las pruebas de plan §6 (fila «Plantilla»): celdas y formato numérico, plantilla en disco intacta (hash), logo en todas las hojas con ancla y tamaño idénticos a los de la plantilla, merges/alturas/estilos, desborde (11 y 40 materiales; 5 y 30 actividades de 500 caracteres; comentarios de 2000 con saltos de línea y criterio medible de REQ-REP-008; descripción de material larga con `wrap_text`), cero materiales, hojas ordenadas y sin `Sheet1`, 100 hojas, fórmulas neutralizadas, caracteres ilegales, FECHA en texto.
- **Hecho cuando:** todas las pruebas pasan (100 %) y la suite backend previa sigue en verde (incluido `test_plantilla_reporte.py`); evidencia de `pytest` registrada.
- **Estado:** COMPLETADA (2026-10-20): 19 pruebas en verde; pytest completo 580 passed (suite previa intacta); evidencia registrada.
- **PARADA.**

### T4 — Servicio de consulta
- **Agentes:** `@coder` (implementación) + `@dba-guard` (revisión de la consulta)
- **REQ:** 002, 003, 004, 005, 016
- **Hacer:** `backend/app/services/reportes_actividades.py` (consulta de plan §2 con filtros AND, `solo_equipos`, zona de negocio enlazada como parámetro, orden y `limite`; constantes `MAX_HOJAS_XLSX`, `MAX_FILAS_XLSX`); `P2_REPORTES_TZ` en `backend/app/config.py` (vacío ≡ no definido) con validación al arrancar, dependencia `tzdata` fijada en `pyproject.toml`/`uv.lock` y documentación en el README. Consulta con SQLAlchemy ORM **tipado** y el `+ 1 día` calculado en SQL (plan §2). Reutiliza `_construir_out`; cero aritmética de negocio; prueba de que la zona configurada existe en `pg_timezone_names`.
- **Hecho cuando:** `@dba-guard` confirma solo lectura, parámetros enlazados y `EXPLAIN` (con y sin `equipo_id`) sin necesidad de índice (o registra el RFC); zona inválida impide el arranque; tipos y linters sin errores nuevos.
- **Estado:** COMPLETADA (2026-10-20): `@coder` implementó y `@dba-guard` APROBÓ (4 criterios); mypy limpio (55 archivos); pytest completo 583 passed.
- **PARADA.**

### T5 — Router, seguridad de entrada y registro
- **Agentes:** `@sec-ops` (controles y revisión) + `@coder` (implementación)
- **REQ:** 002, 003, 004, 005, 009, 010, 011, 016
- **Hacer:** `backend/app/api/v1/reportes_actividades.py` con `GET /reportes/actividades` (plan §3.4): aislamiento (403 por Unidad ajena, vacío/404 por `actividad_id` ajeno), `desde > hasta` ⇒ 422, `formato` inválido ⇒ 422, modelo de consulta `extra="forbid"` (parámetro no declarado ⇒ 422), `gt=0` en identificadores, 404 sin resultados, tope de 100 hojas y de 10 000 filas ⇒ 422, `run_in_threadpool`, adjunto con nombre constante saneado; registrar en `app/main.py`; documentar códigos en OpenAPI.
- **Hecho cuando:** el endpoint aparece en `/openapi.json` con parámetros y códigos del plan; `@sec-ops` confirma default-deny, no divulgación por `actividad_id`, ausencia de secretos y de escritura, y ratifica el límite D-11.
- **Estado:** COMPLETADA (2026-10-20): `@coder` implementó el router y `@sec-ops` APROBÓ (5 criterios, D-11 ratificado); ajuste mínimo de `test_req_act_001` para coexistir con la ruta nueva; pytest completo 583 passed.
- **PARADA.**

### T6 — Pruebas de API
- **Agente:** `@tester`
- **REQ:** 002, 003, 004, 005, 009, 010, 011, 016
- **Hacer:** `backend/tests/test_reportes_actividades.py` con una prueba por requisito (`test_req_rep_NNN_*`) que aserte HTTP **y** BD (regla 8): json y orden, filtros y combinación AND, día inclusivo y borde de zona (23:30 y 00:30 locales), `desde > hasta`, 403 / vacío / 404 por aislamiento, administrador transversal, Unidad inactiva incluida, XLSX descargable leído con openpyxl (hojas, folio, fecha, materiales), 404 sin resultados, 422 por 101 folios, `formato` inválido, 400 fuera de INT4, nombre de archivo, tablas sin cambios y cero eventos de auditoría nuevos, medición de tiempo y tamaño de un libro de 100 hojas (T1 midió 1,56 s y 2,6 MB sin datos); además: desborde vía API (11 materiales, 5 actividades y comentario de 2000 con saltos de línea) con la hoja leída con openpyxl y BD intacta; tope de filas (`LIMITE_FILAS_EXCEDIDO`, 422) sembrando snapshots por `INSERT` directo; `X-Actor` ausente ⇒ 422; parámetro no declarado ⇒ 422; `desde` sin `hasta` y `hasta` sin `desde`; `hasta=9999-12-31` y `desde=0001-01-01` ⇒ 200 (nunca 500); `equipo_id` y `actividad_id` fuera de INT4 (10¹², 10³⁰) ⇒ 400; `equipo_id` inexistente (admin: vacío/404; no admin: 403); precedencia 422 ⇒ 403 ⇒ 200/404.
- **Hecho cuando:** pytest completo pasa al 100 % y cada REQ-REP de backend tiene al menos una prueba que pasa con aserción HTTP + BD.
- **PARADA.**

### T7 — Compuerta de contrato (congelación Backend → Frontend)
- **Agente:** `@qa-agent`
- **REQ:** 011 (y verificación transversal)
- **Hacer:** validación independiente `spec.md` ⇄ plan §3.5 ⇄ `/openapi.json` ⇄ implementación: parámetros y códigos, tipo de contenido XLSX, campos faltantes/inventados, nomenclatura; comprobar que `ActividadListOut`/`ActividadOut`/`ActividadMaterialOut` son idénticos (normalizando la notación nullable) a `components.schemas` de `openspec/openspec.yaml` y al OpenAPI vivo de `/equipos/{equipo_id}/actividades` (no se consulta el paquete archivado, `.agents.md` §2); Zero-Drift Scan; ejecutar la suite backend completa; escribir `openapi.snapshot.json` del paquete y su sha256; actualizar `.openspec.yaml` (`contract.frozen: true`, `openapi_snapshot`, `openapi_snapshot_sha256`).
- **Hecho cuando:** salida **PASS** con cumplimiento de contrato 100 %; en caso de **FAIL** se emite el informe estructurado (Finding → Severity → File/Line → Violated Rule → Evidence → Recommended Correction) y se vuelve a T4-T6. **El frontend sigue bloqueado hasta el PASS.**
- **PARADA.**

### T8 — Tipos, servicio, hooks y claves (frontend)
- **Agente:** `@state-agent`
- **REQ:** 012, 013, 014, 015
- **Hacer:** plan §5.1: `ReporteActividadesParams` y `NavigationTarget.actividadId` en `types.ts`; `listarReporteActividades` y `descargarReporteActividadesXlsx` en `services/reportes.ts` (sin cambiar las funciones existentes); `useReporteActividades` y `useExportarReporteActividades` en `hooks/useReportes.ts`; `queryKeys.reporteActividades` e invalidación en `invalidarActividadesEquipo`. Sin transformar ni agregar datos del reporte; sin campos fuera del contrato congelado.
- **Hecho cuando:** `tsc` sin errores; tipos idénticos al snapshot de OpenAPI; regla de invalidación implementada; pruebas de servicio/hooks (vitest) en verde.
- **PARADA.**

### T9 — Subsección Actividades, selectores de operación y enlace
- **Agentes:** `@form-agent` (workflow/filtros), `@ui-agent` (componentes), `@ux-agent` (ergonomía/estados)
- **REQ:** 001, 012, 013, 014, 015
- **Hacer:** plan §5.2: subsección `'actividades'` en `Reportes.tsx` (tras Consumo) con desglose por folio, inspección individual, descarga individual y consolidada con estados y motivos visibles; selectores de operación (Acta, Seguimiento, Actividad); props opcionales retrocompatibles en `ReporteSubseccion`; `initialActividadId` en `MainLayout`/`Reportes`; botón «Ir a Reportes › Actividades» en el aviso de éxito de `ActividadesPanel`; nomenclatura «Unidad».
- **Hecho cuando:** el flujo completo funciona contra el backend real (verificación manual guiada: confirmar una actividad → enlace → ver y descargar el folio; rango de fechas → libro consolidado; 101 folios → mensaje 422) y los estados de REQ-REP-013 son visibles; `@ux-agent` y `@ui-agent` emiten conformidad; `tsc`, `vite build` y `eslint` sin errores ni warnings; Entrega y Consumo se comportan igual; el barrido `utils/__tests__/nomenclaturaUnidad.test.ts` sigue en verde (ningún texto visible nuevo con «Equipo/Equipos»).
- **PARADA.**

### T10 — Pruebas de frontend
- **Agente:** `@tester`
- **REQ:** 001, 012, 013, 014, 015
- **Hacer:** vitest (patrón `vi.mock('../../services/*')` + `QueryClientProvider` + `ToastProvider`) para: pestaña «Actividades» tras «Consumo»; listado por folio y detalle expandible; filtros y selector «Actividad»; descarga consolidada e individual con parámetros correctos y estados (en curso, éxito, 404, 422 de tope); motivo de deshabilitado; selectores de Acta y Seguimiento con `acta_id` sin romper los flujos existentes; enlace del aviso (visible solo con navegación) con preselección de Unidad y folio; invalidación del listado tras confirmar; hooks, servicio y claves.
- **Hecho cuando:** vitest completo pasa al 100 % (incluida la suite previa).
- **PARADA.**

### T11 — Validación y auditoría (Fase 8)
- **Agentes:** `@auditor` (Drift Report), `@tester` (suite final y Matriz de Trazabilidad), `@qa-agent` (conformidad final), `@arq-reviewer` (visto bueno arquitectónico)
- **REQ:** todos
- **Hacer:** Drift Report (Entity/Logic/Exception/Traceability, incluido código muerto, solo reporte); Matriz de Trazabilidad REQ-REP-001..017 con prueba que pasa y aserta HTTP + BD; regresión completa (pytest, `sql_tests`, vitest, `tsc`/build/lint, `mypy`, `openspec validate --specs --strict`); contratos de `/equipos/{equipo_id}/actividades*` de `openspec/openspec.yaml` sin drift; verificación de que la Etapa 3 (Referencia) no fue adelantada y de que Entrega/Consumo no cambiaron de contrato.
- **Hecho cuando:** `@auditor` = APPROVED; `@qa-agent` = PASS (cobertura de trazabilidad 100 %); `@arq-reviewer` otorga visto bueno; el humano aprueba el cierre.
- **PARADA.**

### T12 — Evolución y archivado (Fase 9)
- **Agente:** Orquestador (condiciones de archivado verificadas por `@auditor`)
- **Hacer:** promover REQ-REP-001..017 a `openspec/specs/003_inventory_dashboard/spec.md` (formato `Requirement`/`Scenario`, «SHALL», sin prefijo `RF-n`) y la regla `reportes_actividades` a `openspec/openspec.yaml` (`domain_rules` con zona de negocio, modelo 1 hoja = 1 folio, tope de 100 hojas y de 10 000 filas, solo lectura; `paths` con `GET /api/v1/reportes/actividades` tomado del `openapi.snapshot.json`; sin `components` nuevos porque los DTOs ya existen); documentar `P2_REPORTES_TZ` en el README; mover el paquete a `openspec/changes/archive/2026-10-actividades-reportes/`; no registrar en `.agents.md` enlaces al paquete archivado.
- **Hecho cuando:** el paquete está en `archive/`, las specs maestras actualizadas y `openspec validate --specs --strict` pasa.
- **PARADA.** Solo entonces el humano solicita el SDD de la **Etapa 3** («Referencia»).

---

## Trazabilidad REQ → Tarea

| REQ | Implementa | Verifica |
| --- | --- | --- |
| 001 | T9 | T10 |
| 002, 003, 004, 005 | T4, T5 | T6 |
| 006, 007, 008 | T2 | T3, T6 |
| 009 | T2, T5 | T3, T6 |
| 010 | T2, T5 | T3, T6 |
| 011 | T5 | T6, T7 |
| 012, 013, 014 | T8, T9 | T10 |
| 015 | T8, T9 | T10 |
| 016 | T4, T5 | T6, T11 |
| 017 | — (transversal) | T11 |
