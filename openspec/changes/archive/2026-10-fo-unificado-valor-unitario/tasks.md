# Tareas: 2026-10-fo-unificado-valor-unitario

> Secuencial por fases SDD. **Backend-First:** T6 (frontend) queda bloqueada hasta que T5 registre la Congelación Contractual. Cualquier cambio de contrato posterior invalida la congelación.
> Cada tarea cita los `RF-x` de `spec.md` que cubre y el agente responsable. Los agentes no amplían alcance: lo no listado en `spec.md` §4 (Fuera de Alcance) no se implementa.

## P0 — Prerrequisito (fuera de T1..T7)

- [x] **P0** Archivar `openspec/changes/2026-10-04-saneamiento-deuda-tecnica/` (26/26 tareas completadas) en `openspec/changes/archive/`.
  **Hecho cuando:** `openspec/changes/` contiene un único paquete activo (este) y existe aprobación humana del archivado. *(Evidencia: `git mv` ejecutado 2026-10-15; `openspec/changes/` contiene solo `2026-10-fo-unificado-valor-unitario/` + `archive/`; aprobación humana = instrucción de ejecución autónoma del solicitante.)*

---

## Fase 3/4 — Especificación y Clarificación

- [x] **T1 (Fase 3/4 · `@arq-reviewer`)** — Cubre: `RF-1`..`RF-10`.
  Validar el impacto constitucional (§2.1 saldo, §2.4 ledger —incluido el `ALTER TYPE` de `auditoria_eventos.cantidad`, R2—, §4.1 atomicidad, §6.2 auditoría), la clasificación Dominio vs. Bug (cambio de dominio: unificación de FO + nuevo atributo financiero), la coherencia entre alias `[REQ-...]` y `RF-n`, y ratificar o corregir las clarificaciones C-1..C-7 de `spec.md` §3.2.
  **Hecho cuando:** `spec.md` esté aprobado sin ambigüedades abiertas (cada C-n ratificada o resuelta por escrito) y se confirme que no se requiere enmienda constitucional. *(Evidencia: dictamen T1 2026-10-15 — VEREDICTO: APROBADO; C-1..C-7 ratificadas (C-4 condicionada a @sec-ops en T3); sin enmienda constitucional; correcciones M1/M2 y L1-L8 aplicadas a los artefactos.)*

## Fase 5 — Planificación (persistencia y seguridad)

- [x] **T2 (Fase 5 · `@dba-guard`)** — Cubre: `RF-1`, `RF-2`, `RF-3`, `RF-4`, `RF-6`, `RF-7`, `RF-9`.
  Diseñar e implementar la migración Alembic `0027_fo_unificado_valor_unitario.py` (`plan.md` §1):
  - `catalogo_materiales.valor_unitario NUMERIC(12,3) NOT NULL DEFAULT 1.000` + `CHECK >= 0`.
  - `ALTER TYPE NUMERIC(12,3)` del inventario de columnas de `plan.md` §1.2 (confirmado por introspección de `information_schema`; verificar `pg_depend` sin vistas dependientes).
  - Fusión de `inventario_fibra` (PK `material_id`, eliminación de `modulo`) con evento `FO_UNIFICADO` por material y verificación interna `SUM antes = SUM después`.
  - Sección de ruteo `FO`, `ck_secciones_tipo` ampliado, secciones legacy conservadas.
  - Re-publicación de las stored functions de `plan.md` §1.4 (sin `p_modulo`, `NUMERIC(12,3)`, validación de escala, `FOR UPDATE` y mensajes canónicos intactos; `DROP FUNCTION` de firmas previas).
  - Trigger de auditoría extendido con `valor_unitario` (§1.5) y `fn_valor_total_inventario()` (§1.6).
  - `downgrade()` conforme a §1.7 (aborta ante fracciones; restaura funciones verbatim; ledger intacto).
  - Decidir el tratamiento de `backend/db/ddl.sql` (sincronizar secciones tocadas o marcar como referencia histórica).
  **Hecho cuando:** la migración aplique y haga rollback limpiamente (`upgrade head` → `downgrade 0026` → `upgrade head` sobre `p2_test` con datos sembrados), conserve totales de stock (cero pérdida), mantenga conteo y contenido de `auditoria_eventos` previos, y `@dba-guard` emita su visto bueno (concurrencia `FOR UPDATE`, integridad referencial, inmutabilidad del ledger). *(Evidencia: `0027_fo_unificado_valor_unitario.py` entregado 2026-10-15; ciclo completo verificado 2 veces sobre `p2_test`; 8 columnas NUMERIC(12,3), fusión FO con verificación SUM antes==después, evento FO_UNIFICADO, E14 aborta sin pérdida, RF-9 legacy verificado; 9 desviaciones justificadas. Corrección post-T5: Drift T5-1 (nomenclatura Unidad de 0024 restaurada en fn_crear_seguimiento/fn_agregar_todo_seguimiento, cuerpos NUEVA y ANTERIOR).)*

