# Proposal: Warehouse Inter-Site Stock Transfer [REQ-STOCK-001..999]

## Why

Physical operations span multiple storage sites, but the canonical model (spec 001) tracks a single global `skus.current_stock`, making inter-site movements impossible to express, audit, or authorize under Constitution 2.2 (material binding) and 3.2 (resource-scoped RBAC). Fleet data files in `data/` evidence multi-site material reality.

## What Changes

- New two-phase transfer lifecycle (PENDING_APPROVAL / APPROVED → dispatch → IN_TRANSIT → receive → RECEIVED, with REJECTED and CANCELLED exits) moving material between warehouses.
- **BREAKING**: `skus.current_stock` becomes a derived aggregate (view) instead of a writable column; legacy balance-mutation paths re-target to per-warehouse inventory.
- New data model: `warehouses`, `warehouse_inventory` (per-site balances, DB-enforced non-negative), `stock_transfers` (workflow state), `transfer_line_items` (multi-SKU), `stock_movements` (append-only ledger).
- New API surface `/api/v1/stock-transfers` (create / approve / dispatch / receive / cancel / list / detail) with site-scoped RBAC, MFA-gated approvals above a configurable quantity threshold, and idempotent creation.
- Migration: expand/contract with zero data loss; backfill existing `current_stock` into a default `CENTRAL` warehouse; pre-flight quarantine for any negative legacy balances (2.1, 4.3).

## Capabilities

### New Capabilities
- `002_stock_transfer`: inter-warehouse stock transfer lifecycle, authorization model, idempotency, and discrepancy handling.

### Modified Capabilities
- `001_core_logistics`: per-warehouse inventory model replaces the single global stock column; atomic locking guarantee extended across all balance-mutating paths; STOCK ALERT semantics updated to the derived aggregate.

## Impact

- **Data model**: new tables above; `skus.current_stock` → derived view; `stock_movements` ledger append-only with DB-role-level `REVOKE UPDATE/DELETE`.
- **Backend services**: refactor `InventoryService` lock target; add `TransferService` state machine; legacy bulk-ingest and fleet-allocation write paths route through `warehouse_inventory`.
- **API**: versioned `/api/v1/stock-transfers` surface; deterministic 403/404/409/422 error contract consistent with spec 001 RF-4.
- **Security**: action-bound single-use MFA elevation, TOTP rate limiting/lockout, TOTP seeds encrypted at rest, audit events per Constitution 6.2.
- **Verification**: concurrency tests (double-dispatch, A→B/B→A deadlock pair), migration up/down zero-loss test, idempotency tests, RBAC scope tests, `openspec validate --strict`.
