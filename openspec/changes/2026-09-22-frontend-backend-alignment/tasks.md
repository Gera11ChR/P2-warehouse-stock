# Implementation Tasks (tasks.md)
**Document Status:** Approved for Implementation (v1.1 — Phase 1 Review)
**Source Context:** Udoc2 (`proposal.md`, `EARS.md` v1.1, `issues-breakdown.md`) + `domain-validation.md` + `constitution-impact.md` v1.1
**Target Branch:** `feat/backend-logistics-fixes`

This document serves as the strict execution checklist for Phase 2 (Data & Schemas) and Phase 3 (Backend Implementation) of the SDD Pipeline. Frontend work remains BLOCKED (Backend-First Rule) until backend Phases 1–5 are approved.

---

## Phase 2: Database & Schema Design (`@dba-guard` & `@sec-ops`)

### 1. Catalog & Category Schema Verification
- [x] **Task 2.1:** Verify or create Alembic migration ensuring the `categoria_id` FK (and `categorias.nombre UNIQUE`) exists and is properly constrained in the `Inventario General` table (`catalogo_materiales`). [REQ-API-004]
- [x] **Task 2.2:** Update Pydantic DTOs (`schemas/material.py`) to enforce `extra = "forbid"` and include `Categoría` in creation, update, and response payloads. [REQ-API-004, REQ-API-005]

### 2. Inventory Isolation Migrations (Track B)
- [x] **Task 2.3:** Generate Alembic migration to decouple `Equipos` inventory: keep `inventario_equipos` as the physical autonomous team inventory; DROP the sparse view `vw_inventario_equipo_completo` (abandoning the Sparse Model). Team inventories are physically independent from the global catalog. [REQ-DOMAIN-001, REQ-DOMAIN-002]
- [x] **Task 2.4:** Generate Alembic migration for `Fibra Óptica`: create independent inventory structures for `FO_PAQUETE` and `FO_EN_USO` aligned with the standard schema (`CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`); drop legacy `fiber_variants` (carretes/metros columns) and remove the `FO_PAQUETE`/`FO_EN_USO` section types; migrate existing data. [REQ-DOMAIN-003, REQ-DOMAIN-004, REQ-DOMAIN-005, REQ-DOMAIN-006]
- [x] **Task 2.5:** Review DDL of `fn_ajustar_stock_almacen`, `fn_procesar_movimiento`, `fn_cancelar_movimiento`: enforce mandatory non-empty `motivo` (RAISE on NULL/empty), keep non-negative `CHECK` constraints, and apply `FOR UPDATE` row-level locks on the new isolated tables (`inventario_equipos`, FO inventories) for zero race conditions. [REQ-API-003, REQ-API-009]

---

## Phase 3: Backend Implementation (`@coder`)

### 3. Ghost Records & Absolute Deletion (Track A)
- [x] **Task 3.1 [REQ-API-001]:** Refactor all `GET` endpoints for `Inventario General` and transfer selectors, INCLUDING `stock_seccion` (`services/sparse_inventory.py`). Inject a strict `.where(is_active == True)` or `is_deleted == False` clause in SQLAlchemy queries to completely omit deleted records from the JSON payload. Audit ledger reads are exempt.

### 4. Category Persistence (Track A)
- [x] **Task 3.2 [REQ-API-004, REQ-API-005]:** Update the `POST` and `PUT` controllers for materials. Ensure the `Categoría` field is correctly extracted from the payload (dual selector: `categoria_id` / `nueva_categoria`) and persisted via the ORM session. Ensure the response DTO includes the saved category.

### 5. Flexible Mutation & Audit Ledger (Track A)
- [x] **Task 3.3 [REQ-UI-004]:** Update the `PUT /api/v1/materials/{id}` endpoint to accept `CÓDIGO (SKU)` mutations (backend schema already supports `codigo`; verify end-to-end).
- [x] **Task 3.4 [REQ-API-002, REQ-API-003]:** Implement stock delta detection in the material `PUT` controller (Inventario General scope). If `STOCK ACTUAL` is modified in the payload, **DO NOT** execute a direct ORM update for the stock. Instead, compute the delta and route it through `SELECT fn_ajustar_stock_almacen(...)` with a MANDATORY non-empty `motivo` (schema-level `min_length=1`), guaranteeing an adjustment event is logged in `Auditoría`. Require administrative authorization.

### 6. Team Autonomous Inventory (Track B)
- [x] **Task 3.5 [REQ-DOMAIN-001, REQ-DOMAIN-002]:** Refactor the `Equipos` creation endpoint. Hook a post-creation service that immediately initializes an independent, EMPTY inventory for the new team (no global catalog inheritance, no preloaded material rows).
- [x] **Task 3.6 [REQ-DOMAIN-001, REQ-DOMAIN-002]:** Update the `GET /api/v1/equipos/{id}/inventario` endpoints to query the isolated `inventario_equipos` table directly, completely bypassing the legacy `vw_inventario_equipo_completo` sparse view. Render ONLY rows with real stock from audited movements; zero-stock/inactive ghost rows SHALL NOT appear. Each row SHALL expose its originating movement reference.