- [x] **T3 (Fase 5 · `@sec-ops`)** — Cubre: `RF-8`, `RF-1`.
  Verificar RBAC y schemas del plan (`plan.md` §2.4): `require_admin` al enviar `valor_unitario` en `PATCH /catalogo/{id_lista}` y `PATCH /fibra/materiales/{material_id}`; default-deny en `GET /inventario/resumen-general`; `extra="forbid"` en todos los DTO de entrada nuevos o modificados (incluido el rechazo de `modulo`); ausencia de secretos o dependencias nuevas; ratificar C-4.
  **Hecho cuando:** los DTOs rechacen campos extra (422), un actor no administrador reciba 403 al enviar `valor_unitario`, el endpoint de resumen rechace solicitudes sin credenciales válidas y `@sec-ops` emita su aprobación escrita del plan y del contrato. *(Evidencia: primer dictamen RECHAZADO (hallazgos 1 MEDIUM y 2 LOW); correcciones aplicadas a plan §2.4/§2.2/§2.5, spec E15 y matriz RF-8; re-dictamen 2026-10-15 VEREDICTO: APROBADO, C-4 ratificada incondicionalmente; condiciones N1-N4 para T4/T5.)*

## Fase 7 — Implementación Backend

- [x] **T4 (Fase 7 · `@coder`)** — Cubre: `RF-1`, `RF-2`, `RF-3`, `RF-4`, `RF-6`, `RF-8`, `RF-9`. Depende de T2 y T3.
  Implementar el backend aprobado (`plan.md` §1.8, §2): modelos SQLAlchemy alineados al DDL (`Numeric(12,3)`, `InventarioFibra` con PK `material_id`), tipos `CantidadDecimal`/`CantidadMovimiento` con serialización a número JSON, DTOs de `plan.md` §2.2 con `extra="forbid"`, rutas de `plan.md` §2.3 (`/fibra`, `/fibra/materiales/{id}`, `/inventario/resumen-general`, secciones transferibles), ajuste de `services/transaccional.py`, `services/inventario.py` y `services/catalogo.py` a las nuevas firmas, mapeo de errores SQL a 400/422 y docstrings OpenAPI. Cero aritmética de stock ni de valor en Python; cero `UPDATE` directo de saldos.
  **Hecho cuando:** los endpoints devuelvan las respuestas en JSON con los contratos de `plan.md` §2 (números JSON para valores decimales, `valor_total` y `moneda: "MXN"` en `resumen-general`), `mypy app/ tests/` pase sin errores y no exista ninguna referencia a `modulo` en el contrato vivo. *(Evidencia: 1 archivo nuevo + 22 modificados en app/; mypy app/ 0 errores; verificación funcional real (resumen-general 200 con número JSON, RBAC 403 por presencia, null no-op, decimales, 422s); corrección post-T5: Drift T5-2 (handler RequestValidationError con sanitización de floats no finitos → 422, nunca 500).)*

