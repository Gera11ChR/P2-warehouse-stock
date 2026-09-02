# Design — Warehouse Inter-Site Stock Transfer

## Context

Spec 001 models a single global `skus.current_stock` with no warehouse entity. This change introduces per-site balances, a two-phase transfer workflow, and a new API surface, while keeping the constitution's invariants provable (2.1 non-negative, 2.2 material binding, 2.3 serialization, 2.4 append-only ledger with counter-adjustments). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Per-warehouse balances with DB-level non-negative enforcement.
- Two-phase dispatch/receive lifecycle with explicit IN_TRANSIT recovery state.
- One global locking protocol across all balance-mutating paths (transfers, legacy adjust_stock, bulk ingest, counter-adjustments) so there is a single lock domain.
- Site-scoped RBAC on every transfer endpoint; action-bound MFA elevation for over-threshold approvals.
- Zero-data-loss expand/contract migration.

**Non-Goals:**
- Fleet-vehicle restocking (vehicles stay out of this change; `warehouses` leaves room for a future site model).
- Cost/valuation tracking and third-party logistics integration.
- Mutating transfer workflow rows is accepted (they are workflow state, not ledger); ledger immutability applies to `stock_movements` and `audit_logs` only.

## Decisions

### D1: `skus.current_stock` becomes a derived VIEW, not a cached column
- **Decision**: a DB view `SUM(warehouse_inventory.on_hand_quantity) GROUP BY sku`; all legacy write paths re-targeted to `warehouse_inventory` in this same change.
- **Why**: a cached column creates a dual-write hazard and a second lock domain over the same physical quantity (guard audit R2/R3). The view is always correct by construction.
- **Alternatives considered**: materialized view (staleness windows), trigger-maintained counter (hidden write path, harder to test), keeping the column (rejected — dual-write).

### D2: Two-phase lifecycle with status-guarded transitions (CAS)
- **Decision**: transitions execute as `UPDATE stock_transfers SET status = '<next>' WHERE transfer_id = ? AND status = '<expected>'` under a `SELECT ... FOR UPDATE` on the transfer row; `rowcount == 0` → HTTP 409. Replays of completed transitions return the current state (no-op), satisfying 4.2.
- **Why**: plain status checks race; CAS + row lock makes double-dispatch/double-receive impossible (4.1/4.2, 2.3).
- **Alternatives considered**: version column with optimistic locking (same effect, more surface), exclusive advisory locks (opaque, easy to misuse).

### D3: Global lock ordering
- **Decision**: every balance-mutating transaction acquires locks in this order: (1) workflow row (`stock_transfers`, if applicable), (2) `warehouse_inventory` rows `ORDER BY warehouse_id ASC, sku ASC` via `SELECT ... FOR UPDATE`. Business rules are re-validated after acquiring locks, and deterministic 422s are raised before any DB CHECK constraint can surface as IntegrityError.
- **Why**: one total order across all paths eliminates cross-path deadlock (A→B vs B→A) (2.3).
- **Alternatives considered**: SKIP LOCKED retry loops (complex, still racy), single global mutex (kills throughput).

### D4: Append-only ledger + write-once workflow fields
- **Decision**: `stock_movements` (signed quantity, movement type TRANSFER_OUT/TRANSFER_IN/ADJUSTMENT/RECEIPT/DISPATCH, `actor_id`, `references_movement_id` nullable for counter-adjustments, `transfer_id` nullable for non-transfer movements) is append-only at code level AND the application DB role gets `REVOKE UPDATE, DELETE` on it and on `audit_logs` (defense-in-depth per 8.2). Workflow fields `requested_by`, `approved_by`, `dispatched_at`, `received_at` are write-once (service-layer guard).
- **Why**: 2.4 requires discrepancies resolved exclusively via traceable counter-adjustments referencing the target event; the `references_movement_id` column makes that expressible. 6.2 requires actor on every adjustment → `actor_id` on movements.
- **Alternatives considered**: dual-write paired `audit_logs` per movement (rejected — single source of truth, movement row already carries actor + context).

