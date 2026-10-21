# Especificación — ETAPA 3/3: REFERENCIA DE MATERIALES POR UNIDAD

**Paquete:** `2026-10-referencia-materiales-unidades` · **Fase SDD:** 3 (Especificación) · **Estado:** redactada, pendiente de aprobación del humano; Fase 4 (T1) abierta, ver §8.
**Fuente de requisitos:** `docs/2 Unities Functions.docx`, sección «Referencia», y las decisiones D-1..D-4 de `proposal.md`. Gobernanza: `docs/constitution.md` (L1), `.agents.md` (L2). Separación Constitución §1.2: este documento define el *qué*; el *cómo* está en `plan.md`.

## 1. Propósito

Dar a cada Unidad una **Referencia de materiales**: una lista visual, sin efecto contable, con la Descripción, la U.M. y la Cantidad Semanal de los materiales que la Unidad maneja. Se consulta desde Inventario por Unidad y se configura (añadir, modificar, eliminar) con materiales ya existentes, sin reescribirlos a mano.

## 2. Alcance

**Dentro:** tabla propia por Unidad, API de lectura y escritura, botón «Referencia», panel «Materiales Referencia», alta con selección dependiente (origen → material), modificar y eliminar, auditoría de las mutaciones.
**Fuera:** unidades de medida nuevas, equivalencias y conversiones; cualquier efecto sobre inventarios, catálogo, movimientos, seguimientos, actividades, actas o reportes; validación de la cantidad semanal contra el stock; exportación; autenticación real.

## 3. Glosario y nomenclatura

- **Unidad:** texto oficial de UI. En código, rutas y parámetros el identificador técnico permanece `equipo`/`equipo_id` (REQ-UNI-005; protegido por `backend/tests/test_unidad_nomenclatura.py`).
- **Referencia:** lista visual de materiales de una Unidad. **Línea de Referencia:** un material con su cantidad semanal dentro de la Referencia de una Unidad.
- **Cantidad Semanal:** cantidad visual de manejo semanal de un material; no es stock y no se valida contra él.
- **Inventario General / Inventario FO:** orígenes ofrecidos por la interfaz para elegir el material (etiqueta oficial «Inventario FO», `.agents.md` §3). Son ayuda de selección y no se persisten.
- **Etiquetas de interfaz:** «Referencia», «Materiales Referencia», «Descripción», «U.M.», «Cantidad Semanal», «+ Agregar», «+ Agregar línea», «Modificar», «Eliminar».

## 4. Reglas de negocio (extraídas del documento fuente)

- **RN-1** La Referencia es independiente para cada Unidad.
- **RN-2** La Referencia es solo un aspecto visual: no afecta inventarios, base de datos de inventarios ni materiales existentes.
- **RN-3** El botón «Referencia» aparece tanto en la subsección Consulta (solo despliega la tabla) como en Configuración (añadir, modificar y eliminar).
- **RN-4** Los materiales se eligen de los inventarios existentes (General o FO) con su nomenclatura oficial, sin escribirlos a mano.
- **RN-5** La cantidad capturada no afecta el inventario.
- **RN-6** Cualquier material de la tabla puede modificarse o eliminarse.

## 5. Requisitos

Cada requisito tiene identificador inmutable `REQ-REF-NNN` (Constitución §1.5).

### Requirement: REQ-REF-001 Botón «Referencia» en Inventario por Unidad
The system SHALL show in Inventario por Unidad, for the selected Unidad, a button named «Referencia» at the right end of the subsection bar, visible in both Consulta and Configuración, that shows and hides the «Materiales Referencia» panel. The system SHALL NOT show the button in CONSUMO or ACTIVIDADES, and SHALL expose the open/closed state to assistive technology.

#### Scenario: Button in Consulta and Configuración
- **WHEN** the operator opens Inventario por Unidad with a Unidad selected
- **THEN** the button «Referencia» is present in Consulta and in Configuración, absent in CONSUMO and ACTIVIDADES, and pressing it toggles the panel with `aria-expanded` updated

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
- **THEN** no add, modify or delete control is rendered and no request other than the listing is issued

### Requirement: REQ-REF-004 Independencia por Unidad
The system SHALL keep one Referencia per Unidad: the lines of a Unidad SHALL NOT appear in another Unidad's Referencia, and WHEN the selected Unidad changes the panel SHALL show the lines of the new Unidad.

#### Scenario: Switching Unidad
- **WHEN** two Unidades hold different lines and the operator switches the selected Unidad
- **THEN** the panel shows only the lines of the newly selected Unidad

