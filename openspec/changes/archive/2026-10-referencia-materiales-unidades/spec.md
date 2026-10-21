# Especificación — ETAPA 3/3: REFERENCIA DE MATERIALES POR UNIDAD

**Paquete:** `2026-10-referencia-materiales-unidades` · **Fase SDD:** 3 (Especificación) · **Estado:** redactada y clarificada en T1 (Fase 4 resuelta, ver §8); pendiente de aprobación del humano.
**Fuente de requisitos:** `docs/2 Unities Functions.docx`, sección «Referencia», y las decisiones D-1..D-4 de `proposal.md`. Gobernanza: `docs/constitution.md` (L1), `.agents.md` (L2). Separación Constitución §1.2: este documento define el *qué*; el *cómo* está en `plan.md`.

## 1. Propósito

Dar a cada Unidad una **Referencia de materiales**: una lista visual, sin efecto contable, con la Descripción, la U.M. y la Cantidad Semanal de los materiales que la Unidad maneja. Se consulta desde Inventario por Unidad y se configura (añadir, modificar, eliminar) con materiales ya existentes, sin reescribirlos a mano.

## 2. Alcance

**Dentro:** tabla propia por Unidad, API de lectura y escritura, botón «Referencia», panel «Materiales Referencia», alta con selección dependiente (origen → material), modificar y eliminar, auditoría de las mutaciones.
**Fuera:** unidades de medida nuevas, equivalencias y conversiones; cualquier efecto sobre inventarios, catálogo, movimientos, seguimientos, actividades, actas o reportes; validación de la cantidad semanal contra el stock; exportación; autenticación real.

## 3. Glosario y nomenclatura

- **Unidad:** texto oficial de UI. En código, rutas y parámetros el identificador técnico permanece `equipo`/`equipo_id` (REQ-UNI-005; protegido por `backend/tests/test_unidad_nomenclatura.py`).
- **Referencia:** lista visual de materiales de una Unidad. **Línea de Referencia:** un material con su cantidad semanal dentro de la Referencia de una Unidad.
- **U.M. de la Referencia:** la U.M. efectiva de la Unidad para ese material: la U.M. local configurada para el material en esa Unidad o, si no hay ninguna, la U.M. del catálogo (decisión Q2).
- **Cantidad Semanal:** cantidad visual de manejo semanal de un material; no es stock y no se valida contra él.
- **Inventario General / Inventario FO:** orígenes ofrecidos por la interfaz para elegir el material (etiqueta oficial «Inventario FO», `.agents.md` §3). Son ayuda de selección y no se persisten.
- **Etiquetas de interfaz:** «Referencia», «Materiales Referencia», «Descripción», «U.M.», «Cantidad Semanal», «+ Agregar», «+ Agregar línea», «Modificar», «Eliminar».

## 4. Reglas de negocio (extraídas del documento fuente)

- **RN-1** La Referencia es independiente para cada Unidad.
- **RN-2** La Referencia es solo un aspecto visual: no afecta inventarios, base de datos de inventarios ni materiales existentes.
- **RN-3** El botón «Referencia» aparece tanto en la subsección Consulta (solo despliega la tabla) como en Configuración (añadir, modificar y eliminar).
- **RN-4** Los materiales se eligen de los inventarios existentes (General o FO) con su nomenclatura oficial, sin escribirlos a mano. Es una restricción de la interfaz: la API acepta cualquier material activo del catálogo.
- **RN-5** La cantidad capturada no afecta el inventario.
- **RN-6** Cualquier material de la tabla puede modificarse o eliminarse.
- **RN-7** `cantidad_semanal` no es un saldo: la invariante de saldo no negativo (Constitución §2.1) y la prohibición de `UPDATE` directo sobre saldos no le aplican; toda mutación de la Referencia queda auditada (§6.2).

## 5. Requisitos

Cada requisito tiene identificador inmutable `REQ-REF-NNN` (Constitución §1.5).

### Requirement: REQ-REF-001 Botón «Referencia» en Inventario por Unidad
The system SHALL show in Inventario por Unidad, for the selected Unidad, a button named «Referencia» right-aligned immediately above the inventory area and below the subsection tabs, visible in every view of Consulta and in Configuración, that shows and hides the «Materiales Referencia» panel. The system SHALL NOT show the button in CONSUMO or ACTIVIDADES, and SHALL expose the open/closed state to assistive technology.

