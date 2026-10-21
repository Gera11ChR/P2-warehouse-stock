# 003_inventory_dashboard Specification

## Purpose

Provides the operator-facing warehouse management surface: Spanish-language navigation, KPI dashboard, filter toolbar, per-(SKU+Almacén) inventory browsing, material detail drawer, bulk search, the unified fiber-optic inventory (Inventario FO), the Valor Unitario / Valor Total valuation, team inventory assignment, the per-Unidad ACTIVIDADES registration (immutable activity records with automatic folio and date), and the material/inventory/team/fiber/KPI API contracts.

## Requirements

### Requirement: REQ-DASH-001 Three-column layout
The system SHALL render the dashboard as a three-column layout composed of a left navigation sidebar, a center inventory workspace, and a right material detail drawer that opens on demand.

#### Scenario: Layout regions present
- **WHEN** the dashboard loads
- **THEN** a dark sidebar occupies the left, a light inventory workspace occupies the center, and a white material detail drawer occupies the right when a material is selected

### Requirement: REQ-DASH-002 Spanish domain language enforcement
The system SHALL present all user-facing labels, database entities, schemas, DTOs, API responses, table headers, forms, and React components using Spanish terminology, and SHALL NOT display mixed English/Spanish terminology.

#### Scenario: No mixed language
- **WHEN** any inventory view, form, header, or API response is rendered
- **THEN** every visible label uses Spanish terms (e.g., "Almacén", "Stock Actual", "Stock Mínimo", "Alerta Stock", "Transferencia", "Inventario por Unidad") with no English equivalents

### Requirement: REQ-DASH-003 Navigation hierarchy
The system SHALL provide a sidebar navigation with the following structure: "Sección General", "Inventario FO" (a single entry without sub-entries), "Inventario por Unidad", "Transferencias", "Reportes", and "Auditoría".

#### Scenario: All navigation entries present
- **WHEN** the sidebar is rendered
- **THEN** each listed entry is present in the given hierarchy, "Inventario FO" has no sub-entries, and selecting one navigates to its module

### Requirement: REQ-DASH-004 KPI dashboard cards
The system SHALL render five KPI cards in the order "Total Materiales" (blue), "Valor Total" (teal), "Stock Total" (green), "Alertas Stock" (amber), and "Transferencias Hoy" (purple), positioned above all inventory tables.

#### Scenario: Five KPI cards render above tables
- **WHEN** the Sección General module is displayed
- **THEN** the five KPI cards appear above the inventory table in the stated order with their respective colors and current values

### Requirement: REQ-DASH-005 Filter toolbar and actions
The system SHALL render a filter toolbar immediately below the KPI cards with controls "Buscar", "Categoría", "U.M.", and "Almacén", and action buttons "+ Agregar" (green), "Modificar" (yellow), "Eliminar" (red), and "Transferir Stock" (blue).

#### Scenario: Filter toolbar renders
- **WHEN** the Sección General module is displayed
- **THEN** the filter toolbar appears below the KPI cards with the four filter controls and the four action buttons in their specified colors

### Requirement: REQ-DASH-006 Sección General inventory table
The system SHALL render the main inventory table with columns CÓDIGO (SKU), DESCRIPCIÓN, U.M., STOCK ACTUAL, VALOR UNITARIO, STOCK MÍNIMO, ALERTA STOCK, and ALMACÉN, and SHALL emit one row per (SKU + Almacén) combination.

#### Scenario: One row per SKU and warehouse
- **WHEN** a material holds stock in more than one warehouse
- **THEN** the table renders one row for each warehouse where that material has on-hand quantity, each carrying the exact ALMACÉN

#### Scenario: Table columns present in order
- **WHEN** the Sección General table is rendered
- **THEN** columns appear in the order CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, VALOR UNITARIO, STOCK MÍNIMO, ALERTA STOCK, ALMACÉN

### Requirement: REQ-DASH-007 Stock level color coding
The system SHALL color stock levels such that normal stock renders green, low stock renders amber, and critical stock renders red.

#### Scenario: Critical stock is red
- **WHEN** an SKU's stock falls into the critical band
- **THEN** its stock indicator renders red; normal renders green and low renders amber

### Requirement: REQ-DASH-008 Mandatory field ordering
The system SHALL render the Material Detail Drawer, CRUD forms, view modals, transfer dialogs, and edit screens with fields in the exact order: DESCRIPCIÓN, STOCK ACTUAL, VALOR UNITARIO (where the surface shows it), STOCK MÍNIMO, ALERTA STOCK, U.M., CÓDIGO (SKU), overriding any default UI framework or component-library ordering.

#### Scenario: Fields ordered correctly in every surface
- **WHEN** any detail drawer, CRUD form, view modal, transfer dialog, or edit screen is rendered
- **THEN** its fields appear in the order DESCRIPCIÓN, STOCK ACTUAL, VALOR UNITARIO (where shown), STOCK MÍNIMO, ALERTA STOCK, U.M., CÓDIGO (SKU)

### Requirement: REQ-DASH-009 Material detail drawer
The system SHALL provide a material detail drawer with a close button, fields in the mandatory order, and footer actions "Modificar", "Eliminar", and "Transferir Stock".

#### Scenario: Drawer opens on row selection
- **WHEN** a row in the Sección General table is selected
- **THEN** the material detail drawer opens showing the material's fields in the mandatory order and the three footer actions

### Requirement: REQ-DASH-010 Bottom tabbed section
The system SHALL render a bottom tabbed section with two tabs: "1 Buscador" providing standard inventory browsing and pagination, and "2 Buscador a granel" providing "Desde SKU" and "Hasta SKU" inputs that drive a range-search results table.

