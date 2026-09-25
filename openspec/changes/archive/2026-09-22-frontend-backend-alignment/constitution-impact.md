# Constitution Impact Assessment (constitution-impact.md)
**Document Status:** Approved with Mitigations (v1.1 — Phase 1 Review)
**Source Context:** Udoc2 (`proposal.md`, `EARS.md` v1.1, `issues-breakdown.md`) + `domain-validation.md`
**Target Branch:** `feat/backend-logistics-fixes`

## 1. Executive Summary
This document analyzes the architectural and constitutional risks introduced by the `2026-09-22-frontend-backend-alignment` change set. The primary risks involve the request to allow manual stock editing (which threatens the immutable ledger) and the structural decoupling of inventories (which impacts transaction atomicity). Phase 1 adds binding governance conditions and domain clarifications ratified by the @arq-reviewer / @auditor governance pair.

## 2. Invariant Risk Analysis & Mitigation Strategies

### 2.1. Invariant: Immutable Audit Ledger (Append-Only)
* **Triggering Requirement:** `[REQ-UI-004]` — Allow administrators to edit `STOCK ACTUAL` directly from the UI form (Inventario General scope only).
* **Constitutional Risk:** **CRITICAL**. A direct SQL `UPDATE` to the `stock_actual` column bypasses the transactional ledger, erasing the history of who changed the stock and why, destroying traceability.
* **Mandatory Mitigation:** The backend `@coder` is strictly forbidden from executing a raw `UPDATE` for stock mutations. The API controller MUST calculate the delta (Difference = New Stock − Old Stock) and execute the PostgreSQL stored function `SELECT fn_ajustar_stock_almacen(...)`. This guarantees that the database trigger automatically appends an adjustment event to the `Auditoría` ledger.
* **Phase 1 Binding Condition:** `motivo` is MANDATORY and non-empty for every adjustment. The Pydantic schema SHALL reject empty motives (`Field(min_length=1)`), and the stored function SHALL raise an exception when `motivo` is NULL or empty.

### 2.2. Invariant: Data Integrity & Ghost Records
* **Triggering Requirement:** `[REQ-API-001]` — Omit deleted materials from all active operational endpoints.
* **Constitutional Risk:** **MEDIUM**. If soft-deleted items (`is_active = FALSE`) are allowed in `TEAMS` or `DEVOL` transfers, it creates ghost transactions tied to dead catalog entries, breaking referential logic.
* **Mandatory Mitigation:** `@coder` MUST enforce strict API-level filtering. All active `GET` queries and validation logic for transfers MUST append `WHERE is_active = True`. Physical deletion (`DELETE FROM`) remains forbidden to protect historical foreign keys.
* **Phase 1 Binding Condition:** The filter MUST also be applied to `stock_seccion` (`services/sparse_inventory.py`) and to every team inventory read. Zero ghost rows in operational views; the audit ledger is explicitly exempt (see 2.5).

### 2.3. Invariant: Transaction Atomicity & Concurrency
* **Triggering Requirement:** `[REQ-DOMAIN-001, REQ-DOMAIN-003]` — Isolate `Equipos` and `Fibra Óptica` into independent inventory catalogs, abandoning the Sparse Model.
* **Constitutional Risk:** **HIGH**. Changing the underlying table structures for these domains means the existing Stored Functions (`fn_procesar_movimiento`, `fn_cancelar_movimiento`) might fail or lock the wrong tables during concurrent `TEAMS` or `DEVOL` operations.
* **Mandatory Mitigation:** During Phase 2, `@dba-guard` MUST review and update the DDL for the stored functions to ensure they apply `FOR UPDATE` row-level locks on the *new* isolated tables (`inventario_equipos`, `inventario_fibra_*`), guaranteeing zero race conditions and preventing negative stock.
* **Phase 1 Binding Condition:** The TEAMS/DEVOL movement contract SHALL remain 100% functionally identical (`REQ-API-009`): same endpoints, same payloads, same state machine, same audit events. Existing regression tests SHALL pass unchanged.