- [x] **T5 (Fase 7 · `@tester` / `@qa-agent`)** — Cubre: `RF-1`..`RF-9` (backend). Depende de T4.
  `@tester`: escribir y actualizar pruebas de integración Pytest en `backend/tests/` con nomenclatura `test_RF_<n>_...` (matriz de `plan.md` §5: `test_fo_unificado.py`, `test_valor_unitario.py`, `test_stock_decimal.py`, `test_migracion_0027.py` y actualización de las suites existentes que usaban `modulo`/enteros); cada prueba asevera respuesta HTTP **y** estado de BD; incluir concurrencia (`asyncio.gather`), cancelación de movimientos legacy `FO_PAQUETE`/`FO_EN_USO` y entradas JSON `0.1`/`2.675`/`1e-4`.
  `@qa-agent`: validar de forma independiente el contrato contra el OpenAPI generado (campos faltantes/inventados, tipos, rutas y métodos) y registrar la **Congelación Contractual** según `plan.md` §3 (a–d), con aprobaciones de `@arq-reviewer` y `@sec-ops`.
  **Hecho cuando:** las pruebas pasen al 100 % (backend completo, incluida la suite previa adaptada) y `@qa-agent` registre la congelación contractual (PASS) con la evidencia del diff de OpenAPI; solo entonces se desbloquea T6. *(Evidencia: pytest 421/421 (3+ corridas), mypy 0 en 83 archivos; 4 suites nuevas (test_fo_unificado, test_valor_unitario, test_stock_decimal, test_migracion_0027) + helpers/migraciones.py; 11 suites actualizadas; drifts T5-1/T5-2 corregidos y re-verificados; @qa-agent: CONGELACIÓN CONTRACTUAL: REGISTRADA — PASS (2026-10-15), 2 hallazgos LOW no bloqueantes para T7.)*

## Fase 7 — Implementación Frontend (bloqueada hasta T5)

- [x] **T6 (Fase 7 · `@state-agent` → `@form-agent` → `@ui-agent` → `@ux-agent`)** — Cubre: `RF-1`, `RF-3`, `RF-5`, `RF-6`, `RF-7`, `RF-8`, `RF-9`, `RF-10`. Depende de T5 (congelación registrada).
  Implementar `plan.md` §4:
  - `@state-agent`: `types.ts` (sin `modulo`, `valor_unitario`/cantidades `number`, `ResumenGeneral`), `services/fibra.ts`, `services/inventory.ts`, hook `useResumenGeneral`, invalidación de `resumen-general` en todas las mutaciones que alteran existencias o valor (RFC OpenSpec si se detecta un contrato incompleto).
  - `@form-agent`: campo `Valor Unitario` (admin) y entradas decimales (Zod preliminar) en `MaterialForm`, `FibraMaterialForm`, `CampoCantidad` y flujos de cantidades; el backend sigue siendo la autoridad.
  - `@ui-agent`: tarjeta `Valor Total` entre `Total Materiales` y `Stock Total` (`KpiCards.tsx`), columna `VALOR UNITARIO` con `MXN` en las tres tablas, `FibraOptica.tsx` sin subapartados, `Sidebar.tsx` con una sola entrada "Inventario FO", etiquetas históricas y barrido de nomenclatura.
  - `@ux-agent`: estados de carga/error del indicador, confirmaciones con contexto y mensajes operativos para 400/422 decimales.
  - Tests vitest de `plan.md` §5 (RF-3, RF-5, RF-10 y actualización de suites de FO/formularios/Transferencias).
  **Hecho cuando:** la interfaz renderice las cifras en MXN (`Valor Total` segunda tarjeta y `VALOR UNITARIO` en las tres tablas), refresque mediante TanStack Query tras cada mutación, no exista selección de Paquete/En Uso, y `tsc -b`, eslint, vitest y `vite build` pasen sin errores ni advertencias. *(Evidencia: 2026-10-16 — `tsc -b` 0 errores; eslint 0; vitest 524/524 en 40 archivos (baseline 380); `vite build` OK. Contrato verificado contra el OpenAPI generado y una consulta real a la API (`/fibra`, `/inventario/resumen-general`, `/inventario/secciones/transferibles`). Entregado: `types.ts`/servicios/`useResumenGeneral`/`invalidarResumenGeneral` (state); `CampoCantidad` decimal, `schemas/valorUnitario.ts`, `MaterialForm`/`FibraMaterialForm` con Valor Unitario (form); `KpiCards` (`Valor Total` 2ª tarjeta), columna `VALOR UNITARIO` ×3 con `MonedaMxn`, `FibraOptica` sin subapartados, `Sidebar` «Inventario FO» (ui); `utils/errorMensaje.ts`, traductor de errores decimales, estados carga/error del indicador (ux). Pruebas nuevas: `KpiCards.test.tsx` (RF-5), `NomenclaturaFo.test.tsx` (RF-10), `valorUnitario.test.ts` (RF-2/RF-3), `errorMensaje.test.ts`, `resumenGeneral.test.tsx` + suites existentes adaptadas. **Observaciones para T7:** (1) `vite build` emite la advertencia de chunk >500 kB que ya existía en el baseline (556 kB → 560 kB); no se introdujo en T6 y no se resolvió (requiere code-splitting/ajuste de config fuera de alcance). (2) Contrato sin fuente de rol: no hay endpoint de rol del actor, por lo que el RBAC visual es la prop `esAdmin` (default `true`, el campo solo se envía si cambió) y el 403 del backend se muestra con su mensaje canónico. (3) Las secciones FO históricas no se emiten en `/secciones/transferibles`: el historial rotula como «Inventario FO» todo `almacen_id` no listado (RF-9; ver `etiquetaSeccionPorId`); un campo explícito de tipo en `MovimientoOut` lo haría determinista (candidato a RFC).)*