### 7. Fiber Optic Standardization (Track B)
- [x] **Task 3.7 [REQ-DOMAIN-003, REQ-DOMAIN-004, REQ-DOMAIN-005, REQ-DOMAIN-006]:** Update controllers for `Fibra Óptica`. Map incoming/outgoing data to the standard inventory schema for the new independent `Paquete` and `En uso` inventories. Ensure logic relies exclusively on the `U.M.` (Unidad de Medida) field to differentiate between spools, meters, or pieces. Remove dependencies on `fiber_variants`.

### 8. Search & Audit Ergonomics
- [x] **Task 3.8 [REQ-UI-006, REQ-API-008]:** Update `Auditoría` log retrieval endpoints to `LEFT JOIN` the material catalog (WITHOUT `is_active` filter) and return the material's `Descripción`, `codigo`, `categoria`, plus an `estado_activo` flag, rather than relying on `ID Lista`. Historical events SHALL remain fully visible (immutable ledger).
- [x] **Task 3.9 [REQ-UI-007, REQ-API-006, REQ-API-007]:** Update the `Buscador a granel` endpoint: accept `desde_numero_lista`/`hasta_numero_lista` translated to deterministic ordinal positioning (`ORDER BY descripcion ASC, id_lista ASC`, `OFFSET = X-1`, `LIMIT = Y-X+1`, response `start_index = X`), and accept `desde_descripcion`/`hasta_descripcion` applying deterministic range filters. NO full-dataset downloads to the client.

### 9. Regression Contract (Track A)
- [x] **Task 3.10 [REQ-API-009]:** Run the existing TEAMS/DEVOL test suite unchanged (`test_teams.py`, `test_devol.py`, `test_e2e_flujo.py`). The isolation changes SHALL NOT alter movement endpoints, payloads, state machines, or audit events. Any failure blocks Phase 3 exit.

> **Nota de ejecución (Fase 3, resolución de conflicto de contratos):** las suites TEAMS/DEVOL referencian el helper `catalogo_equipo`, que lee el CONTRATO DE PRESENTACIÓN del inventario de equipo (payload sparse con `id_lista` y filas fantasma de stock 0). Ese contrato de presentación queda formalmente deprecado por REQ-DOMAIN-002 (cero fantasmas, inventario autónomo). La interpretación vinculante de REQ-API-009 es: la LÓGICA DE MOVIMIENTOS (endpoints, payloads, máquina de estados, aritmética de stock en PostgreSQL y eventos de auditoría) no cambia; las aserciones de presentación que dependen del modelo sparse (filas en stock 0, clave `id_lista` del catálogo heredado) se migran en Fase 4 al endpoint canónico `GET /api/v1/equipos/{equipo_id}/inventario` (`InventarioEquipoOut`, clave `material_id`). En Fase 3, los fallos de esas suites atribuibles EXCLUSIVAMENTE al contrato de presentación deprecado son aceptados y documentados; cualquier otro fallo es defecto.

---

**Exit Criteria for Phase 3:** All checkboxes checked. No direct SQL stock updates executed in Python. `motivo` mandatory on every adjustment. Zero ghost rows in operational views. Audit ledger intact. TEAMS/DEVOL regression suite green. Pytest implementation (Phase 4) may begin.

---

## Phase F: Frontend Adaptation (`@ui-agent`, `@ux-agent`, `@form-agent`, `@state-agent`) — BLOCKED

**Backend-First Rule (SDD v7.1):** These tasks SHALL NOT start until backend Phases 1–5 are completed and approved. The frontend SHALL only consume approved backend contracts and SHALL NOT redefine backend behavior.

- [ ] **Task F.1 [REQ-UI-001, REQ-UI-002]:** Remove `ID Lista` columns from `InventoryTable`, `EquipoInventoryTable`, `Auditoría`; render dynamic 1-indexed `número de lista` (using `start_index` from REQ-API-006 in bulk search).
- [ ] **Task F.2 [REQ-UI-003]:** Immediately remove deleted materials from all active grids, dropdowns, and transfer selectors on delete.
- [ ] **Task F.3 [REQ-UI-004]:** Unlock `STOCK ACTUAL` and `CÓDIGO (SKU)` inputs in `MaterialForm.tsx` edit mode (Inventario General scope only), sending `stock_actual` + `motivo` to the approved backend contract.
- [ ] **Task F.4 [REQ-UI-005]:** Display the `Categoría` column in `InventoryTable`; bind and dispatch `categoria_id`/`nueva_categoria` correctly in the `Modificar` payload.
- [ ] **Task F.5 [REQ-UI-006]:** Render `Auditoría` with `Descripción` (and optional `[Inactivo]` label from `estado_activo`).
- [ ] **Task F.6 [REQ-UI-007]:** Update `BulkSearch.tsx` inputs: "Desde número de lista / Hasta número de lista" and "Desde descripción / Hasta descripción", rendering continuous numbers from backend `start_index`.
- [ ] **Task F.7 [REQ-DOMAIN-004]:** Refactor `FibraOptica.tsx` to the standard data table schema (U.M.-driven) instead of the legacy "carretes/metros" view.
