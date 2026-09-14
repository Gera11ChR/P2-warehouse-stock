# Spec 003 — Inventory Dashboard (Delta)

## ADDED Requirements

### Requirement: REQ-MAT-005 Edición manual de STOCK ACTUAL
The system SHALL allow an operator to edit the `STOCK ACTUAL` value directly in the "Modificar Material" modal, and SHALL persist it as `warehouse_inventory.on_hand_quantity` for the selected material's warehouse (defaulting to the `CENTRAL` warehouse when no warehouse is specified).

#### Scenario: Manual stock override updates on-hand quantity
- **WHEN** an operator opens "Modificar Material" and enters a non-negative integer in the `STOCK ACTUAL` field
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

## MODIFIED Requirements

### Requirement: REQ-MAT-001 Material CRUD
The system SHALL provide create, read, update, and delete operations for materials, with created, modified, and deleted materials persisted atomically; the delete operation SHALL be a logical soft-delete that marks the material inactive (`is_active = false`) and preserves referential integrity. Material updates SHALL additionally accept an optional manual `STOCK ACTUAL` override per REQ-MAT-005.

#### Scenario: Material created, updated, deleted
- **WHEN** the operator creates, modifies, or deletes a material
- **THEN** the operation persists the change and subsequent inventory queries reflect the new state

#### Scenario: Deleted material becomes inactive
- **WHEN** the operator deletes a material through the materials API
- **THEN** the material is marked inactive instead of being removed and is excluded from subsequent catalog and inventory queries