#### Scenario: Bulk range search
- **WHEN** the user selects the "2 Buscador a granel" tab and enters "Desde SKU" and "Hasta SKU" values
- **THEN** the system returns a results table containing materials whose SKU falls within the inclusive range

### Requirement: REQ-DASH-011 Success feedback toasts
The system SHALL display green toast notifications in the bottom-right corner for a completed transfer, a created material, a modified material, and a deleted material.

#### Scenario: Toast on material creation
- **WHEN** a material is created, modified, or deleted, or a transfer completes
- **THEN** a green toast appears in the bottom-right corner confirming the action

### Requirement: REQ-DASH-012 Top header with search
The system SHALL render a top header with breadcrumbs (e.g., "Dashboard / Sección General") and a global search input with placeholder "Buscar materiales, SKU o descripción..." and a "Ctrl + K" shortcut badge.

#### Scenario: Header renders breadcrumbs and search
- **WHEN** the dashboard is displayed
- **THEN** the header shows breadcrumbs and the global search input with the specified placeholder and shortcut badge

### Requirement: REQ-FO-003 Official Inventario FO nomenclature
The system SHALL name the single fiber-optic location "Inventario FO" in the side navigation, page title, TRANSF/Mover/+Cantidad selectors, reports, audit and messages, SHALL present a single fiber-optic navigation entry without sub-entries, and IF a visible text contains "Paquete", "En Uso", "FO Paquete" or "FO En Uso" as an inventory name THEN a sweep test SHALL fail (comments and the unit of measure `PAQUETE (100 PZ)` exempt).

#### Scenario: Nomenclature sweep
- **WHEN** the sweep test runs over the visible texts
- **THEN** there are no matches outside the declared exceptions

### Requirement: REQ-VALOR-002 Initial value, display and edition
The system SHALL assign `1.000` MXN as the initial Valor Unitario to the whole existing catalog and to every new material that declares no other value; SHALL display the VALOR UNITARIO column in the tables of the Inventario General, the Inventario FO and the Inventario por Unidad with the figure on the left and the label `MXN` on its right (e.g. `1.00 MXN`; up to 3 decimals, minimum 2); WHEN an administrator opens the modify option of a material (Inventario General or Inventario FO) the system SHALL present the Valor Unitario field preloaded with the current value and allow saving it with decimals; and WHERE the modify option runs in the Inventario por Unidad the system SHALL show the Valor Unitario in read-only mode (the value belongs to the catalog).

#### Scenario: Default value
- **WHEN** the migration is applied over an existing catalog
- **THEN** all materials have Valor Unitario `1.000`

#### Scenario: Edition with decimals
- **WHEN** the administrator saves `2.5` in Modificar Material
- **THEN** the three tables show `2.50 MXN` for that material after refreshing

### Requirement: REQ-VALOR-004 Valor Total indicator position
The system SHALL show the Valor Total indicator immediately after Total Materiales and before Stock Total, with the figure returned by the API (never recalculated in the client) and the label `MXN` on its right; WHEN a mutation (adjustment, Valor Unitario edit, movement, etc.) completes successfully the indicator SHALL refresh with the persisted value; and WHILE the query is loading or has failed the indicator SHALL show an explicit loading or error state and never an invented value.

#### Scenario: Card order
- **WHEN** the general section is rendered
- **THEN** the cards appear in the order Total Materiales, Valor Total, Stock Total, Alertas Stock, Transferencias Hoy and Valor Total is the second one

#### Scenario: Refresh after editing the value
- **WHEN** the administrator changes a Valor Unitario successfully
- **THEN** the indicator shows the new Valor Total coming from the API

### Requirement: REQ-TEAM-001 Team inventory records
The system SHALL persist team inventory records with columns Equipo, Usuario, Código SKU, Descripción, Cantidad, Valor Unitario (read-only, belonging to the catalog), and Última Modificación.

#### Scenario: Team inventory record persisted
- **WHEN** a team inventory record is created or updated
- **THEN** its Equipo, Usuario, Código SKU, Descripción, Cantidad, and Última Modificación are stored and returned, together with the catalog Valor Unitario

### Requirement: REQ-TEAM-002 SKU auto-fill description
The system SHALL automatically fill the Descripción field when a Código SKU is entered in the team inventory module.

#### Scenario: Description auto-filled from SKU
- **WHEN** the user types a known Código SKU
- **THEN** the Descripción field is automatically populated with that SKU's description

### Requirement: REQ-TEAM-003 Automatic modification timestamp
The system SHALL automatically update the Última Modificación timestamp whenever a team inventory record is modified.

#### Scenario: Timestamp updates on modification
- **WHEN** a team inventory record is modified
- **THEN** its Última Modificación timestamp is automatically updated to the modification time

### Requirement: REQ-MAT-001 Material CRUD
The system SHALL provide create, read, update, and delete operations for materials, with created, modified, and deleted materials persisted atomically; the delete operation SHALL be a logical soft-delete that marks the material inactive (`is_active = false`) and preserves referential integrity.

#### Scenario: Material created, updated, deleted
- **WHEN** the operator creates, modifies, or deletes a material
- **THEN** the operation persists the change and subsequent inventory queries reflect the new state

#### Scenario: Deleted material becomes inactive
- **WHEN** the operator deletes a material through the materials API
- **THEN** the material is marked inactive instead of being removed and is excluded from subsequent catalog and inventory queries

### Requirement: REQ-MAT-002 Per-SKU-per-warehouse inventory query
The system SHALL return inventory data as one row per (SKU + Almacén), with STOCK ACTUAL derived from the aggregate on-hand quantity for that warehouse and ALERTA STOCK derived by comparing that value to the SKU's STOCK MÍNIMO.