### Requirement: REQ-REF-005 Consulta de la Referencia
WHEN the client requests `GET /api/v1/equipos/{equipo_id}/referencia`, the system SHALL return the lines of that Unidad as `{items, total}`, each item carrying `material_id`, `codigo`, `descripcion`, `u_m` and `cantidad_semanal`, ordered by `descripcion` ascending and then `material_id` ascending. Descripción, código and U.M. SHALL be read from the catalog at query time, and lines whose catalog material is inactive SHALL NOT be listed but SHALL be preserved.

#### Scenario: Ordered listing with live catalog data
- **WHEN** the Unidad holds several lines and the catalog description of one material changes
- **THEN** the next response is ordered by descripción and shows the updated description, with `total` equal to the number of listed items

#### Scenario: Inactive material omitted, line preserved
- **WHEN** a catalog material of a line is deactivated and later reactivated
- **THEN** the line is absent from the listing while inactive and reappears, unchanged, after reactivation

### Requirement: REQ-REF-006 Alta de líneas
WHEN the client submits `POST /api/v1/equipos/{equipo_id}/referencia` with `{"lineas":[{"material_id","cantidad_semanal"}]}` carrying 1 to 50 lines, the system SHALL validate the whole payload and, only if every line is valid, create all the lines in one transaction and respond 201 with the created lines. The system SHALL reject the whole payload, creating nothing, if any line is invalid; the error SHALL identify the offending line. The origin chosen in the interface (Inventario General or Inventario FO) SHALL NOT be part of the contract.

#### Scenario: Valid batch
- **WHEN** a payload with three valid lines for an active Unidad is submitted by an authorized actor
- **THEN** the response is 201, the three lines exist in the Unidad's Referencia and exactly one audit event per line is written

#### Scenario: All or nothing
- **WHEN** a payload carries two valid lines and one invalid line (unknown material, zero quantity or repeated material)
- **THEN** the response is 404, 422 or 409 as applicable, no line is created and no audit event is written

### Requirement: REQ-REF-007 Validación de la línea
IF a line carries `cantidad_semanal` that is not greater than zero or has more than 3 decimals or more than 12 digits, THEN the system SHALL respond HTTP 422. IF the payload carries fields not declared by the contract, no lines, more than 50 lines or the same `material_id` twice, THEN the system SHALL respond HTTP 422 (`REFERENCIA_LINEA_DUPLICADA` for the repeated material). IF a `material_id` does not exist in the catalog or its material is inactive, THEN the system SHALL respond HTTP 404 `MATERIAL_NO_ENCONTRADO`. IF the material is already in the Unidad's Referencia, THEN the system SHALL respond HTTP 409 `REFERENCIA_DUPLICADA` and SHALL NOT modify the existing line.

#### Scenario: Rejected inputs create nothing
- **WHEN** a request carries a quantity of 0, a quantity of 1.2345, an extra field, 51 lines or a repeated material
- **THEN** the response is 422 and no row is written

#### Scenario: Unknown, inactive or already referenced material
- **WHEN** a request names a non-existent or inactive material, or a material already in the Referencia
- **THEN** the response is 404 `MATERIAL_NO_ENCONTRADO` or 409 `REFERENCIA_DUPLICADA` respectively and the existing lines are unchanged

### Requirement: REQ-REF-008 Modificación de una línea
WHEN the client submits `PATCH /api/v1/equipos/{equipo_id}/referencia/{material_id}` with `{"cantidad_semanal"}`, the system SHALL update only the quantity of that line, refresh its modification timestamp and respond 200 with the line. The system SHALL NOT allow changing the material of a line. IF the line does not exist, THEN the system SHALL respond HTTP 404 `REFERENCIA_NO_ENCONTRADA`.

#### Scenario: Quantity updated
- **WHEN** an authorized actor sends a valid new quantity for an existing line
- **THEN** the response is 200 with the new quantity, the other lines are unchanged and one audit event with the previous and new quantity is written

#### Scenario: Missing line
- **WHEN** the line does not exist for the Unidad
- **THEN** the response is 404 `REFERENCIA_NO_ENCONTRADA` and nothing is written

### Requirement: REQ-REF-009 Eliminación de una línea
WHEN the client submits `DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id}`, the system SHALL remove that line of the Referencia, respond 204 and keep the previous values in the audit event. IF the line does not exist, THEN the system SHALL respond HTTP 404 `REFERENCIA_NO_ENCONTRADA`. The interface SHALL ask for confirmation before deleting.

#### Scenario: Line removed with audit
- **WHEN** an authorized actor deletes an existing line
- **THEN** the response is 204, the line no longer exists, the material remains in the catalog and in every inventory, and an audit event keeps the removed quantity