## Fase 8 — Validación y Auditoría

- [x] **T7 (Fase 8 · `@auditor` / `@qa-agent`)** — Cubre: `RF-1`..`RF-10`. Depende de T6.
  `@tester`: completar la suite y la **Matriz de Trazabilidad** (`RF-x` → prueba(s) → HTTP/BD).
  `@auditor`: emitir el **Drift Report** (Entity/Logic/Exception/Traceability Drift; código muerto: referencias residuales a `modulo`, `FO_PAQUETE`/`FO_EN_USO`, `FibraModulo`, `ModuloFo`; sin eliminar nada sin tarea aprobada) y verificar condiciones de archivado.
  `@qa-agent`: conformidad final Zero-Drift (spec = plan = tareas = pruebas = OpenAPI = TypeScript), criterios de liberación y comprobación de que no hay aritmética de stock/valor en React ni en Python.
  Verificaciones: `pytest`, `mypy`, `tsc -b`, eslint, `vite build`, `openspec validate --specs --strict`, aprobación de `@arq-reviewer` y `@sec-ops`.
  **Hecho cuando:** el paquete esté listo para moverse a `openspec/changes/archive/` y promover las specs a `openspec/specs/` (Matriz de Trazabilidad al 100 %, Drift Report `APPROVED`, QA `PASS`, aprobación humana), y se hayan planificado las actualizaciones de `openspec/openspec.yaml › domain_rules` de `plan.md` §7 para la Fase 9. *(Evidencia: 2026-10-16 — Matriz de Trazabilidad `trazabilidad.md` (RF 10/10 · escenarios 24/24 · E1..E15 15/15); correcciones H-1/H-2/M1-M4/M7 aplicadas; decisiones humanas D-1 (Opción B) y D-2 (Opción A) aplicadas el 2026-10-16 con visto bueno de `@sec-ops` (APROBADO) y `@arq-reviewer` (APROBADO CON CONDICIONES documentales, cumplidas); dictámenes `@auditor` APPROVED WITH CONDITIONS y `@qa-agent` PASS WITH CONDITIONS cuyas condiciones (D-1, D-2, D-4, aprobación humana) quedan cumplidas. Compuertas finales: pytest 446 · sql_tests 25 · mypy 0 · tsc 0 · eslint 0 · vitest 533 · `vite build` sin advertencias · `openspec validate --specs --strict` 3/3. Plan de la Fase 9 ejecutado a continuación.)*

---

## Matriz de cobertura RF → Tarea

| RF | Alias | Tareas |
| :-- | :-- | :-- |
| RF-1 | REQ-FO-001 | T1, T2, T3, T4, T5, T6, T7 |
| RF-2 | REQ-VALOR-001 | T1, T2, T4, T5, T7 |
| RF-3 | REQ-VALOR-002 | T1, T2, T4, T5, T6, T7 |
| RF-4 | REQ-VALOR-003 | T1, T2, T4, T5, T7 |
| RF-5 | REQ-VALOR-004 | T1, T6, T7 |
| RF-6 | REQ-DEC-001 | T1, T2, T4, T5, T6, T7 |
| RF-7 | REQ-VALOR-005 | T1, T2, T5, T6, T7 |
| RF-8 | REQ-VALOR-006 | T1, T3, T4, T5, T6, T7 |
| RF-9 | REQ-FO-002 | T1, T2, T4, T5, T6, T7 |
| RF-10 | REQ-FO-003 | T1, T6, T7 |