#### Scenario: Derived stock and alert flag returned
- **WHEN** inventory is queried
- **THEN** each row carries a derived STOCK ACTUAL and a derived ALERTA STOCK flag, computed from the warehouse on-hand quantity and the SKU minimum stock

### Requirement: REQ-MAT-003 Seed data set
The system SHALL provide an idempotent seed routine that loads the official catalog of exactly 53 materials — 5 fiber-optic `CF-*` SKUs (`tipo=FIBRA`) and 48 general SKUs (`tipo=GENERAL`) — into the `CENTRAL` warehouse with zero initial stock and zero minimum stock (as registered in the DMS template), deactivates any non-official legacy SKU, and never deletes physical rows that hold transaction history.

#### Scenario: Seed loads full data set
- **WHEN** the seed routine is executed against an empty database
- **THEN** exactly 53 active SKUs matching the official list are created in `CENTRAL` with zero on-hand quantities and no RECEIPT stock movements for zero-quantity balances

#### Scenario: Seed is idempotent
- **WHEN** the seed routine is executed twice consecutively
- **THEN** the catalog still contains exactly 53 active SKUs with no duplicate rows, no database errors, and unchanged history counts

### Requirement: REQ-MAT-004 Supported units vocabulary
The system SHALL support the units: PZ, LT, CARRETE (1 KM), METRO (M), CARRETE (5 KM), BOLSA (500 PZ), PAQUETE (100 PZ), ROLLO, EQUIPO, and UNIDAD.

#### Scenario: All supported units accepted
- **WHEN** a material is created with any of the supported units
- **THEN** the material is accepted and its unit stored without truncation or rejection

### Requirement: REQ-MAT-005 Edición manual de STOCK ACTUAL
The system SHALL allow an operator to edit the `STOCK ACTUAL` value directly in the "Modificar Material" modal, and SHALL persist it as `warehouse_inventory.on_hand_quantity` for the selected material's warehouse (defaulting to the `CENTRAL` warehouse when no warehouse is specified).

#### Scenario: Manual stock override updates on-hand quantity
- **WHEN** an operator opens "Modificar Material" and enters a non-negative decimal (up to 3 decimals) in the `STOCK ACTUAL` field
- **THEN** the update endpoint sets `warehouse_inventory.on_hand_quantity` for that SKU and warehouse to the entered value, and subsequent inventory queries reflect the new stock

#### Scenario: Negative or missing stock rejected
- **WHEN** the operator submits a negative `STOCK ACTUAL` value or the SKU holds no inventory row in the target warehouse
- **THEN** the request is rejected with HTTP 422 and no inventory change is committed

### Requirement: REQ-MAT-006 Auditoría inmutable del ajuste manual
WHEN a manual `STOCK ACTUAL` override is committed, THE SYSTEM SHALL record an immutable audit log entry and a stock movement documenting the adjustment, carrying the actor, SKU, warehouse, old quantity, and new quantity.

#### Scenario: Adjustment writes audit row and movement
- **WHEN** a manual stock override is committed
- **THEN** exactly one audit entry (action "Ajuste manual") and one stock movement row are appended with the actor, SKU, warehouse, old quantity, and new quantity, and the delta equals new minus old

### Requirement: REQ-DASH-013 Consulta de almacenes destino
The system SHALL provide an endpoint returning all active warehouses the authenticated actor has scope for, so the "Transferir Stock" dialog can render valid destination options regardless of whether those warehouses hold stock rows.

#### Scenario: Scoped active warehouses returned
- **WHEN** an authenticated operator requests the warehouse list
- **THEN** the response contains every active warehouse within the actor's scope, and no warehouse outside the actor's scope

#### Scenario: Unscoped actor receives empty list
- **WHEN** an actor with no warehouse scope requests the warehouse list
- **THEN** the response contains an empty warehouse list without an authorization error

### Requirement: REQ-DASH-014 Opciones de destino en transferencia
The system SHALL populate the "ALMACÉN DESTINO" select in the "Transferir Stock" modal with the active scoped warehouses excluding the origin warehouse, immediately when the modal opens.

#### Scenario: Destinations exclude origin and inactive warehouses
- **WHEN** the "Transferir Stock" modal opens for a material with stock in its origin warehouse
- **THEN** the destination select renders every active scoped warehouse other than the origin, and excludes inactive warehouses

### Requirement: REQ-CAT-001 Catálogo oficial de 53 SKUs y visibilidad solo-activos
The system SHALL maintain a material catalog restricted to the official 53-item list (5 fiber-optic `CF-*` SKUs with `tipo=FIBRA` and 48 general SKUs with `tipo=GENERAL`, using the normalized SKU structure `[PREFIJO]-[VARIANTE/MEDIDA]-[SUFIJO_OPCIONAL]`), and SHALL expose only active SKUs (`is_active = true`) through the material list, inventory grid, KPI aggregates, and fiber-optic surfaces.

#### Scenario: Exactly 53 active materials
- **WHEN** the catalog is seeded against the official list
- **THEN** exactly 53 active SKUs exist and the set of active SKU codes equals the official list with no extras and no missing items

#### Scenario: Inactive materials hidden from views
- **WHEN** an SKU is marked inactive
- **THEN** it is excluded from material listings, inventory rows, KPI totals, and fiber-optic listings without being physically deleted

### Requirement: REQ-CAT-002 Soft-delete y preservación de historial
WHEN a material that holds transactional history (stock movements, transfers, audit records) is retired from the official catalog, THE SYSTEM SHALL deactivate it logically (`is_active = false`) instead of deleting it physically, and SHALL leave every foreign-key reference and historical record intact and countable.