### 2.4. Invariant: Relational Immutability vs. UI Abstraction
* **Triggering Requirement:** `[REQ-UI-001]` — Remove `ID Lista` from the UI.
* **Constitutional Risk:** **LOW**. Developers might mistakenly interpret this as a directive to remove the primary key from the database or alter relational mappings.
* **Mandatory Mitigation:** The database schema for `id_lista` MUST remain untouched (Integer, Primary Key, Immutable). The abstraction is strictly a presentation and DTO concern. The frontend will dynamically generate a 1-indexed `número de lista` for display, while the backend continues to map and expect the real ID internally.
* **Phase 1 Binding Condition:** In the `Buscador a granel`, the list number is resolved by the BACKEND via deterministic ordinal positioning (REQ-API-006): stable secondary ordering (`ORDER BY descripcion ASC, id_lista ASC`), `OFFSET/LIMIT` translation, and `start_index` in the response. Downloading full datasets to the client for manual filtering is FORBIDDEN (Principle 4: Backend is the Source of Truth).

### 2.5. Invariant: Audit Preservation & Human-Readable History (Phase 1 addition)
* **Triggering Requirement:** `[REQ-API-008]` — Auditoría reads with human-readable names.
* **Constitutional Risk:** **MEDIUM**. Filtering the audit ledger by `is_active` to "clean up" deleted materials would violate the immutable ledger invariant (2.4) and destroy accounting history.
* **Mandatory Mitigation:** The `Auditoría` API MUST resolve names via `LEFT JOIN` to `catalogo_materiales` WITHOUT any `is_active` filter. The response MUST include `descripcion`, `codigo`, `categoria`, and an `estado_activo` flag. The frontend MAY render a discreet `[Inactivo]` label. Historical events are NEVER hidden, NEVER mutated, NEVER deleted.

### 2.6. Invariant: Authorization Boundaries & Non-Negative Inventory (Phase 1 addition)
* **Triggering Requirement:** `[REQ-API-003]` — Counter-adjustment emission.
* **Constitutional Risk:** **MEDIUM**. An unauthenticated or low-privilege actor triggering stock adjustments would violate 3.1 (Default-Deny) and 3.2 (Resource-Scoped Authorization).
* **Mandatory Mitigation:** The material `PUT` endpoint with stock delta MUST require authenticated administrative authorization (existing `assert_authenticated` + role checks; MFA per 3.3 for elevated sessions). Non-negative balance remains enforced by the DB `CHECK` constraints (`ck_inventario_almacen_non_negative`, `ck_inventario_equipos_non_negative`) and by the stored functions.

## 3. Governance Bindings (Phase 1 — ratified)

1. **Operational Preservation:** TEAMS/DEVOL flows keep their contract 100% intact (`REQ-API-009`).
2. **Constitutional Shielding of Stock:** `fn_ajustar_stock_almacen` requires mandatory `motivo`; DB enforces non-negative stock.
3. **Zero Ghost Records:** strict `is_active = True` in `stock_seccion` and all operational inventory views (audit ledger exempt).
4. **Backend-First Rule (SDD v7.1):** ANY modification to `frontend/` is STRICTLY FORBIDDEN until backend Phases 1–5 are completed and approved. Frontend may only consume approved backend contracts and SHALL NOT redefine backend behavior.

## 4. Domain Clarifications (Phase 1 — ratified)

1. **Teams:** autonomous inventory (not "team catalogs"): `inventario_equipos` initialized empty at team creation; populated ONLY by audited TEAMS/DEVOL transfers; zero ghost/zero-stock rows rendered; every entry traceable to its originating movement.
2. **Bulk search:** list-number ranges resolved 100% in backend (deterministic ordinal positioning per 2.4). No full-dataset client downloads.
3. **Audit:** full immutable history always shown; `LEFT JOIN` name resolution without activity filter; optional `[Inactivo]` label; deactivation only affects operational selectors for new movements.

## 5. Architectural Verdict
**APPROVED (with binding mitigations).** The business requirements in Udoc2 can be implemented safely without violating the Constitution, provided the mitigations above (specifically the strict use of `fn_ajustar_stock_almacen` with mandatory `motivo`, proper `FOR UPDATE` locks on the new tables, the zero-ghost filtering discipline, and the audit-ledger preservation rule) are rigorously enforced by `@auditor` and `@dba-guard` during execution. Phase 2 (Data, Schemas & Security) is UNBLOCKED upon approval of this document.