## Cierre (Fase 9 — Evolución; posterior a T7)

Tras la aprobación humana: mover el paquete a `openspec/changes/archive/2026-10-fo-unificado-valor-unitario/`, promover los `RF-n` a `openspec/specs/`, actualizar `openspec/openspec.yaml › domain_rules` y verificar que `.agents.md` no contiene referencias a este paquete ni a `docs/1 Changes.docx` (efimeridad del insumo).

---

## T7 — Registro de ejecución (2026-10-16)

**Correcciones de drift aplicadas durante T7** (hallazgos de `@tester`/`@auditor`/`@qa-agent`/`@arq-reviewer`; el contrato OpenAPI no cambió, la Congelación Contractual de T5 sigue vigente):
- **H-1 (RF-7, Logic Drift):** el evento `MATERIAL_MODIFICADO` por cambio de `valor_unitario` registraba el rol de BD en lugar del actor. Corrección: `0027` §1.5 usa `COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER)` y `services/catalogo.py` fija `app.actor` antes de mutar el ORM (el `session.execute` auto-vaciaba el `UPDATE`). Prueba `test_RF_007_evento_de_valor_atribuye_al_actor_http` en verde.
- **M3/H-2 (RF-3 Option-driven):** `ConfigLocalForm` muestra el Valor Unitario como solo lectura.
- **M1 (Constitución §7.2.2):** `vite build` sin advertencias (code-splitting con `React.lazy` por página).
- **L3:** el cambio de Valor Unitario invalida `['stock']` (todas las secciones) y `['equipo']` además de `resumen-general`.
- **M4 (decisión T2 sobre `ddl.sql`):** marcado como **REFERENCIA HISTÓRICA**; la fuente de verdad del esquema son las migraciones Alembic (head `0027`). `README.md` corregido.
- **M2:** `backend/sql_tests/` adaptada a 0027 (25/25).
- **M7:** `openspec/openspec.yaml › paths` regenerado desde el OpenAPI vigente.
- **Matriz de Trazabilidad:** `trazabilidad.md` (RF 10/10, escenarios 24/24, E1..E15 15/15).
- **Pruebas añadidas por seguridad (@sec-ops L-3):** RBAC de `PATCH /fibra/materiales/{id}` con `null`/mixto, admin + `null` no-op, `modulo` en catálogo → 422.

**Compuertas finales (corrida serializada):** pytest 443 passed · sql_tests 25 passed · mypy 0 (84 archivos) · tsc 0 · eslint 0 · vitest 533 passed (43 archivos) · `vite build` sin advertencias · `openspec validate --specs --strict` 3/3 · `openspec validate <cambio> --strict` válido.

**Evidencia histórica actualizada:** la cifra «421/421» de T5 corresponde a la línea base de la Congelación; la suite vigente es 443 (+22 de T7).

### Decisiones humanas (RESUELTAS 2026-10-16; clasificación original de los dictámenes: D-1 bloquea el archivado · D-2 es pre-despliegue · D-3 es Fase 9 · D-4 es previo al archivado)

