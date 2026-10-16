# 001_core_logistics Specification

## Purpose

Core logistics invariants of the warehouse system: serialized atomic concurrency control across all balance-mutating paths, per-warehouse inventory binding, derived aggregate stock, append-only movement ledger and global lock ordering; the single unified fiber-optic inventory (Inventario FO), exact decimal quantities, the per-material Valor Unitario attribute and the database-computed Valor Total.

## Requirements

### Requirement: RF-3 Atomic concurrency control
WHILE any inventory balance mutation is active, the system SHALL enforce serialized, atomically-scoped locking across ALL balance-mutating paths (bulk adjustment, fleet allocation, inter-site transfer dispatch/receive, counter-adjustment) so that concurrent operations cannot produce race conditions, double-allocations, or invalid stock quantities.

#### Scenario: Concurrent adjustments serialize
- **WHEN** two bulk adjustment transactions target the same SKU concurrently
- **THEN** the operations serialize on the row lock and the final balance equals the exact mathematical result

#### Scenario: Cross-path serialization
- **WHEN** a bulk adjustment and an inter-site transfer dispatch target the same SKU and warehouse concurrently
- **THEN** the operations execute serially under the same locking protocol and the final balance equals the mathematically correct value

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

### Requirement: REQ-FO-001 Unified Inventario FO
The system SHALL maintain a single fiber-optic on-hand quantity per material (one general "Inventario FO" location) with no sub-sections, modules or intermediate sections in the interface, the API and the database; the unification migration (0027, historical) merged into one balance the quantities of the same material previously held in the legacy Paquete and En Uso inventories without loss or creation of quantity; any request that carries a module identifier (`modulo`, `origen_modulo`, `destino_modulo`) in a fiber-optic operation SHALL be rejected with HTTP 422 without side effects.

#### Scenario: Single balance per material
- **WHEN** the Inventario FO is queried
- **THEN** it shows at most one row per material (primary key `material_id`), with no module column

#### Scenario: No sub-sections in the interface
- **WHEN** the operator opens the Inventario FO
- **THEN** the navigation offers neither "Paquete" nor "En Uso" and one single table of fiber-optic materials is displayed

#### Scenario: Module identifier rejected
- **WHEN** `{"modulo": "PAQUETE"}` is sent to any Inventario FO operation
- **THEN** the response is HTTP 422 and no balance changes

### Requirement: REQ-FO-002 No legacy FO sections
The system SHALL expose only two section types, `GENERAL` and `FO` (`secciones.tipo`, `ck_secciones_tipo`); the former Paquete and En Uso sections (`FO_PAQUETE`/`FO_EN_USO`) SHALL NOT exist; the published contract (`GET /api/v1/inventario/secciones/transferibles`, `tipo` in {`GENERAL`,`FO`}) SHALL offer and emit only the active GENERAL sections and the unified Inventario FO; and IF a request references the `almacen_id` of a section that does not exist (including those formerly legacy) THEN the system SHALL respond HTTP 422 "Sección origen inexistente" / "Sección destino inexistente" without side effects.

#### Scenario: Former origins not selectable
- **WHEN** the operator opens the TRANSF origin/destination selector
- **THEN** only the active general sections and "Inventario FO" appear, and not "Paquete"/"En Uso"

#### Scenario: Purged section id rejected
- **WHEN** a draft TRANSF is created with `origen_almacen_id` equal to the id of a former FO_PAQUETE section
- **THEN** the response is HTTP 422 "Sección origen inexistente" and nothing is persisted

### Requirement: REQ-DEC-001 Decimal stock and quantities
The system SHALL represent as decimal quantities (non-negative numbers with up to 3 decimals and up to 12 digits in total, maximum `999 999 999.999`) the on-hand quantity of the General, FO and per-Unit inventories, the quantity of every movement line, the taken and consumed quantities of follow-ups, the quantity/stock parameter of every transactional operation and the quantity recorded in the audit ledger; the system SHALL preserve the non-negative balance invariant and the movement quantity greater than zero with decimal values; WHEN a confirmed movement with decimal quantities is cancelled the system SHALL revert exactly the original quantities; IF a quantity has more than 3 decimals, is negative where not allowed or exceeds the maximum THEN the system SHALL reject it (HTTP 400/422) without silent rounding and without altering balances; identifiers and `stock_minimo` SHALL remain integers.

