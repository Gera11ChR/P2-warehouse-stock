## Context

See proposal.md - Why. Key constraints from the existing system:

- `warehouse_inventory` rows are keyed by `(warehouse_id, sku)` with a `on_hand_quantity >= 0` check constraint.
- All balance-mutating paths serialize on row locks (`app/services/locking.py`) and write append-only `audit_logs` + `stock_movements` (Constitution 2.4, spec 001 RF-1/RF-3).
- Material updates go through `PATCH /api/v1/materials/{codigo}`; the schema uses `extra="forbid"`.
- There is no warehouse listing endpoint; `SeccionGeneral` derives warehouses from inventory rows, which is why the destination dropdown is empty.
- Transfer creation asserts the actor holds scope for both source and destination warehouses.

## Goals / Non-Goals

- Goals: editable `STOCK ACTUAL` in the edit modal with immutable audit trail; a scoped, active-warehouse listing endpoint; populated destination dropdown.
- Non-Goals: no initial-stock input on material create; no new PUT route (keep PATCH); no schema migration.

## Decisions

1. **New `GET /api/v1/warehouses` returning actor-scoped active warehouses.**
   Chosen over returning all active warehouses because transfer creation 403s on unscoped destinations; scoped results guarantee every option is usable. Unscoped actors get `[]` (consistent with `list_transfers`).
2. **`PATCH /materials/{codigo}` gains optional `on_hand_quantity` + `warehouse_id` (default `CENTRAL`).**
   Chosen over a separate stock endpoint because the edit modal already submits material changes; a single call keeps the UI simple. `on_hand_quantity`/`warehouse_id` are popped from the field-mapping loop (they are not `Sku` attributes).
3. **New `InventoryService.set_on_hand_quantity` service method.**
   Reuses `lock_inventory_rows` (RF-3), raises 422 when no inventory row exists, writes `StockMovement(movement_type="ADJUSTMENT", quantity_change = new − old)` — `ADJUSTMENT` because the `stock_movements` check constraint only permits the five existing types and this change is migration-free — and `make_audit(action="STOCK_ADJUST_MANUAL", details={warehouse_id, sku, old_quantity, new_quantity, movement_id})`. Zero-delta submissions (same value) skip the write.
   Alternative considered: reuse `InventoryService.adjust_stock` — rejected because it lacks old/new quantities in audit details required by REQ-MAT-006. A `MANUAL_ADJUSTMENT` movement type was considered but would require an Alembic expand/contract migration for no functional gain.
4. **Scope assertion on the target warehouse** (`assert_scope`) before mutating stock, matching every other balance-mutating path.
5. **Frontend warehouse source of truth becomes the new endpoint.**
   `SeccionGeneral` fetches it once (same effect as today) and passes it to both `FilterToolbar` and `TransferDialog`. `TransferDialog` filters `w.id !== origin && w.is_active`, and stores the select value in state (re-renders naturally on open since the dialog receives fresh props).
6. **`STOCK ACTUAL` input renders only in edit mode** (per user decision); create mode keeps the read-only display. Payload includes `on_hand_quantity` and `warehouse_id` only when the value changed.
7. **Audit label**: new frontend mapping `STOCK_ADJUST_MANUAL: 'Ajuste manual'` in `ACCIONES_AUDITORIA`.

## Risks / Trade-offs

- [Actor without `CENTRAL` scope edits stock with the default warehouse] → 403 from `assert_scope`; acceptable and consistent with transfer rules.
- [Row missing for (warehouse_id, sku)] → 422 `BusinessRuleError`, no partial commit (single transaction).
- [New endpoint response shape diverges from inventory's `items`] → dedicated `warehouses` key keeps it explicit; frontend service maps to `{id, name, is_active}`.
- [Vitest/jsdom are new dev dependencies] → pinned as devDeps only; no runtime bundle impact.

## Migration Plan

1. Deploy backend (new endpoint is additive; PATCH accepts new optional fields — backward compatible).
2. Deploy frontend.
3. Rollback: redeploy previous frontend build; backend additive changes are inert without the frontend.

## Open Questions

None.