#### Scenario: Legacy material deactivated, not deleted
- **WHEN** the catalog is reconciled with the official list
- **THEN** every non-official SKU with history is marked inactive, all foreign keys remain valid, and the counts of stock transfers, transfer line items, audit logs, and stock movements do not decrease

#### Scenario: API delete performs soft-delete
- **WHEN** an operator deletes a material through the materials API
- **THEN** the material is marked inactive instead of removed, subsequent catalog queries exclude it, and its row remains queryable at the database level

### Requirement: REQ-CAT-003 Custodia CENTRAL con compatibilidad multi-almacén
The system SHALL consolidate custody of the official catalog inventory in the `CENTRAL` warehouse while preserving the multi-warehouse schema and all existing inter-site transfer capabilities for other warehouses (e.g., `NORTE`, `SUR`).

#### Scenario: Official catalog stock lives in CENTRAL
- **WHEN** the seed routine executes
- **THEN** every official SKU holds its on-hand inventory row in `CENTRAL` and the main inventory table renders one row per active material

#### Scenario: Multi-warehouse transfer schema preserved
- **WHEN** a transfer between any two existing warehouses is dispatched or received
- **THEN** the operation behaves exactly as before the catalog consolidation with no schema or endpoint changes

### Requirement: REQ-ACT-001 ACTIVIDADES subsection
The system SHALL offer in Inventario por Unidad a subsection named "ACTIVIDADES", placed after CONSUMO in the subsection bar.

#### Scenario: Tab order
- **WHEN** an operator opens Inventario por Unidad
- **THEN** the subsection bar lists Consulta, Configuración, CONSUMO and ACTIVIDADES in that order, and selecting ACTIVIDADES mounts the activity registration panel for the selected Unidad

### Requirement: REQ-ACT-002 Inherited consumed materials
WHEN an operator opens ACTIVIDADES for a Unidad that has a seguimiento pending an activity, the system SHALL display, read-only, the materials consumed in that seguimiento with CANTIDAD, MATERIAL, U.M. and VALOR UNITARIO (the current value of the material at query time, computed by PostgreSQL).

#### Scenario: Pending seguimiento shows consumed materials
- **WHEN** `GET /equipos/{equipo_id}/actividades/pendiente` is requested for a Unidad whose most recent CERRADA seguimiento has no activity
- **THEN** the response lists that seguimiento with one line per material having `cantidad_consumida` > 0 and the current `valor_unitario`, and no row is written

### Requirement: REQ-ACT-003 One-to-one link with the seguimiento
IF the Unidad has no seguimiento pending an activity, THEN the system SHALL disable "Confirmar", show a notice that a seguimiento must be closed in CONSUMO, and the backend SHALL reject the confirmation with HTTP 409. IF the submitted `seguimiento_id` does not exist or does not belong to the Unidad, THEN the system SHALL respond 404. IF the seguimiento is not CERRADA or already has a confirmed activity, THEN the system SHALL respond 409 without creating a record. The backend SHALL NOT require the seguimiento to be the most recent one; only the interface offers the most recent.

#### Scenario: Rejections create nothing
- **WHEN** an activity is submitted for an ABIERTA seguimiento, a non-existent seguimiento, or a seguimiento of another Unidad
- **THEN** the response is 409 (`SEGUIMIENTO_NO_CERRADO`), 404 (`SEGUIMIENTO_NO_ENCONTRADO`) or 404 respectively, and no row is written to `actividades_reportes` nor to the audit ledger

### Requirement: REQ-ACT-004 Seguimiento without consumption
WHILE a closed seguimiento has zero materials with `cantidad_consumida` > 0, the system SHALL allow confirming the activity with an empty materials list.

#### Scenario: Empty consumption is confirmable
- **WHEN** an activity is confirmed for a CERRADA seguimiento whose consumed quantities are all zero
- **THEN** the response is 201 and the persisted `materiales` snapshot is `[]`

### Requirement: REQ-ACT-005 Header fields and placeholders
The system SHALL present Fecha (read-only, labelled "Automatizado"), Vehículo, Nombre Cliente(s) and Dirección(es), with the exact placeholders «Ej. Acelmo Hernández, Guillermina Juárez, …» (Cliente) and «Ej. Huapacal 2da, Los Palmares, …» (Dirección). The system SHALL require Vehículo, Cliente(s) and Dirección(es) to be non-empty after trimming, with maximum lengths 100, 500 and 500 characters respectively.

#### Scenario: Required header fields
- **WHEN** an activity is submitted with a blank or over-limit Vehículo, Cliente(s) or Dirección(es)
- **THEN** the interface blocks the submission with a field message and the API responds 422 with no row written

### Requirement: REQ-ACT-006 Activity cells and "+ Agregar"
The system SHALL initially present one activity cell. WHEN the operator presses "+ Agregar", the system SHALL add one empty cell, up to a maximum of 30 cells. The system SHALL require at least one cell with content; empty cells are discarded on confirmation; each cell admits at most 500 characters.

#### Scenario: Cell limit and discard
- **WHEN** the operator adds cells until 30 exist
- **THEN** "+ Agregar" is disabled; and when empty cells remain at confirmation they are omitted from the payload, while an empty list, more than 30 cells or a cell over 500 characters is rejected with 422

### Requirement: REQ-ACT-007 Optional comments
WHERE the operator captures Comentarios, the system SHALL save them (maximum 2000 characters, line breaks allowed); if omitted, the system SHALL save the absence of comments. The interface SHALL send `comentarios: null` when the field is empty.