### D5: Status as VARCHAR + CHECK, not PG ENUM
- **Decision**: `status VARCHAR(20) NOT NULL CHECK (status IN (...))`.
- **Why**: native enums make adding values painful (cannot use a new value in the same transaction as ALTER TYPE); VARCHAR+CHECK migrates cleanly and rollback trivially.

### D6: Composite idempotency key
- **Decision**: `UNIQUE (actor_id, idempotency_key)`; key bounded to 64 chars with strict charset validation; creation uses `INSERT ... ON CONFLICT` returning the stored transfer inside the transaction. Same-actor replay returns the original; cross-actor collision returns 409 without disclosure.
- **Why**: a global UNIQUE key allows cross-actor squatting and original-response leakage (guard audit); actor-scoped uniqueness closes that while keeping 4.2 semantics.

### D7: Action-bound MFA elevation
- **Decision**: over-threshold approvals require a dedicated elevation issuance: TOTP verification returns a short-TTL, single-use, transfer-bound elevation token (`transfer_id` + action). TOTP attempts are rate-limited with lockout; successes and failures audited (6.2). TOTP seeds stored encrypted at rest (envelope encryption) — seeds cannot be one-way hashed. JWT uses short TTL plus per-request server-side scope re-validation against current assignments (stale-claim defense).
- **Why**: 3.3 requires MFA prior to elevated session issuance; binding the elevation to the transfer id prevents reuse.

### D8: Receive DTO minimality
- **Decision**: receive body is strictly `[{line_id, received_quantity}]`; server resolves lines within the transfer only; duplicate or foreign `line_id` → 422; `0 <= received_quantity <= dispatched_quantity` enforced by schema CHECK and re-validated under lock.
- **Why**: shrinks the mass-assignment surface (3.5); over-credit becomes impossible by construction.

### D9: Expand/contract migration
- **Decision**: EXPAND creates tables and backfills `INSERT INTO warehouse_inventory SELECT 'CENTRAL', sku, current_stock FROM skus ON CONFLICT DO NOTHING` after a pre-flight negative-balance quarantine (quarantine rows logged, never dropped — 2.1/4.3). `skus.current_stock` remains during expand. CONTRACT is a later migration dropping the column; `downgrade()` reconstructs `current_stock` via `SUM(warehouse_inventory)`. `sku`-only index added to `warehouse_inventory` for aggregate/alert queries. All FKs `ON DELETE RESTRICT`. `UNIQUE (transfer_id, sku)` on line items.
- **Why**: zero data loss both directions; expand phase keeps rollback trivial; downgrade reconstruction makes the contract reversible.

## Risks / Trade-offs

- [IN_TRANSIT quantity is bound to the transfer, not a warehouse] → documented as the 2.2-compliant binding state; reconciliation endpoint lists IN_TRANSIT transfers; excluded from `current_stock` (deducted at dispatch) and from STOCK ALERT math.
- [Crash between dispatch and receive leaves material in transit] → IN_TRANSIT is explicit and visible via the list endpoint; recovery is a business receive/counter-adjustment, never manual DB manipulation (4.3).
- [Legacy negative balances in live data] → pre-flight quarantine; documented resolution path; otherwise the CHECK constraint would abort the backfill.
- [Stale JWT scope claims] → short TTL + per-request scope re-validation.
- [TOTP brute force] → rate limiting + lockout + audit of attempts.
- [Status CHECK drift over time] → new states ship as a dedicated migration; checklist documented in design.

## Migration Plan

1. EXPAND migration: create tables, indexes, constraints; pre-flight quarantine; backfill `CENTRAL` warehouse.
2. Deploy code with dual-read (view + legacy column during transition window); legacy write paths re-targeted to `warehouse_inventory`.
3. Verify aggregate view equals legacy column across SKUs (reconciliation query).
4. CONTRACT migration drops `skus.current_stock`; rollback via `downgrade()` reconstruction.
5. `REVOKE UPDATE, DELETE` on `stock_movements` and `audit_logs` for the application DB role.

## Open Questions

None — approval threshold default value and MFA elevation TTL are configurable runtime parameters; defaults are recorded in tasks (threshold default 100 units, elevation TTL 5 minutes) and may be tuned without spec changes.