#### Scenario: Button in Consulta and Configuración
- **WHEN** the operator opens Inventario por Unidad with a Unidad selected
- **THEN** the button «Referencia» is present in every view of Consulta and in Configuración, absent in CONSUMO and ACTIVIDADES, and pressing it toggles the panel with `aria-expanded` updated

### Requirement: REQ-REF-002 Tabla «Materiales Referencia»
The system SHALL present the Referencia as a table titled «Materiales Referencia» with the columns «Descripción», «U.M.» and «Cantidad Semanal», one row per Línea de Referencia, without any stock, valor or alert column. WHEN the Unidad has no lines, the system SHALL show an empty-state message instead of an empty table.

#### Scenario: Columns and values
- **WHEN** the panel is open for a Unidad with lines
- **THEN** each row shows the material description, its U.M. and its Cantidad Semanal, and the three column headers are exactly «Descripción», «U.M.» and «Cantidad Semanal»

#### Scenario: Empty Referencia
- **WHEN** the Unidad has no lines
- **THEN** the panel shows a message that the Referencia is empty (and, in Configuración, how to add materials) and no table rows

### Requirement: REQ-REF-003 Consulta es solo lectura
WHILE the operator is in the Consulta subsection, the system SHALL show the Referencia table in read-only mode and SHALL NOT offer «+ Agregar», «Modificar» or «Eliminar».

#### Scenario: No edit controls in Consulta
- **WHEN** the panel is open in Consulta
- **THEN** no add, modify or delete control is rendered and the panel issues no request other than the Referencia listing

### Requirement: REQ-REF-004 Independencia por Unidad
The system SHALL keep one Referencia per Unidad: the lines of a Unidad SHALL NOT appear in another Unidad's Referencia, and WHEN the selected Unidad changes the panel SHALL keep its open or closed state, show the lines of the new Unidad and discard any unsaved form or pending confirmation, so that no line is ever sent to a Unidad other than the one it was entered for.

#### Scenario: Switching Unidad
- **WHEN** two Unidades hold different lines and the operator switches the selected Unidad
- **THEN** the panel shows only the lines of the newly selected Unidad and an unsaved add form is discarded

### Requirement: REQ-REF-005 Consulta de la Referencia
WHEN the client requests `GET /api/v1/equipos/{equipo_id}/referencia`, the system SHALL return the lines of that Unidad as `{items, total}`, each item carrying `material_id`, `codigo`, `descripcion`, `u_m` and `cantidad_semanal`, ordered by `descripcion` ascending (database collation) and then `material_id` ascending. `descripcion` and `codigo` SHALL be read from the catalog at query time and `u_m` SHALL be the effective U.M. of the Unidad (the local U.M. configured for that material in the Unidad or, if none, the catalog U.M.); `total` SHALL count only the listed items. Lines whose catalog material is inactive SHALL NOT be listed but SHALL be preserved.

#### Scenario: Ordered listing with live catalog data
- **WHEN** the Unidad holds several lines, the catalog description of one material changes and the Unidad configures a local U.M. for another
- **THEN** the next response is ordered by descripción, shows the updated description and the local U.M. where configured (catalog U.M. elsewhere), with `total` equal to the number of listed items

#### Scenario: Inactive material omitted, line preserved
- **WHEN** a catalog material of a line is deactivated and later reactivated
- **THEN** the line is absent from the listing while inactive and reappears, unchanged, after reactivation

### Requirement: REQ-REF-006 Alta de líneas
WHEN the client submits `POST /api/v1/equipos/{equipo_id}/referencia` with `{"lineas":[{"material_id","cantidad_semanal"}]}` carrying 1 to 50 lines, the system SHALL validate the whole payload and, only if every line is valid, create all the lines in one transaction and respond 201 with the created lines ordered as in the listing and `total` equal to the number of created lines. The system SHALL reject the whole payload, creating nothing, if any line is invalid; the error SHALL identify the offending line (`coordinates` with the zero-based `linea` index and the `material_id`). When several errors coexist, the system SHALL report them in this order: payload duplicates (422), unknown or inactive materials (404, first line by index), materials already in the Referencia (409, first line by index). The limit of 50 lines is a defensive limit of this package, not of the source document. The origin chosen in the interface (Inventario General or Inventario FO) SHALL NOT be part of the contract.

#### Scenario: Valid batch
- **WHEN** a payload with three valid lines for an active Unidad is submitted by an authorized actor
- **THEN** the response is 201, the three lines exist in the Unidad's Referencia and exactly one audit event per line is written

