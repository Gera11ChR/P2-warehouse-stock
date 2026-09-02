# Spec 001 — Core Logistics & Ingestion

## Purpose

Defines the core enterprise fiber optic logistics behaviors: SKU catalog management, immutable audit trail recording, atomic inventory adjustments with concurrency control, ergonomic bulk ingestion, and stock alert signaling.

## Requirements

### Requirement: RF-1 Immutable audit trail
The system SHALL record all inventory transactions—including inbound receiving, outbound deployment, and fleet allocations—in an append-only, immutable PostgreSQL audit log table containing the actor ID, exact timestamp, and serialized JSON payload.

#### Scenario: Transaction writes audit row
- **WHEN** any inventory transaction executes
- **THEN** exactly one audit row is appended carrying actor ID, timestamp, and JSON payload, and no API operation may update or delete audit rows

### Requirement: RF-2 Administrator clearance enforcement
WHEN an authenticated user lacking explicit "Administrator" role clearance requests access to any administrative API endpoint, THE SYSTEM SHALL immediately deny the request, log the access attempt, and return an HTTP 403 Forbidden response.

#### Scenario: Operator denied on admin endpoint
- **WHEN** an authenticated Operator requests an administrative API endpoint
- **THEN** the system returns HTTP 403 and records an audit entry for the denied attempt

### Requirement: RF-3 Atomic concurrency control
WHILE any inventory balance mutation is active, the system SHALL enforce serialized, atomically-scoped locking across ALL balance-mutating paths (bulk adjustment, fleet allocation, inter-site transfer dispatch/receive, counter-adjustment) so that concurrent operations cannot produce race conditions, double-allocations, or invalid stock quantities.

#### Scenario: Concurrent adjustments serialize
- **WHEN** two bulk adjustment transactions target the same SKU concurrently
- **THEN** the operations serialize on the row lock and the final balance equals the exact mathematical result

#### Scenario: Cross-path serialization
- **WHEN** a bulk adjustment and an inter-site transfer dispatch target the same SKU and warehouse concurrently
- **THEN** the operations execute serially under the same locking protocol and the final balance equals the mathematically correct value

### Requirement: RF-4 Bulk payload validation rollback
IF an inbound bulk data-grid payload (e.g., from an Excel clipboard) contains a schema violation, negative quantity, or an unrecognized SKU in any individual row, THEN the system SHALL abort the entire batch transaction, prevent any partial database commits, and return an HTTP 422 Unprocessable Entity detailing the exact row indices of the failures.

#### Scenario: Single bad row rejects whole batch
- **WHEN** a bulk payload contains one row violating schema or business rules
- **THEN** nothing is committed and the response carries HTTP 422 with the exact failing row indices

### Requirement: RF-5 Stock alert threshold
WHERE a minimum stock threshold (`min_stock`) is configured for a specific fiber optic item, IF the derived aggregate `current_stock` evaluates to less than or equal to this threshold, THEN the system SHALL inject a "STOCK ALERT" status flag into all relevant data-grid API responses; the aggregate SHALL exclude in-transit quantities deducted at dispatch.

#### Scenario: Below threshold triggers alert
- **WHEN** an SKU's stock evaluates to less than or equal to its `min_stock`
- **THEN** all relevant data-grid responses for that SKU carry the "STOCK ALERT" flag

#### Scenario: Alert uses derived aggregate
- **WHEN** aggregate on-hand stock for an SKU falls to or below its `min_stock`
- **THEN** all relevant data-grid responses for that SKU carry the "STOCK ALERT" flag computed from the derived aggregate

### Requirement: REQ-STOCK-001 Per-warehouse inventory binding
The system SHALL maintain per-warehouse inventory such that every on-hand quantity is bound to exactly one active warehouse entity.

#### Scenario: Stock exists only under a warehouse
- **WHEN** any stock quantity is queried
- **THEN** it is attributable to exactly one warehouse with no unassigned loose quantity

### Requirement: REQ-STOCK-002 Derived aggregate stock
WHILE computing global SKU stock, the system SHALL derive `current_stock` exclusively as the aggregate SUM of on-hand quantities across warehouses for that SKU; no client-writable stock field shall exist on the SKU entity.

#### Scenario: Global stock equals warehouse sum
- **WHEN** global stock for an SKU is displayed or evaluated
- **THEN** its value equals the sum of that SKU's on-hand quantities across all warehouses

### Requirement: REQ-STOCK-003 Append-only movement ledger
The system SHALL maintain an append-only stock movement ledger recording, for every balance change: actor, timestamp, signed quantity change, movement type, target warehouse, and a reference to the originating event.

#### Scenario: Every balance change produces a movement row
- **WHEN** any balance mutation executes
- **THEN** exactly one ledger movement row is appended within the same atomic transaction, carrying actor, signed quantity, movement type, warehouse, and origin reference

### Requirement: REQ-STOCK-004 Global lock ordering
WHILE any balance-mutating path executes (transfers, legacy adjustments, bulk ingestion, counter-adjustments), the system SHALL apply a single global deterministic lock-ordering rule to prevent deadlocks and cross-path races.

#### Scenario: Opposing transfers do not deadlock
- **WHEN** two transfers move the same SKUs between the same two warehouses in opposite directions concurrently
- **THEN** both complete or fail cleanly without deadlock, and balances remain consistent
