# Constitution Impact Assessment (constitution-impact.md)
**Document Status:** Approved with Mitigations
**Source Context:** Udoc2 (`proposal.md`, `EARS.md`, `issues-breakdown.md`)
**Target Branch:** `feat/backend-logistics-fixes`

## 1. Executive Summary
This document analyzes the architectural and constitutional risks introduced by the `2026-09-22-frontend-backend-alignment` change set. The primary risks involve the request to allow manual stock editing (which threatens the immutable ledger) and the structural decoupling of inventories (which impacts transaction atomicity).

## 2. Invariant Risk Analysis & Mitigation Strategies

### 2.1. Invariant: Immutable Audit Ledger (Append-Only)
* **Triggering Requirement:** `[REQ-UI-004]` - Allow administrators to edit `STOCK ACTUAL` directly from the UI form.
* **Constitutional Risk:** **CRITICAL**. A direct SQL `UPDATE` to the `stock_actual` column bypasses the transactional ledger, erasing the history of who changed the stock and why, destroying traceability.
* **Mandatory Mitigation:** The backend `@coder` is strictly forbidden from executing a raw `UPDATE` for stock mutations. The API controller MUST calculate the delta (Difference = New Stock - Old Stock) and execute the PostgreSQL stored function `SELECT fn_ajustar_stock_almacen(...)`. This guarantees that the database trigger automatically appends an adjustment event to the `Auditoría` ledger.

### 2.2. Invariant: Data Integrity & Ghost Records
* **Triggering Requirement:** `[REQ-API-001]` - Omit deleted materials from active operational endpoints.
* **Constitutional Risk:** **MEDIUM**. If soft-deleted items (`is_active = FALSE`) are allowed in `TEAMS` or `DEVOL` transfers, it creates ghost transactions tied to dead catalog entries, breaking referential logic.
* **Mandatory Mitigation:** `@coder` MUST enforce strict API-level filtering. All active `GET` queries and validation logic for transfers MUST append `WHERE is_active = True`. Physical deletion (`DELETE FROM`) remains forbidden to protect historical foreign keys.

### 2.3. Invariant: Transaction Atomicity & Concurrency
* **Triggering Requirement:** `[REQ-DOMAIN-001, REQ-DOMAIN-003]` - Isolate `Equipos` and `Fibra Óptica` into independent inventory catalogs, abandoning the Sparse Model.
* **Constitutional Risk:** **HIGH**. Changing the underlying table structures for these domains means the existing Stored Functions (`fn_procesar_movimiento`, `fn_cancelar_movimiento`) might fail or lock the wrong tables during concurrent `TEAMS` or `DEVOL` operations.
* **Mandatory Mitigation:** During Phase 2, `@dba-guard` MUST review and update the DDL for the stored functions to ensure they apply `FOR UPDATE` row-level locks on the *new* isolated tables (`inventario_equipos`, `inventario_fibra`), guaranteeing zero race conditions and preventing negative stock.

### 2.4. Invariant: Relational Immutability vs. UI Abstraction
* **Triggering Requirement:** `[REQ-UI-001]` - Remove `ID Lista` from the UI.
* **Constitutional Risk:** **LOW**. Developers might mistakenly interpret this as a directive to remove the primary key from the database or alter relational mappings.
* **Mandatory Mitigation:** The database schema for `id_lista` MUST remain untouched (Integer, Primary Key, Immutable). The abstraction is strictly a presentation and DTO concern. The frontend will dynamically generate a 1-indexed `número de lista` for display, while the backend continues to map and expect the real ID internally.

## 3. Architectural Verdict
**APPROVED.** The business requirements in Udoc2 can be implemented safely without violating the Constitution, provided the mitigations above (specifically the strict use of `fn_ajustar_stock_almacen` and proper `FOR UPDATE` locks on the new tables) are rigorously enforced by `@auditor` and `@dba-guard` during execution.