#### Scenario: Fractional adjustment
- **WHEN** the stock of a material is adjusted to `7.250`
- **THEN** the API and the database return `7.250` and the audit event records the decimal differential

#### Scenario: Fractional transfer and cancellation
- **WHEN** `2.5` is transferred to a Unit and the movement is then cancelled
- **THEN** the origin returns exactly to its original quantity and the Unit to its own

#### Scenario: Over-precision rejected
- **WHEN** a quantity `1.0005` is sent
- **THEN** the response is HTTP 422 and no balance changes

#### Scenario: Concurrency with decimals
- **WHEN** two simultaneous TRANSF try to consume `8` and `7` from a stock of `10`
- **THEN** one completes, the other is rejected (HTTP 400/422) and the stock is never negative

### Requirement: REQ-VALOR-001 Valor Unitario attribute
The system SHALL associate to every material a Valor Unitario expressed in MXN as a non-negative decimal (up to 3 decimals, maximum `999 999 999.999`) shared by the General, FO and per-Unit inventories; IF a negative Valor Unitario, one with more than 3 decimals or one exceeding the maximum is assigned THEN the system SHALL reject the operation without modifying the material and return a validation error (HTTP 422) identifying the field.

#### Scenario: Value with decimals
- **WHEN** `12.345` is assigned to a material
- **THEN** the persisted value returned by the API is exactly `12.345`

#### Scenario: Value out of range
- **WHEN** `-1`, `1.2345` or `1000000000` is assigned
- **THEN** the response is HTTP 422 and the previous Valor Unitario does not change

### Requirement: REQ-VALOR-003 Transactional Valor Total calculation
The system SHALL calculate the Valor Total in PostgreSQL (`fn_valor_total_inventario`) as the sum, over all active materials with stock in active sections of the General inventory and in the Inventario FO, of `Stock Actual × Valor Unitario`, with exact arithmetic rounded to 3 decimals (half up) only at the end, and SHALL expose it in `GET /api/v1/inventario/resumen-general` together with the currency `MXN`; WHEN any balance (load, adjustment, +Cantidad, Mover, TRANSF, return, cancellation, deletion) or any Valor Unitario changes, the next calculation SHALL reflect the persisted state (no cache and no client-side calculation); IF there is no stock THEN the Valor Total SHALL be `0` (never null nor an error).

#### Scenario: General + FO consolidation
- **WHEN** material A (General) has stock 4 and value 2.5, and material B (FO) has stock 10 and value 1.25
- **THEN** the Valor Total is `22.500`

#### Scenario: Empty inventory
- **WHEN** no inventory row exists
- **THEN** the Valor Total is `0`

#### Scenario: Inactive material
- **WHEN** a material with stock becomes inactive
- **THEN** its value stops counting in the Valor Total

### Requirement: REQ-VALOR-005 Audit of Valor Unitario and of the unification
WHEN the Valor Unitario of a material changes, the system SHALL emit an immutable audit event with actor, timestamp, material and the previous and new values (the actor being the one that executed the request, set by the service before the ORM is mutated); the system SHALL keep intact (never updated nor deleted) all historical ledger events, including those that contain `modulo`; IF an edit does not modify the Valor Unitario THEN the system SHALL NOT emit a value event.

#### Scenario: Value change event
- **WHEN** the Valor Unitario goes from `1.000` to `2.500`
- **THEN** an event exists with previous value `1.000`, new value `2.500`, actor and date

#### Scenario: Ledger intact
- **WHEN** the migration is applied
- **THEN** the number and content of the previous events match those before migrating