### Requirement: REQ-REF-010 Aislamiento y autorización por Unidad
The system SHALL authorize every Referencia endpoint by Unidad: the administrator SHALL access every Unidad; any other actor SHALL access only the Unidades it belongs to. IF the Unidad does not exist, THEN the system SHALL respond 404 before evaluating membership; IF the actor is not a member, THEN 403 with the current authorization body; IF `X-Actor` is missing or invalid, THEN 422 without querying business data. Writes SHALL additionally require the Unidad to be active (404 otherwise); reads SHALL remain available for decommissioned Unidades.

#### Scenario: Foreign Unidad
- **WHEN** a non-administrator actor requests or modifies the Referencia of a Unidad it does not belong to
- **THEN** the response is 403 and no row is read or written

#### Scenario: Inactive Unidad
- **WHEN** a member lists, then tries to add a line to, a decommissioned Unidad
- **THEN** the listing is 200 and the write is 404 without side effects

### Requirement: REQ-REF-011 Sin efecto sobre inventarios ni catálogo
The system SHALL NOT modify, by creating, updating or deleting Referencia lines, any of `inventario_equipos`, `inventario_almacen`, `inventario_fibra`, `catalogo_materiales`, `equipo_material_config`, `movimientos_cabecera`, `movimientos_detalle`, `seguimientos`, `seguimiento_items`, `actividades_reportes` or `actas_reportes`, nor SHALL it invoke the Stored Functions that mutate stock. Reading the Referencia SHALL NOT write any row or emit any audit event.

#### Scenario: Business tables intact
- **WHEN** lines are created, modified and deleted, and the Referencia is listed
- **THEN** the snapshot of every table listed above is identical before and after, and listing emits no audit event

### Requirement: REQ-REF-012 Auditoría de las mutaciones
WHEN a line is created, modified or deleted, the system SHALL write, in the same transaction and through a database trigger, one immutable audit event (`REFERENCIA_LINEA_CREADA`, `REFERENCIA_LINEA_MODIFICADA` or `REFERENCIA_LINEA_ELIMINADA`) with the actor, the `material_id`, the `equipo_id` and the previous and new values (`modulo`, `accion`, `valores_anteriores`, `valores_nuevos`). IF the transaction is rolled back, THEN the system SHALL leave neither the line nor the event.

#### Scenario: One event per mutation
- **WHEN** a line is created, its quantity modified and then deleted
- **THEN** exactly three events exist, in that order, with the corresponding previous and new values, and a rejected request leaves no event

### Requirement: REQ-REF-013 Alta con selección dependiente en Configuración
WHILE the operator is in Configuración with the panel open, the system SHALL offer a «+ Agregar» button that shows a form with an origin selector («Inventario General», «Inventario FO»), a dependent Material selector listing the materials of the chosen origin with their current stock between parentheses as a visual aid, a «Cantidad» field, a delete control per line and a «+ Agregar línea» button; confirming SHALL send all the lines in one request. The system SHALL make clear that the quantity does not affect the inventory, SHALL NOT offer a material already in the Referencia as a new line, and SHALL keep the entered data when the backend rejects the request.

#### Scenario: Dependent selection and confirm
- **WHEN** the operator picks an origin, a material and a quantity, adds another line and confirms
- **THEN** the Material selector lists only the materials of the chosen origin, one request carries both lines and the table shows them after success

#### Scenario: Rejection keeps the form
- **WHEN** the backend rejects the batch
- **THEN** the message is shown, the entered lines remain and the table is unchanged

### Requirement: REQ-REF-014 Modificar y eliminar desde la tabla
WHILE the operator is in Configuración, the system SHALL offer «Modificar» and «Eliminar» on every row of the table; «Modificar» SHALL edit only the Cantidad Semanal with the same validation as the backend, and «Eliminar» SHALL require explicit confirmation. The system SHALL show the outcome of each action and SHALL keep the table consistent with the backend.

#### Scenario: Modify and delete
- **WHEN** the operator modifies a quantity and then deletes another row after confirming
- **THEN** the table shows the new quantity, the deleted row disappears and each action shows a success or error message

### Requirement: REQ-REF-015 Contrato y errores canónicos
The system SHALL expose `GET` and `POST /api/v1/equipos/{equipo_id}/referencia` and `PATCH` and `DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id}` with the codes 200/201/204/400/403/404/409/422 as frozen in the package OpenAPI contract; validation errors SHALL use the standard body `{"detail":[…]}`, positive identifiers beyond INT4 SHALL respond the canonical 400 `NUMERIC_OUT_OF_RANGE`, and business-rule errors SHALL use the body `{"error":{"code","message","coordinates"}}`. No business-rule error SHALL produce HTTP 500 or expose SQL details. The fields SHALL be Spanish snake_case with no legacy aliases.

