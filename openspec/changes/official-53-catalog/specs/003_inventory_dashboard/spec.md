# Spec 003 — Inventory Dashboard

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: REQ-MAT-001 Material CRUD
The system SHALL provide create, read, update, and delete operations for materials, with created, modified, and deleted materials persisted atomically; the delete operation SHALL be a logical soft-delete that marks the material inactive (`is_active = false`) and preserves referential integrity.

#### Scenario: Material created, updated, deleted
- **WHEN** the operator creates, modifies, or deletes a material
- **THEN** the operation persists the change and subsequent inventory queries reflect the new state

#### Scenario: Deleted material becomes inactive
- **WHEN** the operator deletes a material through the materials API
- **THEN** the material is marked inactive instead of being removed and is excluded from subsequent catalog and inventory queries

### Requirement: REQ-MAT-003 Seed data set
The system SHALL provide an idempotent seed routine that loads the official catalog of exactly 53 materials — 5 fiber-optic `CF-*` SKUs (`tipo=FIBRA`) and 48 general SKUs (`tipo=GENERAL`) — into the `CENTRAL` warehouse with zero initial stock and zero minimum stock (as registered in the DMS template), deactivates any non-official legacy SKU, and never deletes physical rows that hold transaction history.

#### Scenario: Seed loads full data set
- **WHEN** the seed routine is executed against an empty database
- **THEN** exactly 53 active SKUs matching the official list are created in `CENTRAL` with zero on-hand quantities and no RECEIPT stock movements for zero-quantity balances

#### Scenario: Seed is idempotent
- **WHEN** the seed routine is executed twice consecutively
- **THEN** the catalog still contains exactly 53 active SKUs with no duplicate rows, no database errors, and unchanged history counts