#### Scenario: Comments persisted or absent
- **WHEN** an activity is confirmed without comments, or with a multi-line comment
- **THEN** the stored `comentarios` is NULL or the literal text respectively; a comment over 2000 characters or with control characters other than line break is rejected with 422

### Requirement: REQ-ACT-008 Automatic folio
WHEN an activity is confirmed, PostgreSQL SHALL assign the next global correlative number, unique and without gaps among confirmed activities, and the system SHALL expose the folio as `R` plus the number zero-padded to at least 4 digits (never truncated). The system SHALL NOT accept a client-supplied folio.

#### Scenario: Global correlative folio
- **WHEN** two Unidades confirm activities in sequence
- **THEN** their folios are `R0001` and `R0002`, `folio_num` is 1 and 2 in the database, and a request carrying `folio` is rejected with 422; a rolled-back confirmation consumes no number

### Requirement: REQ-ACT-009 Automatic date
WHEN an activity is confirmed, PostgreSQL SHALL record the date-time with `now()` (timestamptz). The system SHALL NOT accept a client-supplied date. The interface SHALL present the date in the user's browser local time.

#### Scenario: Server-assigned timestamp
- **WHEN** an activity is confirmed
- **THEN** `created_at` is a `timestamp with time zone` set by the database and equal to the `fecha` returned by the API, and a request carrying `fecha` is rejected with 422

### Requirement: REQ-ACT-010 Materials and unit value snapshot
WHEN an activity is confirmed, the system SHALL freeze in the record the materials list (`material_id`, code, description, U.M., consumed quantity and current `valor_unitario`) derived exclusively from PostgreSQL. Later changes to the catalog or to seguimientos SHALL NOT alter the confirmed record. The system SHALL NOT accept client-supplied materials or unit values.

#### Scenario: Snapshot survives catalog changes
- **WHEN** the `valor_unitario` of a consumed material changes after the activity was confirmed
- **THEN** the stored `materiales` and the activity listing keep the value in force at confirmation

### Requirement: REQ-ACT-011 Atomicity and idempotency
The system SHALL execute the confirmation in a single transaction through the Stored Function `fn_crear_actividad`, with a `FOR UPDATE` lock on the seguimiento and a UNIQUE constraint on `seguimiento_id`. Two concurrent confirmations, or a retry, over the same seguimiento SHALL produce exactly one record; the other request SHALL respond 409 (`ACTIVIDAD_DUPLICADA`).

#### Scenario: Concurrent confirmations
- **WHEN** two confirmations for the same seguimiento run concurrently
- **THEN** one responds 201 and the other 409, and the database holds exactly one row and one folio for that seguimiento

### Requirement: REQ-ACT-012 Immutability and audit
The system SHALL treat a confirmed activity as append-only: UPDATE and DELETE SHALL be rejected by a database trigger, and the system SHALL NOT offer editing or deleting it. WHEN an activity is confirmed, the system SHALL emit in `auditoria_eventos` an `ACTIVIDAD_CONFIRMADA` event with `usuario` = actor, `equipo_origen_id` = Unidad, result `EXITO` and `detalles` containing `actividad_id`, `folio`, `seguimiento_id` and `equipo_id`.

#### Scenario: Trigger and ledger event
- **WHEN** an UPDATE or DELETE is attempted on a confirmed activity row
- **THEN** it fails with an append-only error, and exactly one `ACTIVIDAD_CONFIRMADA` event exists with the actor, Unidad, folio and ids of the activity

### Requirement: REQ-ACT-013 Input validation
IF the request body contains undeclared fields, wrong types, texts outside the limits of REQ-ACT-005/006/007, control characters (C0 except line break in Comentarios, DEL, C1) or unpaired Unicode surrogates, THEN the system SHALL respond HTTP 422 without accessing business data.

#### Scenario: Strict payload
- **WHEN** the payload carries an extra field such as `usuario` or `materiales`, a non-integer `seguimiento_id`, or a control character in any text
- **THEN** the response is 422 and no row or audit event is written; a path identifier outside INT4 yields the canonical 400 `NUMERIC_OUT_OF_RANGE`

### Requirement: REQ-ACT-014 Authorization per Unidad
WHILE the actor is neither an administrator nor a member of the Unidad, the system SHALL respond 403 on every activities endpoint; IF the Unidad does not exist, THEN 404 (404 before 403). The system SHALL require an authenticated actor on the POST.

#### Scenario: Access control
- **WHEN** an actor without membership calls any of the three endpoints, or an administrator without membership confirms an activity
- **THEN** the first receives 403 with no row written, an unknown Unidad receives 404 even for that actor, and the administrator succeeds with 201 and is recorded as `usuario`

### Requirement: REQ-ACT-015 No effect on inventory
The system SHALL NOT modify `inventario_equipos`, `seguimientos`, `seguimiento_items`, `actas_reportes`, the catalog or any stock balance when querying or confirming an activity.

#### Scenario: Inventory untouched
- **WHEN** an activity is confirmed
- **THEN** the Unidad inventory, the seguimiento state (still CERRADA) and the number of actas are identical before and after

### Requirement: REQ-ACT-016 Unidad activity listing
WHEN a client requests `GET /equipos/{equipo_id}/actividades`, the system SHALL return the confirmed activities of that Unidad ordered from most recent to oldest, with folio, date, vehicle, clients, addresses, activities, comments and materials.

#### Scenario: Ordered listing
- **WHEN** a Unidad has two confirmed activities
- **THEN** the list returns them newest first with `total` = 2 and the full record of each