| ID | Tema | Opciones | Recomendación |
| :-- | :-- | :-- | :-- |
| **D-1 (M5, RF-9 cláusula 3) — BLOQUEA ARCHIVADO** | La API aún permite **crear** un borrador nuevo con origen/destino legacy `FO_PAQUETE`/`FO_EN_USO` (`services/movimientos.py`), mientras que `spec.md` RF-9 dice que todo movimiento **nuevo** con FO debe referenciar el Inventario FO unificado. La UI ya no los ofrece y el contrato no los emite. | **A)** rechazar con 422 la creación de borradores nuevos con origen legacy (cambio backend: reabre la Congelación Contractual y exige actualizar las pruebas de E8 para sembrar los legacy por SQL). **B)** aclarar `spec.md` RF-9 (fe de erratas): «no se ofrecen en UI ni contrato; la API conserva aceptación para BORRADORES/movimientos históricos (E8)». | B (menor riesgo; E8 exige poder confirmar/cancelar legacy). Salvedades de @arq-reviewer: la fe de erratas de `spec.md` RF-9 (L3) debe ser explícita y aprobada por un humano, sin debilitar el escenario «Orígenes antiguos no seleccionables»; `trazabilidad.md` marcará la cláusula 3 como «cubierta parcialmente, erratum D-1»; seguimiento en Fase 9 para cerrar con 422 cuando no queden borradores legacy. |
| **D-2 (H3 arq-reviewer, RF-9 / §3.2) — PRE-DESPLIEGUE** | La migración crea la sección `FO` sin trasladar `actor_almacen_scopes` de `FO_PAQUETE`/`FO_EN_USO`: un operador no admin con scope solo sobre las secciones legacy recibirá 403 al transferir desde «Inventario FO» (falla cerrada; sin riesgo de seguridad, sí regresión operativa). | **A)** paso de migración que copie esos scopes a la sección `FO` (`ON CONFLICT DO NOTHING`; el `downgrade` debe retirarlos), con visto bueno de `@sec-ops`. **B)** runbook operativo aprobado previo al despliegue. | A, antes del primer despliegue permanente y mientras 0027 siga editable in situ (si se difiere, va en `0028`). Consideraciones de @arq-reviewer: es una expansión de privilegio intencional (un actor con scope solo sobre «En Uso» obtiene el de todo el inventario FO unificado; visto bueno de @sec-ops); el `downgrade` debe retirar primero los scopes copiados y el aborto del paso 1b debe tolerarlos. En `p2`, `demo-operador` tiene scope sobre `FO_PAQUETE`/`FO_EN_USO` y ninguno sobre la sección `FO`. |
| **D-3 (M1 arq / H4) — FASE 9** | `RBAC visual` por `esAdmin` inerte (no hay fuente de rol en el contrato) y etiqueta histórica por inferencia (`etiquetaSeccionPorId`). | Elevar a RFC de Fase 9: exponer rol del actor y tipo explícito de sección en `MovimientoOut`/`AuditoriaOut` (invalida la congelación actual). | RFC en Fase 9 |
| **D-4 — PREVIO AL ARCHIVADO** | Commit del trabajo (T6 + T7). El repositorio tiene cambios sin confirmar. | Commit con aprobación humana (no se realizó). | — |

### Plan de la Fase 9 (no ejecutar antes de la aprobación humana de T7)

