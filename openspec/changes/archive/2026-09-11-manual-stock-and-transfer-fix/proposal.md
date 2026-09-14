## Why

Operators cannot correct `STOCK ACTUAL` from the "Modificar Material" modal (the field is read-only and the backend rejects any stock field), so manual recount adjustments have no supported path. Additionally, the "Transferir Stock" modal's "ALMACÉN DESTINO" dropdown is empty because the frontend derives the warehouse list from inventory rows — warehouses without stock rows (e.g., `NORTE`, `SUR`) never appear.

## What Changes

- Add `GET /api/v1/warehouses`, returning the active warehouses the authenticated actor has scope for (from `user_warehouse_scopes`), so the transfer dialog always has valid destinations.
- Accept `on_hand_quantity` (non-negative integer) and an optional `warehouse_id` (default `CENTRAL`) in `PATCH /api/v1/materials/{codigo}`; the endpoint updates `warehouse_inventory.on_hand_quantity` under row locking.
- Record an immutable audit entry (`STOCK_ADJUST_MANUAL`) plus a `stock_movements` row (type `MANUAL_ADJUSTMENT`) with actor, SKU, old quantity, and new quantity on every manual stock adjustment.
- Frontend: make `STOCK ACTUAL` an editable number input in "Modificar Material" (edit mode), include `on_hand_quantity`/`warehouse_id` in the update payload.
- Frontend: load warehouses from the new endpoint and filter destinations by `is_active` and exclude the origin warehouse.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `003_inventory_dashboard`: manual stock override in the material edit flow (REQ-MAT) and destination warehouse lookup for the transfer dialog (REQ-DASH).

## Impact

- **Backend**: `app/api/v1/materials.py`, `app/schemas/material.py`, new `app/api/v1/warehouses.py` + `app/schemas/warehouse.py`, `app/services/inventory.py`, `app/main.py`.
- **Frontend**: `MaterialForm.tsx`, `TransferDialog.tsx`, `SeccionGeneral.tsx`, `services/materials.ts`, new `services/warehouses.ts`, `types.ts` (audit label).
- **Tests**: new backend `test_manual_stock_adjust.py`; new frontend Vitest setup and component tests.
- **Data**: `warehouse_inventory`, `stock_movements`, and `audit_logs` gain new rows; no schema migration required.