#### Scenario: Frozen contract
- **WHEN** the live OpenAPI document is compared with the frozen contract of the four Referencia operations and their schemas
- **THEN** paths, methods, status codes, field names, types and limits are identical

### Requirement: REQ-REF-016 Estados de interfaz y accesibilidad
The system SHALL present explicit loading, error (with retry) and empty states for the Referencia panel, SHALL label every control and field, SHALL keep keyboard operability and focus management in the form and the confirmations, and SHALL render without horizontal page overflow at viewport widths of 390 px and 1280 px. UI texts SHALL use «Unidad» (never «Equipo») and «Inventario FO».

#### Scenario: States and viewports
- **WHEN** the panel loads, fails, is empty or has lines, at 390 px and at 1280 px
- **THEN** each state is announced, controls are reachable by keyboard and the document has no horizontal overflow

### Requirement: REQ-REF-017 Frescura de la Referencia
WHEN a line is created, modified or deleted successfully, the system SHALL refresh the Referencia of that Unidad without a manual reload and SHALL NOT invalidate or refetch the inventory, catalog, reports or activities queries.

#### Scenario: Refresh scope
- **WHEN** a mutation succeeds
- **THEN** only the Referencia query of that Unidad is invalidated and the inventory, catalog and reports queries are not refetched

### Requirement: REQ-REF-018 Regresión y reversibilidad
The system SHALL provide Alembic migration 0030 with a `downgrade()` that removes the Referencia table, trigger and function without touching pre-existing objects, and SHALL keep the full backend and frontend suites green (including the Etapa 1 and Etapa 2 endpoints and reports), the build without warnings, the visual verification of T9 evidence and `openspec validate --specs --strict` passing.

#### Scenario: Migration round trip
- **WHEN** migration 0030 is upgraded, downgraded and upgraded again
- **THEN** the table, constraints, trigger and function are created and removed cleanly, audit events already written are preserved and no pre-existing table is modified

## 6. Casos límite

- Material repetido dentro de la petición, o ya presente en la Referencia: 422 / 409 sin escritura parcial.
- Material desactivado en el catálogo tras formar parte de una Referencia: se oculta y reaparece al reactivarse (REQ-REF-005).
- Dos peticiones simultáneas con el mismo material: la restricción de unicidad garantiza una sola línea; la segunda responde 409.
- Cantidad con más de 3 decimales o cero: 422.
- Unidad dada de baja: lectura permitida, escritura 404.
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

## 8. Clarificaciones para la Fase 4 (T1, `@arq-reviewer`)

Propuestas que el humano ratifica o corrige; ninguna se inventa fuera del documento.

- **C-1:** persistir `material_id` (no texto copiado) para mostrar Descripción y U.M. vigentes (D-5).
- **C-2:** el origen General/FO es solo ayuda de selección; el backend solo valida material activo del catálogo (D-7). ¿Debe el backend verificar además que el material pertenezca a Inventario General o FO?
- **C-3:** «Eliminar» es borrado físico con evento de auditoría que conserva los valores previos (D-9).
- **C-4:** materiales inactivos del catálogo: se ocultan y la línea se conserva (D-10).
- **C-5:** orden del listado por Descripción ascendente (D-11); el documento no lo fija.
- **C-6:** ubicación del botón en el extremo derecho de la barra de subsecciones (D-12); las capturas lo muestran sobre la tabla, a la derecha.
- **C-7:** etiqueta «Inventario FO» en lugar de «Inventario Fibra Óptica» (D-13).
- **C-8:** alta por lote de 1 a 50 líneas, todo o nada (Constitución §5.3).
- **C-9:** lectura permitida con Unidad inactiva; escritura exige Unidad activa (D-14).
- **C-10:** el stock entre paréntesis del selector es una ayuda visual de solo lectura obtenida de los endpoints existentes; la Referencia no valida la cantidad semanal contra él (RN-5).
- **C-11:** «Modificar» edita solo la Cantidad Semanal (D-8).
- **C-12:** permisos de edición: administrador e integrantes de la Unidad (D-3), aunque el documento diga que la Referencia la «necesita el administrador».
- **C-13:** `cantidad_semanal` con la misma precisión que el resto de cantidades del sistema (`NUMERIC(12,3)`, `> 0`).
