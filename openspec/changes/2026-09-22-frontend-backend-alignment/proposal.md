# OpenSpec Proposal: Frontend-Backend Contract Alignment & Domain Adjustments
**Document Status:** Draft / Proposed
**Target Systems:** `backend/` (FastAPI), `frontend/` (React), `db/` (PostgreSQL)

## 1. Executive Summary
This proposal aims to bridge the gap between the original backend-driven architecture and the actual operational realities required by the enterprise administrators. It addresses specific ergonomic frictions, data isolation requirements for operational teams (`Equipos`), and field mutability constraints identified in the latest UI audits. 

## 2. Problem Statement
Based on the feedback from the administrative operators, the current system enforces several constraints that hinder operational flexibility:
1. **Fixed IDs in UI:** The `ID Lista` exposes database primary keys to the user, resulting in non-sequential numbering (e.g., starting at 10).
2. **Ghost Records:** Deleted materials remain visible in transfer selectors and history, breaking the user experience.
3. **Locked Fields:** `STOCK ACTUAL` and `CÓDIGO (SKU)` are locked during material modification in `Inventario General`, preventing flexible corrections.
4. **Shared Catalog Coupling:** `Equipos` and `Fibra Óptica` currently inherit the global catalog. The enterprise requires each entity to maintain its own strictly isolated inventory catalog.
5. **Audit Readability:** The `Auditoría` logs use `ID Lista` instead of `Descripción`, making it hard for admins to read.
6. **Data Persistence Bugs:** `Categoría` assignments are not persisting upon modification and are missing from the main data tables.

## 3. Proposed Specifications (The "What")

### 3.1. UI Numbering & Identifier Abstraction
* **Requirement:** Completely remove `ID Lista` as a visible identifier across all UI views (Tables, Forms, Audit, Bulk Search).
* **Implementation:** The frontend MUST generate a dynamic row index (`número de lista` starting from 1) for display purposes only. The backend will continue to use UUIDs/Ints for relational integrity, but these MUST remain hidden from the operator.

### 3.2. Absolute Material Deletion (Soft vs. Hard Delete)
* **Requirement:** When a material is deleted from the `Inventario General`, it MUST NOT appear in any subsequent dropdowns, active searches, or transfer forms. 
* **Implementation:** If soft-deletes are used in the DB, the backend APIs MUST strictly filter out `is_deleted=True` records from all active operational endpoints.

### 3.3. Flexible Mutation in `Inventario General`
* **Requirement:** Unlock the `STOCK ACTUAL` and `CÓDIGO (SKU)` fields in the `Modificar Material` form to allow direct administrative edits.
* **Constitutional Compliance (Amendment):** To respect the "Immutable Ledger" rule, modifying `STOCK ACTUAL` directly from the form MUST NOT be a naive SQL `UPDATE`. The backend MUST intercept this payload and automatically calculate and emit a counter-adjustment event (e.g., "Ajuste manual de administrador") in the `Auditoría` ledger.

### 3.4. Inventory Isolation (`Equipos` & `Fibra Óptica`)
* **Requirement:** Decouple the catalogs. Every created `Equipo` MUST have its own independent inventory catalog. It SHALL NOT inherit the global catalog by default.
* **Requirement:** The `Fibra Óptica` modules (`Paquete` and `En uso`) MUST drop the "carretes en stock / metros disponibles" specific schema. They MUST adopt the standard inventory schema: `CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`. The specific metric will be determined by the `U.M.` field.

### 3.5. Ergonomics in `Auditoría` & `Buscador a granel`
* **Requirement:** In the `Auditoría` view, replace the `ID Lista` column/filters with `Descripción`.
* **Requirement:** In the `Buscador a granel`, remove "Desde ID LISTA / Hasta ID LISTA" and replace it with "Desde número de lista a número de lista". Add a new filter parameter for "Desde descripción a descripción".

### 3.6. Category Persistence Fix
* **Requirement:** The `Categoría` field MUST persist successfully in the database when assigned or modified.
* **Requirement:** The `Categoría` MUST be returned in the API payload and displayed as a column in the `Inventario General` table to enable correct filtering.

## 4. Execution Tasks for OpenCode Agents

### UI/UX Agent (`ux-agent.md`, `ui-agent.md`)
- [ ] Remove `ID Lista` columns from all `InventoryTable`, `EquipoInventoryTable`, and `Auditoría` components. Replace with dynamic `número de lista`.
- [ ] Refactor `FibraOptica.tsx` to use the standard data table schema instead of the custom "carretes/metros" view.
- [ ] Add `Categoría` column to `InventoryTable`.
- [ ] Update `BulkSearch.tsx` inputs to use `número de lista` and `Descripción` range filters.

### State/Form Agent (`state-agent.md`, `form-agent.md`)
- [ ] Unlock `STOCK ACTUAL` and `CÓDIGO (SKU)` inputs in `MaterialForm.tsx` for edit mode.
- [ ] Ensure `Categoría` state is correctly bound and dispatched in the `Modificar` payload.

### Backend/API Agent
- [ ] Refactor `equipos` and `fibra optica` endpoints to support isolated table structures/relations (abandon global catalog inheritance).
- [ ] Update the material modification endpoint to detect changes in `STOCK ACTUAL` and auto-generate an audit ledger entry.
- [ ] Fix the `UPDATE` query/ORM logic to ensure `Categoría` is persisted.