### Requirement: REQ-VALOR-006 API contract and security
The system SHALL validate every API input that carries Valor Unitario, stock or quantities with strict decimal schemas (limits of REQ-VALOR-001/REQ-DEC-001) rejecting undeclared properties with HTTP 422, SHALL return Valor Unitario, stock, quantities and Valor Total as JSON numbers, and WHEN a request includes `valor_unitario` SHALL require the administrator role (HTTP 403 otherwise, evaluated by the presence of the field and an explicit `null` being a no-op) without affecting the other fields editable by authenticated actors; IF a PostgreSQL business rule rejects an operation THEN the API SHALL respond 400 or 422 with the canonical error and never 500; `GET /api/v1/inventario/resumen-general` SHALL require an authenticated actor (default-deny).

#### Scenario: Extra property
- **WHEN** an undeclared field is sent to the `PATCH` of a material
- **THEN** the response is HTTP 422

#### Scenario: Actor without privileges
- **WHEN** a non-administrator actor sends `valor_unitario`
- **THEN** the response is HTTP 403 and the value does not change

#### Scenario: Numeric representation
- **WHEN** a material with value `12.345` is queried
- **THEN** the JSON contains the number `12.345` (not the string `"12.345"`)

### Requirement: REQ-PURGA-001 Legacy FO purge and cleanup
The system SHALL contain no data that depends on the former FO Paquete/En Uso sections: the one-time migration `0028` SHALL physically delete the movements (any state, including those with only some legacy lines) and their lines, their delivery records (`actas_reportes`), the actor scopes, the idempotency keys and the audit events that depend on them (by section column, by JSON key `modulo`/`origen_modulo`/`destino_modulo` with value PAQUETE or EN_USO, by event type `FO_UNIFICADO`, and by reference to a purged `movimiento_id`/`acta_id`), SHALL null the `inventario_equipos.ultimo_movimiento_id` pointers to purged movements, SHALL redefine `ck_secciones_tipo` to {`GENERAL`,`FO`} and the FO routing functions to `tipo = 'FO'`, and SHALL NOT alter any balance or any event that does not meet the criteria (the unit of measure `PAQUETE (100 PZ)` and `modulo = 'CATALOGO'` are live domain).

#### Scenario: Mixed movement purged without touching balances
- **WHEN** a TEAMS movement has one line with a legacy origin and another with a general origin
- **THEN** the whole movement is deleted and every balance remains identical

#### Scenario: Live domain preserved
- **WHEN** a `MATERIAL_MODIFICADO` event contains `"u_m": "PAQUETE (100 PZ)"` and `"modulo": "CATALOGO"`
- **THEN** it remains intact after the purge

### Requirement: REQ-PURGA-002 Safe, atomic and traced purge
The system SHALL execute the purge in a single transaction with full rollback on any failure; SHALL keep both ledger-immutability triggers (`tg_ledger_auditoria_inmutable`, `tg_ledger_actas_inmutable`) enabled before and after (suspended only inside the transaction and verified re-enabled); SHALL emit exactly one immutable audit event `PURGA_LEGACY_FO` (counts per table and per event type, reference to amendment E-1 and to the backup) ; IF the database is not `p2` or `p2_test` and legacy-dependent rows exist THEN the migration SHALL abort without effects; and its `downgrade()` SHALL restore only the schema (never the data), warning that purged data is recoverable only from the prior `pg_dump`.

#### Scenario: Triggers re-enabled
- **WHEN** `0028` completes
- **THEN** a later `DELETE`/`UPDATE` on `auditoria_eventos` or `actas_reportes` fails with the immutability exception

#### Scenario: Failed verification
- **WHEN** an internal verification detects a residue or a balance difference
- **THEN** the migration rolls back and the database remains at `0027` with the triggers enabled

### Requirement: REQ-PURGA-003 Code without legacy FO bridge
The backend SHALL NOT contain acceptance, routing or special handling of the `FO_PAQUETE`/`FO_EN_USO` sections, and the frontend SHALL type `Seccion.tipo` as `'GENERAL' | 'FO'`, SHALL NOT contain presentation logic for historical FO modules, and SHALL label a section id that is not in the received list as "Sección #<id>" (never as "Inventario FO"); the published OpenAPI contract SHALL NOT change in paths, fields, types, enums or status codes (only `description` text).

#### Scenario: No legacy references in code
- **WHEN** the repository sweep looks for `FO_PAQUETE`/`FO_EN_USO` in `backend/app` and `frontend/src`
- **THEN** there are no matches