#### Scenario: All or nothing
- **WHEN** a payload carries two valid lines and one invalid line (unknown material, zero quantity or repeated material)
- **THEN** the response is 404, 422 or 409 as applicable, no line is created and no audit event is written

### Requirement: REQ-REF-007 Validación de la línea
IF a line carries `cantidad_semanal` that is not greater than zero or has more than 3 decimals or more than 12 digits in total (maximum 999 999 999.999), THEN the system SHALL respond HTTP 422. IF the payload carries fields not declared by the contract, a `material_id` that is not a positive INT4, no lines or more than 50 lines, THEN the system SHALL respond HTTP 422 in the standard validation body. IF the payload carries the same `material_id` twice, THEN the system SHALL respond HTTP 422 `REFERENCIA_LINEA_DUPLICADA` with the coordinates of the second occurrence. IF a `material_id` does not exist in the catalog or its material is inactive, THEN the system SHALL respond HTTP 404 `MATERIAL_NO_ENCONTRADO`. IF the material is already in the Unidad's Referencia, THEN the system SHALL respond HTTP 409 `REFERENCIA_DUPLICADA` and SHALL NOT modify the existing line.

#### Scenario: Rejected inputs create nothing
- **WHEN** a request carries a quantity of 0, a quantity of 1.2345, an extra field, 51 lines or a repeated material
- **THEN** the response is 422 and no row is written

#### Scenario: Unknown, inactive or already referenced material
- **WHEN** a request names a non-existent or inactive material, or a material already in the Referencia
- **THEN** the response is 404 `MATERIAL_NO_ENCONTRADO` or 409 `REFERENCIA_DUPLICADA` respectively and the existing lines are unchanged

### Requirement: REQ-REF-008 Modificación de una línea
WHEN the client submits `PATCH /api/v1/equipos/{equipo_id}/referencia/{material_id}` with `{"cantidad_semanal"}`, the system SHALL update only the quantity of that line, refresh its modification timestamp and respond 200 with the line. The system SHALL NOT allow changing the material of a line. IF the new quantity equals the stored one, THEN the system SHALL respond 200 without writing, without refreshing the modification timestamp and without auditing (idempotent no-op). IF the line does not exist, or exists but its catalog material is inactive, THEN the system SHALL respond HTTP 404 `REFERENCIA_NO_ENCONTRADA` and SHALL NOT modify it.

#### Scenario: Quantity updated
- **WHEN** an authorized actor sends a valid new quantity for an existing line
- **THEN** the response is 200 with the new quantity, the other lines are unchanged and one audit event with the previous and new quantity is written

#### Scenario: Missing line
- **WHEN** the line does not exist for the Unidad, or its catalog material is inactive
- **THEN** the response is 404 `REFERENCIA_NO_ENCONTRADA` and nothing is written

#### Scenario: Same quantity is a no-op
- **WHEN** the new quantity equals the stored quantity
- **THEN** the response is 200, the modification timestamp is unchanged and no audit event is written

### Requirement: REQ-REF-009 Eliminación de una línea
WHEN the client submits `DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id}`, the system SHALL remove that line of the Referencia, respond 204 and keep the previous values in the audit event. IF the line does not exist, or exists but its catalog material is inactive, THEN the system SHALL respond HTTP 404 `REFERENCIA_NO_ENCONTRADA` and SHALL NOT delete it. The interface SHALL ask for confirmation before deleting.

#### Scenario: Line removed with audit
- **WHEN** an authorized actor deletes an existing line
- **THEN** the response is 204, the line no longer exists, the material remains in the catalog and in every inventory, and an audit event keeps the removed quantity

### Requirement: REQ-REF-010 Aislamiento y autorización por Unidad
The system SHALL authorize every Referencia endpoint by Unidad: the administrator SHALL access every Unidad; any other actor SHALL access only the Unidades it belongs to. Writes SHALL additionally apply the same authentication rule as the Unidad configuration (the actor is an administrator or has at least one section scope assigned; 403 otherwise); reads require only Unidad membership. The precedence SHALL be: (1) parameter, body and `X-Actor` validation (422; identifiers beyond INT4 in the path, 400 `NUMERIC_OUT_OF_RANGE`); (2) for writes, the authentication rule (403); (3) the Unidad exists and is active, for reads and writes (404 otherwise, before evaluating membership); (4) membership (403 with the current authorization body); (5) the operation. IF `X-Actor` is missing or invalid, THEN the system SHALL respond 422 without querying business data.

#### Scenario: Foreign Unidad
- **WHEN** a non-administrator actor requests or modifies the Referencia of a Unidad it does not belong to
- **THEN** the response is 403 and no row is read or written