### Requirement: REQ-ACT-017 Operation state presentation
The system SHALL show the user at all times the state of the confirmation operation (pending, successful, rejected); after success it SHALL show the assigned folio and refresh the state from the backend (no local stock state), and the form SHALL be left without a pending seguimiento (REQ-ACT-003); after a rejection the backend message SHALL be shown and the captured data preserved for retry.

#### Scenario: Success and rejection states
- **WHEN** the operator confirms and the backend answers 201
- **THEN** the interface shows the folio, invalidates the pending, history and audit queries, and re-reads the pending seguimiento; and when the backend answers 409 the message is shown, the entered data remain, and no query is invalidated

### Requirement: REQ-ACT-018 Contract and nomenclature
The system SHALL expose the activities fields in Spanish snake_case as frozen in the package OpenAPI contract (no legacy aliases), and UI texts SHALL use "Unidad" (never "Equipo"); technical identifiers `equipo`/`equipo_id` are kept.

#### Scenario: Frozen contract
- **WHEN** the live OpenAPI document is compared with the frozen contract of the three activities endpoints and their schemas
- **THEN** paths, methods, status codes, field names, types and limits are identical

### Requirement: REQ-ACT-019 Deterministic errors
The system SHALL map the errors of the Stored Functions to HTTP 400/404/409/422 with the canonical body `{"error":{"code","message","coordinates"}}`; business rules SHALL NEVER produce HTTP 500 nor expose SQL details.

#### Scenario: Domain error codes
- **WHEN** a confirmation is rejected by `fn_crear_actividad` or by a residual UNIQUE race
- **THEN** the body carries one of `SEGUIMIENTO_NO_ENCONTRADO` (404), `SEGUIMIENTO_NO_CERRADO` (409), `ACTIVIDAD_DUPLICADA` (409) or `ACTIVIDAD_INVALIDA` (422)

### Requirement: REQ-ACT-020 Reversibility and regression
The system SHALL provide Alembic migration 0029 with a `downgrade()` that removes the activities objects without loss of pre-existing tables, and SHALL keep the full backend and frontend suites green, the build without warnings and `openspec validate --specs --strict` passing.

#### Scenario: Migration round trip
- **WHEN** migration 0029 is upgraded, downgraded and upgraded again
- **THEN** the table, constraints, trigger and both functions are created and removed cleanly, audit events already written are preserved, and no pre-existing table is modified


### Requirement: REQ-REP-001 Reportes › Actividades subsection
The system SHALL offer in Reportes a subsection named "Actividades", placed after "Consumo" in the subsection bar, without altering the order or the behavior of "Entrega" and "Consumo".

#### Scenario: Tab order after Consumo
- **WHEN** an operator opens Reportes
- **THEN** the subsection bar lists Entrega, Consumo and Actividades in that order, and selecting Actividades mounts the activities report without changing how Entrega or Consumo behave

### Requirement: REQ-REP-002 Query of confirmed activities
WHEN the client requests `GET /reportes/actividades` with `formato=json` (the default), the system SHALL return the confirmed activities (frozen `ActividadListOut` DTO) matching the given filters, ordered from most recent to oldest, each with folio, fecha, Unidad, vehículo, clientes, direcciones, actividades, comentarios and materiales. The system SHALL accept the filters `equipo_id`, `desde`, `hasta` and `actividad_id`, combinable with AND semantics; without filters, the report SHALL cover every Unidad visible to the actor.

#### Scenario: JSON listing ordered and total
- **WHEN** `GET /reportes/actividades` is requested with `formato=json` and filters
- **THEN** the response is 200 with `{items, total}` ordered by `created_at DESC, id DESC` and each item carries folio, fecha, Unidad, vehículo, clientes, direcciones, actividades, comentarios and materiales

#### Scenario: AND semantics
- **WHEN** several filters are combined (e.g. `equipo_id` + `desde` + `hasta` + `actividad_id`)
- **THEN** only the activities satisfying all of them are returned

### Requirement: REQ-REP-003 Per-Unidad isolation
WHILE the actor is not an administrator, the system SHALL limit the report to the Unidades the actor belongs to: IF `equipo_id` names a foreign Unidad, THEN HTTP 403; IF `actividad_id` belongs to a foreign Unidad, THEN that activity SHALL be treated as nonexistent (empty result; 404 in `formato=xlsx`) without revealing its existence. The administrator SHALL see every Unidad. The system SHALL NOT exclude activities of decommissioned Unidades (documental history is preserved). IF `equipo_id` matches no Unidad, THEN the administrator SHALL receive an empty result (404 in `formato=xlsx`) and a non-administrator actor HTTP 403, indistinguishable from a foreign Unidad; this endpoint SHALL NOT apply the "404 before 403" rule of REQ-ACT-014.

#### Scenario: Foreign Unidad is denied
- **WHEN** a non-administrator actor requests `equipo_id` of a Unidad they do not belong to
- **THEN** the response is 403 without querying activity rows

#### Scenario: Decommissioned Unidad history is preserved
- **WHEN** the filter includes a decommissioned Unidad the actor belongs to
- **THEN** its confirmed activities remain visible

### Requirement: REQ-REP-004 Date filter in the business timezone
WHEN `desde` and/or `hasta` (calendar dates `AAAA-MM-DD`) are given, the system SHALL interpret them as whole days of the business timezone and include the activities whose confirmation date (REQ-ACT-009) satisfies `>= start of desde` and `< start of the day after hasta`, making both extremes inclusive. Each extreme SHALL apply independently: with only `desde` the filter is `>= start of desde`; with only `hasta`, `< start of the day after hasta`. IF `desde` is later than `hasta`, THEN the system SHALL respond HTTP 422 without querying business data; parameter validation (format and `desde > hasta`) SHALL precede authorization and the query. The system SHALL use the same business timezone to print the FECHA of the XLSX (REQ-REP-007).