1. **Archivado:** `git mv openspec/changes/2026-10-fo-unificado-valor-unitario openspec/changes/archive/` y verificar que `.agents.md` no contiene referencias al paquete ni a `docs/1 Changes.docx` (estado actual: limpio). Decidir la baja de `docs/1 Changes.docx` (insumo efímero).
2. **`openspec/openspec.yaml › domain_rules`:** añadir `fn_valor_total_inventario` a `mandatory_functions` (y reconciliar la lista con `fn_cargar_stock_inicial_fibra`/`fn_ajustar_stock_general`); ampliar `prohibition` a «aritmética de stock **y de valor** en Python/React»; nuevas reglas `fo_unificado` (PK `material_id`, ruteo por sección `FO`, `FO_PAQUETE`/`FO_EN_USO` solo históricos, `modulo` → 422), `valor_unitario` (atributo de catálogo NUMERIC(12,3) MXN, default 1.000, RBAC admin por presencia, `null` sin efecto, auditado por trigger, Valor Total global, sin multimoneda) y `decimal_quantities` (NUMERIC(12,3), número JSON, `stock_minimo` entero, 22003→400); `audit_ledger_immutability`: eventos `FO_UNIFICADO` y `MATERIAL_MODIFICADO` con `valor_unitario`; reescribir `quick_operator_semantics` y `transferencias_multi_origen` (hoy hablan de «módulos FO»); `nomenclature_glossary`: «Inventario FO».
3. **Specs maestras (`openspec/specs/`):** promover con identificadores `[REQ-…]` únicamente (REQ-FO-001..003, REQ-VALOR-001..006, REQ-DEC-001; **no** usar `RF-n` en los encabezados: `001_core_logistics` ya define `RF-3`/`RF-5` con otro significado) traduciendo «deberá» → «SHALL». En `003_inventory_dashboard`: retirar `REQ-FIBER-001/002/003`; reescribir `REQ-DASH-003/004/006` y el escenario «En Uso» de `REQ-DASH-009`; `REQ-MAT-005` y `REQ-TEAM-001` (decimal; Valor Unitario solo lectura). En `002_stock_transfer`: `REQ-STOCK-006` («positive integer quantities») → decimal. Añadir a `.agents.md` §3 la nota de que los valores técnicos históricos (`FO_PAQUETE`, `FO_EN_USO`, `TEAMS`, `DEVOL`) quedan exentos en ledger y `secciones.tipo` (L2: requiere aprobación humana).
4. **Documentación:** `README.md` (historial de cambios, secciones de FO).
5. **Seguimiento (cambios OpenSpec propios, fuera de este paquete):** cierre con HTTP 422 de la creación de borradores con origen legacy (A diferida de D-1, cuando no existan borradores legacy); autenticación real (`X-Actor` hardcodeado, preexistente); `material_id`/`almacen_id` fuera de INT4 → 500 (preexistente; `le=2147483647` o handler global `DBAPIError`); `{"descripcion": null}`/`{"is_active": null}` en `PATCH /catalogo` (NOT NULL, preexistente) y `stock_inicial: 0` sin `seccion_id`; `ActaItem` de TS sin `origen_almacen_id`/`origen_nombre`; retirada de código muerto preexistente (`cargarStockInicialFibra`/`ajustarStockFibra` sin invocadores en la UI, rama `children` del Sidebar, `formatMxnConMoneda`/`parseCantidadDecimal` solo en tests, imports no usados en `models/`); `resultado='OK'` vs `'EXITO'` en eventos `FO_UNIFICADO` (decisión documental, plan §1.3).

### Regla de ventana de edición in situ de `0027` (@arq-reviewer, condición 2)

La migración `0027` solo puede editarse **in situ** mientras no se haya desplegado ni publicado fuera de dev/test (precedente Drift T5-1; el commit `0bf73fc` no está en ningún remoto). El fix de H-1 se aplicó así y `p2`/`p2_test` recibieron el `CREATE OR REPLACE` equivalente; cualquier otra base ya marcada en `0027` debe parchearse con el trigger de H-1 (Alembic no re-ejecuta revisiones). **Tras el primer despliegue o archivado, todo cambio de esquema va en `0028` o posterior.** Los 87 eventos `MATERIAL_MODIFICADO` históricos de `p2` con `usuario='p2admin'` son anteriores al fix: el ledger es append-only y no se reescribe.

### Dictámenes de la Fase 8 (2026-10-16)

| Rol | Ronda 1 | Re-revisión tras correcciones |
| :-- | :-- | :-- |
| `@tester` | Matriz de Trazabilidad 100 % (`trazabilidad.md`); H-1/H-2 detectados | — |
| `@auditor` | REJECTED (M1..M7) | **APPROVED WITH CONDITIONS** (sin CRITICAL/MEDIUM abiertos; M1-M4, M6, M7, H-1 cerrados; condiciones C-1..C-5 = D-1, D-2, D-4, paridad de entornos, aprobaciones finales) |
| `@qa-agent` | FAIL (H-1) | **PASS WITH CONDITIONS** (OpenAPI idéntico a la congelación; DoD 1-7 PASS; DoD 8 pendiente de aprobación humana y D-1) |
| `@arq-reviewer` | RECHAZADO (H1) | **APROBADO CON CONDICIONES** (sin enmienda constitucional) |
| `@sec-ops` | APROBADO | **APROBADO** (sin hallazgos ≥ MEDIUM; `X-Actor` sin autenticar queda como seguimiento fuera del paquete) |

Adiciones al plan de Fase 9 (@arq-reviewer): (a) regla de atribución en `audit_ledger_immutability` (los triggers toman `app.actor` y el servicio lo fija antes de mutar el ORM); (b) reflejar en `domain_rules` el resultado de D-1 y D-2; (c) ejecutar `openspec validate --specs --strict` tras la promoción; (d) archivar `trazabilidad.md` con el paquete.

