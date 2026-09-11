# Spec 003 — Inventory Dashboard

## Purpose

Provides the operator-facing warehouse management surface: Spanish-language navigation, KPI dashboard, filter toolbar, per-(SKU+Almacén) inventory browsing, material detail drawer, bulk search, fiber-optic spool tracking, team inventory assignment, and the material/inventory/team/fiber/KPI API contracts.

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
- **THEN** every visible label uses Spanish terms (e.g., "Almacén", "Stock Actual", "Stock Mínimo", "Alerta Stock", "Transferencia", "Inventario por Equipos") with no English equivalents

### Requirement: REQ-DASH-003 Navigation hierarchy
The system SHALL provide a sidebar navigation with the following structure: "Sección General", "Fibra Óptica" (with "Paquete" and "En Uso"), "Inventario por Equipos", "Transferencias", "Reportes", and "Auditoría".

#### Scenario: All navigation entries present
- **WHEN** the sidebar is rendered
- **THEN** each listed entry is present in the given hierarchy and selecting one navigates to its module

### Requirement: REQ-DASH-004 KPI dashboard cards
The system SHALL render four KPI cards — "Total Materiales" (blue), "Stock Total" (green), "Alertas Stock" (amber), and "Transferencias Hoy" (purple) — positioned above all inventory tables.

#### Scenario: Four KPI cards render above tables
- **WHEN** the Sección General module is displayed
- **THEN** the four KPI cards appear above the inventory table with their respective colors and current values

### Requirement: REQ-DASH-005 Filter toolbar and actions
The system SHALL render a filter toolbar immediately below the KPI cards with controls "Buscar", "Categoría", "U.M.", and "Almacén", and action buttons "+ Agregar" (green), "Modificar" (yellow), "Eliminar" (red), and "Transferir Stock" (blue).

#### Scenario: Filter toolbar renders
- **WHEN** the Sección General module is displayed
- **THEN** the filter toolbar appears below the KPI cards with the four filter controls and the four action buttons in their specified colors

### Requirement: REQ-DASH-006 Sección General inventory table
The system SHALL render the main inventory table with columns CÓDIGO (SKU), DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK, and ALMACÉN, and SHALL emit one row per (SKU + Almacén) combination.

#### Scenario: One row per SKU and warehouse
- **WHEN** a material holds stock in more than one warehouse
- **THEN** the table renders one row for each warehouse where that material has on-hand quantity, each carrying the exact ALMACÉN

#### Scenario: Table columns present in order
- **WHEN** the Sección General table is rendered
- **THEN** columns appear in the order CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK, ALMACÉN

### Requirement: REQ-DASH-007 Stock level color coding
The system SHALL color stock levels such that normal stock renders green, low stock renders amber, and critical stock renders red.

#### Scenario: Critical stock is red
- **WHEN** an SKU's stock falls into the critical band
- **THEN** its stock indicator renders red; normal renders green and low renders amber

### Requirement: REQ-DASH-008 Mandatory field ordering
The system SHALL render the Material Detail Drawer, CRUD forms, view modals, transfer dialogs, and edit screens with fields in the exact order: DESCRIPCIÓN, STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK, U.M., CÓDIGO (SKU), overriding any default UI framework or component-library ordering.

#### Scenario: Fields ordered correctly in every surface
- **WHEN** any detail drawer, CRUD form, view modal, transfer dialog, or edit screen is rendered
- **THEN** its fields appear in the order DESCRIPCIÓN, STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK, U.M., CÓDIGO (SKU)

### Requirement: REQ-DASH-009 Material detail drawer
The system SHALL provide a material detail drawer with a close button, fields in the mandatory order, and footer actions "Modificar", "Eliminar", and "Transferir Stock".

#### Scenario: Drawer opens on row selection
- **WHEN** a row in the Sección General table is selected
- **THEN** the material detail drawer opens showing the material's fields in the mandatory order and the three footer actions

#### Scenario: Fiber material shows remaining meters
- **WHEN** the selected material is a fiber-optic material in the "En Uso" view
- **THEN** the drawer displays "METROS RESTANTES" inside a highlighted blue information card

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

### Requirement: REQ-FIBER-001 Fiber-optic variant tracking
The system SHALL persist fiber-optic materials with a "Variante" and "Metros Restantes" attribute, distinct from general materials.

#### Scenario: Fiber material carries variant and remaining meters
- **WHEN** a fiber-optic material is stored or retrieved
- **THEN** its variant and remaining meters are persisted and returned alongside its SKU and description

### Requirement: REQ-FIBER-002 En Uso view columns
The system SHALL render the "En Uso" view with columns CÓDIGO, DESCRIPCIÓN, VARIANTE, METROS RESTANTES, and STOCK ACTUAL, and SHALL NOT replace "Metros Restantes" with stock counts.

#### Scenario: En Uso view shows remaining meters
- **WHEN** the "En Uso" view is displayed
- **THEN** the table shows CÓDIGO, DESCRIPCIÓN, VARIANTE, METROS RESTANTES, and STOCK ACTUAL, with remaining meters present and not substituted by a stock count

### Requirement: REQ-FIBER-003 Paquete and En Uso views
The system SHALL provide two fiber-optic views, "Paquete" and "En Uso", selectable within the Fibra Óptica module.

#### Scenario: Two fiber views available
- **WHEN** the Fibra Óptica module is opened
- **THEN** both "Paquete" and "En Uso" views are available and selecting one renders its corresponding table

### Requirement: REQ-TEAM-001 Team inventory records
The system SHALL persist team inventory records with columns Equipo, Usuario, Código SKU, Descripción, Cantidad, and Última Modificación.

#### Scenario: Team inventory record persisted
- **WHEN** a team inventory record is created or updated
- **THEN** its Equipo, Usuario, Código SKU, Descripción, Cantidad, and Última Modificación are stored and returned

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