#### Scenario: Inactive Unidad
- **WHEN** a member lists, then tries to add a line to, a decommissioned Unidad
- **THEN** both responses are 404 without side effects

#### Scenario: Write without section scope
- **WHEN** a Unidad member with no section scope assigned and not administrator tries to create, modify or delete a line
- **THEN** the response is 403 and nothing is written, while that member can still list the Referencia

### Requirement: REQ-REF-011 Sin efecto sobre inventarios ni catálogo
The system SHALL NOT write, when creating, updating or deleting Referencia lines, any table other than the Referencia table and the audit ledger (in particular `inventario_equipos`, `inventario_almacen`, `inventario_fibra`, `catalogo_materiales`, `equipo_material_config`, `ums`, `equipos`, `movimientos_cabecera`, `movimientos_detalle`, `seguimientos`, `seguimiento_items`, `actividades_reportes` and `actas_reportes`), nor SHALL it invoke the Stored Functions that mutate stock. Reading the Referencia SHALL NOT write any row or emit any audit event.

#### Scenario: Business tables intact
- **WHEN** lines are created, modified and deleted, and the Referencia is listed
- **THEN** the snapshot of every table listed above is identical before and after, and listing emits no audit event

### Requirement: REQ-REF-012 Auditoría de las mutaciones
WHEN a line is created, modified or deleted, the system SHALL write, atomically with the mutation and in the same transaction, one immutable audit event (`REFERENCIA_LINEA_CREADA`, `REFERENCIA_LINEA_MODIFICADA` or `REFERENCIA_LINEA_ELIMINADA`) with the actor, the `material_id`, the `equipo_id` and the previous and new values (`modulo`, `accion`, `valores_anteriores`, `valores_nuevos`). IF the transaction is rolled back, THEN the system SHALL leave neither the line nor the event. A modification that does not change the quantity SHALL NOT write an event.

#### Scenario: One event per mutation
- **WHEN** a line is created, its quantity modified and then deleted
- **THEN** exactly three events exist, in that order, with the corresponding previous and new values, and a rejected request leaves no event

### Requirement: REQ-REF-013 Alta con selección dependiente en Configuración
WHILE the operator is in Configuración with the panel open, the system SHALL offer a «+ Agregar» button that shows a form where each line has its own origin selector («Inventario General», «Inventario FO»), a dependent Material selector listing the materials of the chosen origin with their current stock between parentheses as a visual aid, a «Cantidad» field and a delete control, plus a «+ Agregar línea» button; WHEN the operator confirms, the system SHALL send all the lines in one request. A material present in several General sections SHALL appear as one option per section, with the section as suffix, all mapping to the same `material_id`; the system SHALL NOT add up stock on the client. Changing the origin of a line SHALL reset its material. The system SHALL make clear that the quantity does not affect the inventory, SHALL NOT offer a material already in the Referencia as a new line, and SHALL keep the entered data when the backend rejects the request. WHEN loading an origin fails, the system SHALL show an error with retry and SHALL NOT present an empty origin or a stock of 0 as valid. WHEN the backend answers 409 `REFERENCIA_DUPLICADA`, the system SHALL refresh the listing and keep the entered data.

#### Scenario: Dependent selection and confirm
- **WHEN** the operator picks an origin, a material and a quantity, adds another line and confirms
- **THEN** the Material selector lists only the materials of the chosen origin, one request carries both lines and the table shows them after success

#### Scenario: Rejection keeps the form
- **WHEN** the backend rejects the batch
- **THEN** the message is shown, the entered lines remain and the table is unchanged

### Requirement: REQ-REF-014 Modificar y eliminar desde la tabla
WHILE the operator is in Configuración, the system SHALL offer «Modificar» and «Eliminar» on every row of the table; «Modificar» SHALL edit only the Cantidad Semanal with the same validation as the backend, and «Eliminar» SHALL require explicit confirmation. The system SHALL show the outcome of each action and SHALL keep the table consistent with the backend; WHEN the backend answers 404 `REFERENCIA_NO_ENCONTRADA` to a modification or deletion, the system SHALL refresh the table and report that the line no longer exists.

#### Scenario: Modify and delete
- **WHEN** the operator modifies a quantity and then deletes another row after confirming
- **THEN** the table shows the new quantity, the deleted row disappears and each action shows a success or error message