#### Scenario: Inclusive day in the business timezone
- **WHEN** `desde` equals `hasta` and activities were confirmed at the local edges of that day (e.g. 00:30 and 23:30 in the business timezone)
- **THEN** both activities are included

#### Scenario: Invalid range rejects before anything else
- **WHEN** `desde > hasta` is requested, even for a foreign `equipo_id`
- **THEN** the response is 422 (`RANGO_FECHAS_INVALIDO`) without authorization or business queries

### Requirement: REQ-REP-005 Selection by operation
WHEN `actividad_id` is given, the system SHALL return only that activity (if it satisfies the other filters and the isolation), so the user can pick reports by operation, not only by dates. The system SHALL expose in the JSON response, per activity, the folio `R`+number as the operation label. `actividad_id` SHALL combine with AND with the other filters: an activity failing another filter produces an empty result (404 in `formato=xlsx`).

#### Scenario: Single operation
- **WHEN** the request carries a valid `actividad_id`
- **THEN** exactly that folio is returned, and it is absent if any other filter excludes it

### Requirement: REQ-REP-006 XLSX over the official template
WHEN the client requests `formato=xlsx`, the system SHALL generate the workbook by loading the official `REPORTE DE ACTIVIDADES.xlsx` template and injecting data into its cells, preserving styles, merged cells and the corporate logo; the system SHALL NOT build a workbook from scratch. The template path SHALL be a server constant (no user data involved) and the file on disk SHALL remain unmodified.

#### Scenario: Template reused, not rebuilt
- **WHEN** the XLSX report is generated
- **THEN** the workbook is produced from the official template with its styles, merges and logo, and the template file on disk keeps its checksum

### Requirement: REQ-REP-007 Field mapping from the snapshot
The system SHALL dump into every sheet, exclusively from the persisted record (never from the live catalog or stock): FOLIO (`FOLIO: R0001`), FECHA (confirmation date in the business timezone as text `20 / OCTUBRE / 2026`), VEHÍCULO, NOMBRE (clientes), DIRECCION, one materials row per snapshot line (CANTIDAD, U.M., MATERIAL and the **frozen** VALOR UNITARIO), one row per performed activity and COMENTARIOS (empty when absent). The system SHALL NOT perform stock or value arithmetic: quantities and unit value are transported as recorded; the COLABORADORES block SHALL stay blank.

#### Scenario: Frozen values, no arithmetic
- **WHEN** the sheet is filled from an activity record
- **THEN** every cell comes from the frozen snapshot, and no stock or monetary computation is applied

### Requirement: REQ-REP-008 Template overflow
WHILE an activity has more than 10 materials, more than 4 performed activities, or comments longer than the template area, the system SHALL expand the sheet without losing information or format: insert material and activity rows copying the style and merged cells of the reference row, shift downstream content (cells, merges, heights and images) and adjust the heights of the COMENTARIOS rows and, if the required height exceeds their capacity (409.5 pt per row, Excel limit), expand the area by inserting rows and extending its merges, so the full text (up to 2000 characters, with line breaks) stays intact and visible. Verifiable criterion: the sum of the heights of the area rows >= estimated lines × 13.2 pt (estimated lines = Σ per paragraph of `max(1, ceil(length / chars per line))`), no row exceeds 409.5 pt and the cell value equals the original text. Material descriptions longer than their cell width SHALL wrap with the same rule. An activity with zero materials SHALL generate the sheet with an empty materials table.

#### Scenario: Overflow expands, content survives
- **WHEN** an activity has 11 materials, 5 activities or a 2000-character comment
- **THEN** rows are inserted with copied style, downstream content shifts, and the resulting cell values equal the original texts

#### Scenario: Zero materials
- **WHEN** an activity has no materials
- **THEN** its sheet renders with an empty materials table

