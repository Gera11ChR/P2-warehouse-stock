# Spec Delta — 002_stock_transfer

## Purpose

Enables authorized, auditable movement of stock between warehouses through a two-phase dispatch/receive lifecycle, with per-site balances, immutable ledger records, and constitutional invariant enforcement.

## ADDED Requirements

### Requirement: REQ-STOCK-006 Transfer creation validation
WHEN a transfer creation request is received, THE SYSTEM SHALL validate distinct source/destination warehouses, SKU existence, positive integer quantities, and actor site-scope authorization on both warehouses, and SHALL reject invalid payloads with HTTP 422 identifying exact line coordinates.

#### Scenario: Invalid line rejected with coordinates
- **WHEN** a multi-line transfer payload contains an unrecognized SKU on the second line
- **THEN** the system returns HTTP 422, persists nothing, and reports the failing line index

#### Scenario: Out-of-scope warehouse rejected
- **WHEN** an actor submits a transfer involving a warehouse outside their assigned scope
- **THEN** the system returns HTTP 403 and records no transfer

### Requirement: REQ-STOCK-007 Idempotent transfer creation
WHEN a creation request duplicates a prior idempotency key for the same actor, THE SYSTEM SHALL return the original transfer response without creating duplicate state; WHEN the key belongs to a different actor, THE SYSTEM SHALL reject with HTTP 409 without disclosing the original transfer.

#### Scenario: Duplicate key replays original transfer
- **WHEN** an actor retries a creation request with the same idempotency key
- **THEN** the system returns the originally created transfer and creates no new rows

#### Scenario: Cross-actor key collision rejected
- **WHEN** a second actor submits a request reusing another actor's idempotency key
- **THEN** the system returns HTTP 409 and does not disclose the original transfer

### Requirement: REQ-STOCK-008 Approval threshold and MFA-gated approval
WHEN the total transfer quantity exceeds the configured approval threshold, THE SYSTEM SHALL place the transfer in PENDING_APPROVAL and SHALL require Administrator approval under a valid action-bound MFA elevation before dispatch; a rejection SHALL set status REJECTED and emit an audit event.

#### Scenario: Over-threshold transfer requires approval
- **WHEN** a transfer above the configured threshold is created
- **THEN** its status is PENDING_APPROVAL and dispatch is refused until an Administrator approves it under a valid action-bound MFA elevation

#### Scenario: Rejection sets terminal state and audits
- **WHEN** an Administrator rejects a PENDING_APPROVAL transfer
- **THEN** the transfer status becomes REJECTED and an audit event is recorded

### Requirement: REQ-STOCK-009 Scope-restricted transfer reads
WHEN any user requests transfer list or detail data, THE SYSTEM SHALL restrict results to transfers involving warehouses within the actor's assigned scope; out-of-scope detail requests SHALL return HTTP 404.

#### Scenario: List filtered by actor scope
- **WHEN** an actor lists stock transfers
- **THEN** only transfers involving warehouses in that actor's scope are returned

#### Scenario: Foreign detail hidden
- **WHEN** an actor requests details of a transfer with no warehouse in their scope
- **THEN** the system returns HTTP 404

### Requirement: REQ-STOCK-010 Cancellation authorization
WHEN an actor requests cancellation, THE SYSTEM SHALL permit it only from PENDING_APPROVAL or APPROVED state and only when the actor is the creator or holds scope on the involved warehouses; all other cancellation attempts SHALL be rejected.

#### Scenario: Creator cancels pre-dispatch transfer
- **WHEN** the creator cancels a transfer in APPROVED state
- **THEN** the transfer becomes CANCELLED with no quantity changes

#### Scenario: Cancel of dispatched transfer rejected
- **WHEN** any actor attempts to cancel a transfer in IN_TRANSIT state
- **THEN** the system returns HTTP 409 and the transfer state is unchanged

### Requirement: REQ-STOCK-011 Atomic dispatch
WHILE dispatching, THE SYSTEM SHALL lock the transfer row and the source warehouse inventory rows in deterministic order, re-validate sufficiency, deduct quantities, append debit ledger movements, and set status IN_TRANSIT within a single atomic transaction; any per-line failure SHALL roll back the entire transfer.