### Requirement: REQ-REF-015 Contrato y errores canónicos
The system SHALL expose `GET` and `POST /api/v1/equipos/{equipo_id}/referencia` and `PATCH` and `DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id}` with the codes 200/201/204/400/403/404/409/422 as frozen in the package OpenAPI contract; validation errors SHALL use the standard body `{"detail":[…]}` (a 422 therefore has two forms: validation, and business rule with `{"error":{"code","message","coordinates"}}`), positive path identifiers beyond INT4 SHALL respond the canonical 400 `NUMERIC_OUT_OF_RANGE` (a `material_id` in the body beyond INT4 is a validation 422), business-rule errors SHALL use the body `{"error":{"code","message","coordinates"}}` and the 403 SHALL keep the current authorization body. No business-rule error SHALL produce HTTP 500 (including a controlled response to a concurrent-insert deadlock) or expose SQL details. Error messages SHALL use «Unidad» (REQ-UNI-006). The fields SHALL be Spanish snake_case with no legacy aliases.

#### Scenario: Frozen contract
- **WHEN** the live OpenAPI document is compared with the frozen contract of the four Referencia operations and their schemas
- **THEN** paths, methods, status codes, field names, types and limits are identical

### Requirement: REQ-REF-016 Estados de interfaz y accesibilidad
The system SHALL present explicit loading, error (with retry) and empty states for the Referencia panel, SHALL label every control and field, SHALL keep keyboard operability and focus management in the form and the confirmations, and SHALL render without horizontal page overflow at viewport widths of 390 px and 1280 px. UI texts SHALL use «Unidad» (never «Equipo») and «Inventario FO».

#### Scenario: States and viewports
- **WHEN** the panel loads, fails, is empty or has lines, at 390 px and at 1280 px
- **THEN** each state is announced, controls are reachable by keyboard and the document has no horizontal overflow

### Requirement: REQ-REF-017 Frescura de la Referencia
WHEN a line is created, modified or deleted successfully, the system SHALL refresh the Referencia of that Unidad without a manual reload, and the mutation SHALL NOT trigger requests for the inventory, catalog, reports, activities or audit views.

#### Scenario: Refresh scope
- **WHEN** a mutation succeeds
- **THEN** the Referencia of that Unidad is refreshed and no inventory, catalog, reports, activities or audit request is triggered by the mutation

### Requirement: REQ-REF-018 Regresión y reversibilidad
The system SHALL provide a reversible database migration that creates and removes the Referencia objects without altering any pre-existing object (the reversal removes the stored Referencia configuration; audit events already written are preserved), and SHALL keep the existing backend and frontend behavior of the previous stages intact (inventory, Entrega, Consumo, Actividades and reports).

#### Scenario: Migration round trip
- **WHEN** the migration is applied, reverted and applied again
- **THEN** the table, constraints and audit mechanism are created and removed cleanly, audit events already written are preserved and no pre-existing table is modified

## 6. Casos límite

- Material repetido dentro de la petición, o ya presente en la Referencia: 422 / 409 sin escritura parcial.
- Material desactivado en el catálogo tras formar parte de una Referencia: se oculta, reaparece al reactivarse (REQ-REF-005) y mientras está oculto PATCH/DELETE responden 404 `REFERENCIA_NO_ENCONTRADA` (la línea se conserva).
- Un material que deja de figurar en su origen (General o FO) conserva su línea: el origen no se persiste.
- Dos altas concurrentes con los mismos materiales en distinto orden: se insertan en orden ascendente de `material_id`; un interbloqueo residual responde de forma controlada, nunca 500.
- Reintento de DELETE ya ejecutado: 404 `REFERENCIA_NO_ENCONTRADA`; la interfaz lo trata como «ya eliminada» y refresca.
- Dos peticiones simultáneas con el mismo material: la restricción de unicidad garantiza una sola línea; la segunda responde 409.
- Cantidad con más de 3 decimales o cero: 422.
- Unidad dada de baja (inactiva): lectura y escritura responden 404.
- Reintento tras éxito del alta: 409 `REFERENCIA_DUPLICADA` sin duplicar (no hay efectos adicionales).
- Origen con miles de materiales: selector con búsqueda; el backend no exige el origen.

## 7. Matriz de verificación (Constitución §7.1)

