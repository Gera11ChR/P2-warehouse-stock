# Tasks — Warehouse Inter-Site Stock Transfer

## 1. Data Model & Migration

- [x] 1.1 Create SQLAlchemy models for `warehouses`, `warehouse_inventory` (CHECK on_hand >= 0, PK(warehouse_id, sku), INDEX(sku)), `stock_transfers` (VARCHAR+CHECK status, UNIQUE(actor_id, idempotency_key), FKs ON DELETE RESTRICT), `transfer_line_items` (UNIQUE(transfer_id, sku), CHECK quantities), `stock_movements` (actor_id, references_movement_id, nullable transfer_id) — verify `alembic upgrade head` succeeds and `openspec validate --strict` passes with zero violations
- [x] 1.2 Write EXPAND migration with negative-balance pre-flight quarantine and idempotent `CENTRAL` backfill (`ON CONFLICT DO NOTHING`) — verify up/down/up on seeded legacy data preserves every row and quarantines negatives without data loss
- [x] 1.3 Write CONTRACT migration dropping `skus.current_stock` with `downgrade()` reconstructing it via `SUM(warehouse_inventory)` — verify downgrade test restores the column to exact pre-drop values
- [x] 1.4 Add derived `current_stock` view and `REVOKE UPDATE, DELETE` on `stock_movements` and `audit_logs` for the app DB role — verify a direct UPDATE against the ledger fails with a permission error
- [x] 1.5 Reformat canonical `openspec/specs/001_core_logistics/spec.md` into the validated `## Purpose` + `## Requirements` structure (pre-existing drift blocking the 7.2 strict gate) — verify `openspec validate --specs --strict` reports 0 violations for the capability

## 2. Transactional Services

- [x] 2.1 Implement the global lock-ordering protocol (transfer row FOR UPDATE → inventory rows ORDER BY warehouse_id, sku) with business-rule re-validation under lock and deterministic 422s — verify a unit test asserting lock acquisition order
- [x] 2.2 Refactor `InventoryService.adjust_stock`, bulk ingest, and fleet-allocation write paths to mutate `warehouse_inventory` under the shared protocol — verify existing spec-001 concurrency test (10 simultaneous adjustments) still yields the exact mathematical balance with 0 failures
- [x] 2.3 Implement `TransferService.dispatch`: CAS status transition, sufficiency check, deduction, debit movements, audit insert in one atomic transaction — verify concurrent double-dispatch test shows exactly one success and one 409
- [x] 2.4 Implement `TransferService.receive`: minimal DTO resolution, per-line range validation, credit, credit movements, audit insert, status RECEIVED atomically — verify over-quantity, duplicate-line, and foreign-line payloads each produce 422 with line coordinates and zero credits
- [x] 2.5 Implement discrepancy counter-adjustments referencing origin movements (`references_movement_id`) — verify a shortage flow produces exactly one new ADJUSTMENT row and mutates no existing ledger row

## 3. API & Security

- [x] 3.1 Create `/api/v1/stock-transfers` routes (create, approve, reject, dispatch, receive, cancel, list, detail) with Pydantic v2 schemas using `extra="forbid"` (including nested) and server-derived field exclusions — verify schema tests reject unknown and server-derived fields
- [x] 3.2 Wire site-scoped RBAC: create/receive scope on both/respective warehouses, list filtered by scope, detail 404 out-of-scope, cancel restricted to creator or scoped operator — verify pytest returns 403/404 per matrix and never leaks out-of-scope transfers
- [x] 3.3 Implement idempotent creation (`INSERT ... ON CONFLICT` with key charset/length validation) — verify double POST returns the original transfer with no new rows and cross-actor key reuse returns 409
- [x] 3.4 Implement action-bound MFA elevation issuance (short TTL default 5 min, single-use, transfer-bound) with TOTP rate limiting and lockout; store TOTP seeds encrypted at rest — verify approve without elevation returns 403 and locked-out TOTP attempts are rejected and audited
- [x] 3.5 Implement audit events (6.2) for every transition, auth failure, TOTP attempt, and elevation grant/expiry with trace IDs — verify integration test asserts one audit row per transition carrying actor and change context

## 4. Quality Gates (Constitution 7.2)

- [x] 4.1 Run full test suite (concurrency, migration, RBAC, idempotency, audit) — verify 100% pass rate
- [x] 4.2 Run type check and build — verify zero type errors and zero build warnings
- [x] 4.3 Run `openspec validate --specs --strict` — verify zero schema violations
- [x] 4.4 Verify domain invariants hold: non-negative balances, single-location binding (IN_TRANSIT bound to transfer), ledger append-only — verify via invariant-focused test assertions