### Requirement: REQ-REP-009 One sheet per folio, 100-sheet cap
The system SHALL generate the workbook with exactly one sheet per folio of the query, titled with the folio (`R0001`), ordered by ascending folio, and SHALL include the corporate logo in **every** sheet. The workbook SHALL contain only folio sheets (the template's residual `Sheet1` is not included). IF the query exceeds 100 folios, THEN the system SHALL respond HTTP 422 with an indicative message and SHALL NOT generate the file.

#### Scenario: Folio sheets only, ascending
- **WHEN** the XLSX report has several folios
- **THEN** there is one sheet per folio titled `R####` in ascending order, each with the logo, and no `Sheet1`

#### Scenario: Over the folio cap
- **WHEN** the query matches 101 folios
- **THEN** the response is 422 (`LIMITE_HOJAS_EXCEDIDO`) and no file is produced

### Requirement: REQ-REP-010 XLSX safety and limits
IF a user text starts (after whitespace) with `=`, `+`, `-` or `@`, THEN the system SHALL neutralize it before writing it into the cell (no formula evaluation). The system SHALL build the attachment name only from constants, the folio and the date, sanitized to `[A-Za-z0-9._-]`. IF `formato=xlsx` yields no activity, THEN HTTP 404 without a file. The system SHALL impose a limit of 10 000 injected rows per workbook (materials + activities across all sheets) with HTTP 422 `LIMITE_FILAS_EXCEDIDO`, and SHALL generate the XLSX without blocking other requests.

#### Scenario: Formulas neutralized
- **WHEN** a user text begins (after whitespace, even after stripped control characters) with `=`, `+`, `-` or `@`
- **THEN** the cell is written as literal text, never as a formula

#### Scenario: Filas cap
- **WHEN** the workbook would exceed 10 000 injected rows
- **THEN** the response is 422 (`LIMITE_FILAS_EXCEDIDO`) and no file is produced

### Requirement: REQ-REP-011 Contract and canonical errors
The system SHALL expose the endpoint `GET /api/v1/reportes/actividades` with the codes 200, 400, 403, 404 and 422, reusing the `ActividadListOut`/`ActividadOut` DTOs; invalid parameters (`formato`, dates, non-numeric or <= 0 identifiers) and undeclared parameters SHALL respond HTTP 422 with the standard validation body `{"detail":[…]}`; positive identifiers beyond INT4 SHALL respond the canonical 400 `NUMERIC_OUT_OF_RANGE`; business-rule errors (404 no results; 422 `RANGO_FECHAS_INVALIDO`, `LIMITE_HOJAS_EXCEDIDO`, `LIMITE_FILAS_EXCEDIDO`) SHALL use the body `{"error":{"code","message","coordinates"}}`; the 403 keeps the current authorization body. A missing or invalid `X-Actor` SHALL respond 422 without querying business data. No business-rule error SHALL produce HTTP 500 or expose SQL details.

#### Scenario: Canonical bodies
- **WHEN** the endpoint rejects a request for any contract reason
- **THEN** the body matches the canonical shape of that code (validation detail, `NUMERIC_OUT_OF_RANGE`, or `{"error":{"code","message","coordinates"}}`)

### Requirement: REQ-REP-012 Per-folio breakdown and individual inspection
The system SHALL present in Reportes › Actividades a listing with one row per folio (folio, fecha in local time, Unidad, vehículo, cliente, dirección, number of activities and of materials, usuario) and SHALL let each folio be inspected — materials with CANTIDAD, MATERIAL, U.M. and frozen VALOR UNITARIO, performed activities and comments — without leaving the subsection. The system SHALL offer the filters Unidad, Desde, Hasta and the operation (folio) selector with the UI labels «Unidad», «Desde», «Hasta» and «Actividad».

#### Scenario: Row per folio, expandable inspection
- **WHEN** the operator views Reportes › Actividades
- **THEN** one row per folio shows its summary and expands to show materials, activities and comments in place

### Requirement: REQ-REP-013 Consolidated and per-folio downloads with states
WHEN the user triggers the consolidated download, the system SHALL request `formato=xlsx` with the current filters; WHEN the user triggers a folio download, it SHALL request `actividad_id` of that folio. The system SHALL show at all times the download state (in progress, successful with file name, rejected with the backend detail, including 404 and the 422 over the 100-folio cap), SHALL disable downloads with a visible reason while there is no listing, there is an error, or the result is empty, and SHALL clear the result when filters change.

#### Scenario: States and reasons
- **WHEN** a download is started, succeeds or is rejected (404 or 422 by cap)
- **THEN** the state is announced, and while idle conditions hold the download buttons are disabled with a visible reason

### Requirement: REQ-REP-014 Operation selectors in Entrega and Consumo
WHEN the user picks an operation in Reportes › Entrega (Acta) or Reportes › Consumo (Seguimiento), the system SHALL restrict the listing and the export to that operation by sending the existing backend `acta_id`; the options SHALL derive from the acts of the current listing (Unidad and dates) and show their visible identifier. The system SHALL NOT modify the backend, the contracts or the templates of Entrega and Consumo.

#### Scenario: Frontend-only selectors
- **WHEN** an operation is selected
- **THEN** `listarActas` and the export are called with `acta_id`, the options come from the current listing, and no Entrega/Consumo backend, contract or template changed

### Requirement: REQ-REP-015 Success link and listing freshness
WHEN an activity is confirmed successfully (REQ-ACT-017), the system SHALL offer in the success notice a direct access to "Reportes › Actividades" that opens the subsection with the just-confirmed Unidad and folio preselected; IF no navigation is available, THEN the action SHALL be hidden (no inert button). The system SHALL invalidate the Reportes › Actividades listing after confirming an activity, so the new folio appears without a manual reload.

#### Scenario: Link with preselection
- **WHEN** the confirmation succeeds and navigation exists
- **THEN** the success notice links to Reportes › Actividades with `equipoId` and `actividadId` preselected

#### Scenario: Invalidation
- **WHEN** an activity is confirmed
- **THEN** the `['reportes','actividades']` query is invalidated and the new folio shows in the listing

### Requirement: REQ-REP-016 Read-only with no side effects
The system SHALL NOT modify `actividades_reportes`, `inventario_equipos`, `seguimientos`, `seguimiento_items`, `actas_reportes`, the catalog or any stock balance when querying or exporting activities, and SHALL NOT emit audit events for the query or the export.

#### Scenario: No writes, no audit
- **WHEN** the report is queried as JSON or XLSX
- **THEN** the business tables keep identical snapshots and the audit ledger gains no events

### Requirement: REQ-REP-017 Regression and reversibility
The system SHALL keep the full backend and frontend suites green (including the Entrega and Consumo reports and the `/equipos/{equipo_id}/actividades*` endpoints), the build without warnings, the contracts of `/equipos/{equipo_id}/actividades*` in `openspec/openspec.yaml` free of drift and `openspec validate --specs --strict` passing. The system SHALL NOT require an Alembic migration; reverting the package SHALL consist of removing the router, the service and the new components.

#### Scenario: Reversibility
- **WHEN** the reportes-de-actividades router, service and frontend components are removed
- **THEN** the Entrega/Consumo reports and the Etapa 1 endpoints remain intact, and no migration is needed