> **T7 permanece `[ ]` hasta la aprobación humana** (decisiones D-1 y D-4, y aprobación del archivado). Todo lo demás de T7 está ejecutado y registrado arriba.

### Resolución de las decisiones humanas (2026-10-16)

- **D-1 → Opción B aplicada:** fe de erratas en `spec.md` RF-9 (acota la cláusula 3 a la interfaz y al contrato publicado; la API conserva la aceptación de borradores legacy por E8). Sin cambios de backend ni de OpenAPI: la Congelación Contractual sigue vigente. `@arq-reviewer`: coherente con E8, sin enmienda constitucional. Seguimiento: cerrar la puerta con HTTP 422 cuando no existan borradores legacy (cambio con contrato propio).
- **D-2 → Opción A aplicada:** `0027` Paso 4b copia a la sección `FO` los scopes de `FO_PAQUETE`/`FO_EN_USO` (`ON CONFLICT DO NOTHING`; solo actores con scope legacy; scopes legacy conservados) y el `downgrade()` retira primero los scopes copiados antes de abortar por referencias. Pruebas `test_RF_009_D2_*` (3). `p2` recibió el equivalente. **Visto bueno `@sec-ops`: APROBADO** (sin hallazgos ≥ MEDIUM; endurecimiento L-1 `fo.nombre='Inventario FO'` y caso límite L-2 documentado y probado). **`@arq-reviewer`: conforme a las salvedades** (downgrade retira primero los scopes copiados, aborto tolerante, idempotencia, ventana in situ abierta). Efecto lateral aceptado: los actores con scope FO ven en Auditoría los eventos de la sección FO.
- **D-3 → Fase 9 (RFC):** rol del actor expuesto por el contrato y tipo explícito de sección en `MovimientoOut`/`AuditoriaOut`.
- **D-4 → commit local realizado** (T6/T7 con `0027`+D-2); T7 marcada `[x]`.

---

## Fase 9 — Registro de ejecución (2026-10-16)

- **Archivado:** paquete movido (`git mv`) a `openspec/changes/archive/2026-10-fo-unificado-valor-unitario/`; `openspec/changes/` queda solo con `archive/`.
- **Specs maestras promovidas** (identificadores `[REQ-…]`, «deberá» → «SHALL»; sin prefijo `RF-n`):
  - `001_core_logistics`: REQ-FO-001, REQ-FO-002 (con la fe de erratas D-1), REQ-DEC-001, REQ-VALOR-001, REQ-VALOR-003, REQ-VALOR-005, REQ-VALOR-006.
  - `003_inventory_dashboard`: REQ-FO-003, REQ-VALOR-002, REQ-VALOR-004; reescritos REQ-DASH-003 (una sola entrada «Inventario FO»), REQ-DASH-004 (cinco tarjetas), REQ-DASH-006/008/009 (VALOR UNITARIO), REQ-TEAM-001 (Valor Unitario solo lectura) y REQ-MAT-005 (decimales); **retirados REQ-FIBER-001/002/003** (y el escenario «METROS RESTANTES» de REQ-DASH-009).
  - `002_stock_transfer`: REQ-STOCK-006 (cantidades decimales positivas).
- **`openspec/openspec.yaml`:** `paths` (T7) y `domain_rules` actualizados (`fn_valor_total_inventario`, `fn_cargar_stock_inicial_fibra`/`fn_ajustar_stock_general`, prohibición de aritmética de valor, reglas `fo_unificado`/`valor_unitario`/`decimal_quantities`, eventos `FO_UNIFICADO`/`MATERIAL_MODIFICADO` y regla de atribución del actor, glosario con «Inventario FO», «Valor Unitario», «Valor Total» y los valores técnicos históricos).
- **`.agents.md`:** verificado sin referencias a este paquete ni a `docs/1 Changes.docx`.
- **Pendiente de aprobación humana (fuera de este paquete):** (1) nota en `.agents.md` §3 (L2) sobre los valores técnicos históricos exentos — ya reflejada en `openspec.yaml › nomenclature_glossary`; (2) baja de `docs/1 Changes.docx` (insumo efímero); (3) actualización del historial/versión del `README.md`; (4) los cambios de seguimiento del plan §5 (RFC de rol del actor y tipo de sección, cierre con 422 de borradores legacy, autenticación real, etc.).