#### Scenario: Insufficient stock rolls back whole transfer
- **WHEN** dispatch is requested and one line lacks sufficient on-hand quantity
- **THEN** the entire dispatch rolls back, no quantity is deducted, and HTTP 422 identifies the failing line

#### Scenario: Successful dispatch deducts and logs
- **WHEN** dispatch completes successfully
- **THEN** source balances are reduced, debit ledger movements are appended, and status is IN_TRANSIT in one atomic transaction

### Requirement: REQ-STOCK-012 Atomic receive
WHILE receiving, THE SYSTEM SHALL lock the transfer row and the destination warehouse inventory rows, validate each received quantity against its dispatched quantity, credit balances, append credit ledger movements, and set status RECEIVED within a single atomic transaction.

#### Scenario: Successful receive credits destination
- **WHEN** a receive request with valid per-line quantities completes
- **THEN** destination balances are credited, credit ledger movements are appended, and status becomes RECEIVED atomically

### Requirement: REQ-STOCK-013 Receive payload validation
IF a receive payload contains an unknown line, a duplicated line, or a received quantity outside [0, dispatched_quantity], THEN the system SHALL reject the entire receive operation with HTTP 422 and exact coordinates, leaving the transfer IN_TRANSIT.

#### Scenario: Over-quantity receive rejected
- **WHEN** a receive payload reports a quantity greater than the dispatched quantity for a line
- **THEN** the system returns HTTP 422 with the line coordinate and applies no credits

#### Scenario: Duplicate line rejected
- **WHEN** a receive payload contains the same line more than once
- **THEN** the system returns HTTP 422 and applies no credits

### Requirement: REQ-STOCK-014 Illegal transition rejection
WHEN a state transition request targets a state other than a legal successor of the current state, THE SYSTEM SHALL reject with HTTP 409 Conflict and SHALL NOT modify any quantity.

#### Scenario: Dispatch before approval rejected
- **WHEN** dispatch is requested on a PENDING_APPROVAL transfer
- **THEN** the system returns HTTP 409 and no quantity changes

### Requirement: REQ-STOCK-015 Transition replay idempotency
WHERE a transition is retried after successful completion, THE SYSTEM SHALL return the current transfer state without double-applying quantity changes.

#### Scenario: Retried receive does not double-credit
- **WHEN** a receive request is retried after the transfer is already RECEIVED
- **THEN** the system returns the current RECEIVED state and no additional credits occur

### Requirement: REQ-STOCK-016 Transition serialization
WHILE any transition executes, THE SYSTEM SHALL prevent concurrent conflicting transitions so that double-dispatch, double-receive, or simultaneous cancel-and-dispatch cannot occur.

#### Scenario: Concurrent dispatch attempts
- **WHEN** two dispatch requests for the same transfer execute concurrently
- **THEN** exactly one succeeds and the other is rejected with HTTP 409

### Requirement: REQ-STOCK-017 Discrepancy counter-adjustment
IF on-hand and dispatched quantities do not reconcile at receive time, THEN the system SHALL record the discrepancy exclusively via an append-only counter-adjustment movement referencing the originating transfer; historical movement rows SHALL NOT be mutated.

#### Scenario: Shortage recorded via adjustment only
- **WHEN** a receive reports a quantity lower than dispatched and the discrepancy is accepted
- **THEN** the shortage is recorded as a new append-only counter-adjustment movement referencing the transfer, and no existing ledger row is modified

### Requirement: REQ-STOCK-018 Audit events
The system SHALL emit immutable audit events for every transfer state transition, authentication failure, TOTP verification attempt (success and failure), and MFA elevation grant or expiry, capturing actor, target entity, timestamp, and exact change context.

#### Scenario: Transition emits audit row
- **WHEN** any transfer state transition executes
- **THEN** exactly one audit event is appended in the same transaction with actor, target entity, and change context

### Requirement: REQ-STOCK-019 Migration quarantine
IF any migration backfill encounters negative legacy stock, THEN the system SHALL pre-flight detect and quarantine those rows for documented resolution and SHALL NOT lose data.

#### Scenario: Negative legacy balance quarantined
- **WHEN** backfill runs against legacy data containing a negative balance
- **THEN** that row is quarantined and reported, and all other rows backfill without data loss
