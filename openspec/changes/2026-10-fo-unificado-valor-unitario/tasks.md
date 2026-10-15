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

- [ ] **T6 (Fase 7 · `@state-agent` → `@form-agent` → `@ui-agent` → `@ux-agent`)** — Cubre: `RF-1`, `RF-3`, `RF-5`, `RF-6`, `RF-7`, `RF-8`, `RF-9`, `RF-10`. Depende de T5 (congelación registrada).
  Implementar `plan.md` §4:
  - `@state-agent`: `types.ts` (sin `modulo`, `valor_unitario`/cantidades `number`, `ResumenGeneral`), `services/fibra.ts`, `services/inventory.ts`, hook `useResumenGeneral`, invalidación de `resumen-general` en todas las mutaciones que alteran existencias o valor (RFC OpenSpec si se detecta un contrato incompleto).
  - `@form-agent`: campo `Valor Unitario` (admin) y entradas decimales (Zod preliminar) en `MaterialForm`, `FibraMaterialForm`, `CampoCantidad` y flujos de cantidades; el backend sigue siendo la autoridad.
  - `@ui-agent`: tarjeta `Valor Total` entre `Total Materiales` y `Stock Total` (`KpiCards.tsx`), columna `VALOR UNITARIO` con `MXN` en las tres tablas, `FibraOptica.tsx` sin subapartados, `Sidebar.tsx` con una sola entrada "Inventario FO", etiquetas históricas y barrido de nomenclatura.
  - `@ux-agent`: estados de carga/error del indicador, confirmaciones con contexto y mensajes operativos para 400/422 decimales.
  - Tests vitest de `plan.md` §5 (RF-3, RF-5, RF-10 y actualización de suites de FO/formularios/Transferencias).
  **Hecho cuando:** la interfaz renderice las cifras en MXN (`Valor Total` segunda tarjeta y `VALOR UNITARIO` en las tres tablas), refresque mediante TanStack Query tras cada mutación, no exista selección de Paquete/En Uso, y `tsc -b`, eslint, vitest y `vite build` pasen sin errores ni advertencias.

## Fase 8 — Validación y Auditoría

- [ ] **T7 (Fase 8 · `@auditor` / `@qa-agent`)** — Cubre: `RF-1`..`RF-10`. Depende de T6.
  `@tester`: completar la suite y la **Matriz de Trazabilidad** (`RF-x` → prueba(s) → HTTP/BD).
  `@auditor`: emitir el **Drift Report** (Entity/Logic/Exception/Traceability Drift; código muerto: referencias residuales a `modulo`, `FO_PAQUETE`/`FO_EN_USO`, `FibraModulo`, `ModuloFo`; sin eliminar nada sin tarea aprobada) y verificar condiciones de archivado.
  `@qa-agent`: conformidad final Zero-Drift (spec = plan = tareas = pruebas = OpenAPI = TypeScript), criterios de liberación y comprobación de que no hay aritmética de stock/valor en React ni en Python.
  Verificaciones: `pytest`, `mypy`, `tsc -b`, eslint, `vite build`, `openspec validate --specs --strict`, aprobación de `@arq-reviewer` y `@sec-ops`.
  **Hecho cuando:** el paquete esté listo para moverse a `openspec/changes/archive/` y promover las specs a `openspec/specs/` (Matriz de Trazabilidad al 100 %, Drift Report `APPROVED`, QA `PASS`, aprobación humana), y se hayan planificado las actualizaciones de `openspec/openspec.yaml › domain_rules` de `plan.md` §7 para la Fase 9.

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