| REQ | Método de verificación |
| --- | --- |
| 001, 002, 003, 004, 013, 014, 016, 017 | vitest (panel, botón, tabla, estados, selector dependiente, modificar/eliminar, invalidación) + verificación visual Playwright Chromium (T9: árbol semántico, 390 px y 1280 px, consola) |
| 005, 006, 007, 008, 009, 010 | pytest API + BD (listado ordenado, alta todo-o-nada, validaciones, modificar, eliminar, aislamiento 404/403/422, Unidad inactiva) |
| 011 | pytest: snapshot de tablas de negocio antes/después y ausencia de eventos por lectura |
| 012 | `sql_tests` y pytest: trigger de auditoría (eventos, valores previos, rollback) |
| 015 | pytest contra el OpenAPI vivo y comparación con el contrato congelado (T7) |
| 018 | pytest de migración 0030 (upgrade/downgrade/upgrade), suites completas, build, `openspec validate --specs --strict` |

## 8. Clarificaciones de la Fase 4 (T1, `@arq-reviewer`) — decididas

Dictamen de `@arq-reviewer`: **PASS CON CORRECCIONES**, sin hallazgos bloqueantes. Decisiones del humano en T1: Q1 = A, Q2 = U.M. local efectiva, Q3 = por línea, Q4 = solo cantidad, Q5 = una opción por sección, Q6 = como Configuración, Q7 = BD desechable.

- **C-1 (ACEPTADA CON AJUSTE):** se persiste `material_id` (FK `RESTRICT`). `u_m` mostrada = U.M. **efectiva de la Unidad** (U.M. local de `equipo_material_config` o, si no hay, la del catálogo), decisión Q2; el glosario y REQ-REF-005 lo reflejan.
- **C-2 (ACEPTADA):** el backend NO verifica el origen; solo exige material activo del catálogo. El origen no se persiste (RN-4 es restricción de la interfaz).
- **C-3 (ACEPTADA CON AJUSTE):** borrado físico de la línea con evento de auditoría que conserva los valores previos. El ledger sigue append-only; RN-7 declara que `cantidad_semanal` no es un saldo.
- **C-4 (ACEPTADA CON AJUSTE):** material inactivo: línea oculta y conservada; PATCH/DELETE sobre línea oculta responden 404 `REFERENCIA_NO_ENCONTRADA`; la reactivación se prueba por SQL (no hay endpoint).
- **C-5 (ACEPTADA CON AJUSTE):** orden por `descripcion` según la collation de la BD y luego `material_id`; las pruebas derivan el orden esperado con SQL.
- **C-6 (ACEPTADA CON AJUSTE):** el botón se alinea a la derecha inmediatamente encima del área de inventario, **bajo las pestañas** (como en las capturas), y se muestra en todas las vistas de Consulta y en Configuración.
- **C-7 (ACEPTADA):** etiqueta «Inventario FO».
- **C-8 (ACEPTADA CON AJUSTE):** alta por lote de 1 a 50 líneas (límite defensivo del paquete), todo o nada, con precedencia de errores y `coordinates` por línea; inserción en orden ascendente de `material_id`; el 201 devuelve las líneas creadas ordenadas como el listado.
- **C-9 (RECHAZADA-CORREGIDA, Q1 = A):** la premisa «como las actividades» era falsa; lectura **y** escritura exigen Unidad activa (404 en ambas).
- **C-10 (ACEPTADA CON AJUSTE, Q5):** el stock entre paréntesis es ayuda visual de solo lectura, sin sumas en el cliente; un material en varias secciones GENERAL aparece una vez por sección; un error al cargar el origen no se presenta como origen vacío ni stock 0.
- **C-11 (ACEPTADA, Q4):** «Modificar» edita solo la Cantidad Semanal; con la misma cantidad es un no-op auditable (200 sin escritura).
- **C-12 (ACORDADA, D-3 + Q6):** administrador e integrantes de la Unidad; las escrituras aplican además la regla de autenticación de Configuración (administrador o con alguna sección asignada); las lecturas solo exigen pertenencia.
- **C-13 (ACEPTADA CON AJUSTE):** `cantidad_semanal` `NUMERIC(12,3)`, `> 0`, máximo 12 dígitos en total (999 999 999.999).

**Declaraciones de alcance (T1):** (a) los eventos `REFERENCIA_LINEA_*` se muestran en Auditoría con su código crudo; etiquetarlos queda fuera de este paquete. (b) `downgrade()` elimina la configuración almacenada; los eventos de auditoría se conservan. (c) El modelo `X-Actor` vigente (sin autenticación real) es una desviación heredada de §3.1/§3.3 que este paquete no agrava. (d) Un POST reintentado tras éxito responde 409 `REFERENCIA_DUPLICADA` sin duplicar efectos ni eventos (aceptable bajo §4.2).
