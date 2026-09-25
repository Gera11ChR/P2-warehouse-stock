# Implementation Tasks (tasks.md)
**Document Status:** Approved for Implementation
**Source Context:** Udoc2 (`proposal.md`, `EARS.md`, `issues-breakdown.md`)
**Target Branch:** `feat/backend-logistics-fixes`

This document serves as the strict execution checklist for Phase 2 (Data & Schemas) and Phase 3 (Backend Implementation) of the SDD Pipeline.

---

## Phase 2: Database & Schema Design (`@dba-guard` & `@sec-ops`)

### 1. Catalog & Category Schema Verification
- [ ] **Task 2.1:** Verify or create Alembic migration ensuring the `categoria_id` (or equivalent string field for `Categoría`) exists and is properly constrained in the `Inventario General` table.
- [ ] **Task 2.2:** Update Pydantic DTOs (`schemas/material.py`) to enforce `extra = "forbid"` and include `Categoría` in creation, update, and response payloads.

### 2. Inventory Isolation Migrations (Track B)
- [ ] **Task 2.3:** Generate Alembic migration to decouple `Equipos` inventory. Create or modify tables to ensure team inventories are physically independent from the global catalog (abandoning the Sparse Model).
- [ ] **Task 2.4:** Generate Alembic migration for `Fibra Óptica` (`FO_PAQUETE`, `FO_EN_USO`) to drop legacy columns (`carretes en stock`, `metros disponibles`) and align with the standard schema (`CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`).

---

## Phase 3: Backend Implementation (`@coder`)

### 3. Ghost Records & Absolute Deletion (Track A)
- [ ] **Task 3.1 [REQ-API-001]:** Refactor all `GET` endpoints for `Inventario General` and transfer selectors. Inject a strict `.where(is_active == True)` or `is_deleted == False` clause in SQLAlchemy queries to completely omit deleted records from the JSON payload.

### 4. Category Persistence (Track A)
- [ ] **Task 3.2 [REQ-API-004, REQ-API-005]:** Update the `POST` and `PUT` controllers for materials. Ensure the `Categoría` field is correctly extracted from the payload and persisted via the ORM session. Ensure the response DTO includes the saved category.

### 5. Flexible Mutation & Audit Ledger (Track A)
- [ ] **Task 3.3 [REQ-UI-004]:** Update the `PUT /api/v1/materials/{id}` endpoint to accept `CÓDIGO (SKU)` mutations.
- [ ] **Task 3.4 [REQ-API-002, REQ-API-003]:** Implement stock delta detection in the material `PUT` controller. If `STOCK ACTUAL` is modified in the payload, **DO NOT** execute a direct ORM update for the stock. Instead, route the delta through `SELECT fn_ajustar_stock_almacen(...)` to guarantee an adjustment event is logged in `Auditoría`.

### 6. Team Inventory Isolation (Track B)
- [ ] **Task 3.5 [REQ-DOMAIN-001, REQ-DOMAIN-002]:** Refactor the `Equipos` creation endpoint. Hook a post-creation service that immediately initializes an independent, empty inventory structure for the new team.
- [ ] **Task 3.6:** Update the `GET /api/v1/equipos/{id}/inventario` endpoints to query the isolated team tables directly, completely bypassing the legacy `vw_inventario_equipo_completo` sparse view.

### 7. Fiber Optic Standardization (Track B)
- [ ] **Task 3.7 [REQ-DOMAIN-003, REQ-DOMAIN-004]:** Update controllers for `Fibra Óptica`. Map incoming/outgoing data to the standard inventory schema. Ensure logic relies exclusively on the `U.M.` (Unidad de Medida) field to differentiate between spools, meters, or pieces [REQ-DOMAIN-005].

### 8. Search & Audit Ergonomics
- [ ] **Task 3.8:** Update `Auditoría` log retrieval endpoints to join and return the material's `Descripción` rather than relying on `ID Lista`.
- [ ] **Task 3.9:** Update the `Buscador a granel` endpoint to accept `desde_descripcion` and `hasta_descripcion` query parameters, applying dynamic `ILIKE` or range filters in SQLAlchemy.

---
**Exit Criteria for Phase 3:** All checkboxes checked. No direct SQL stock updates executed in Python. Pytest implementation (Phase 4) may begin.