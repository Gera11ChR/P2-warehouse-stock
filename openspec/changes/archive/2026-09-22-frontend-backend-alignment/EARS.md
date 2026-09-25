# Specification Document (EARS): Frontend-Backend Alignment & Domain Adjustments
**Document Status:** Approved for Implementation (v1.1 — Phase 1 Review)
**Source Proposal:** `proposal.md` (Based on user UI/UX feedback)
**Phase 1 Amendments:** Derived from approved `domain-validation.md` (Fase 0) — binding governance conditions and domain clarifications.

## Amendment Log

| Version | Change |
|---|---|
| v1.1 | REQ-API-001 explicit scope (stock_seccion + team views); REQ-UI-004 scope restricted to Inventario General; REQ-API-002/003 mandatory `motivo` + DB non-negative; REQ-UI-007 split: ordinal backend contract; NEW REQ-API-006 (ordinal positioning), REQ-API-007 (description range), REQ-API-008 (audit LEFT JOIN), REQ-API-009 (TEAMS/DEVOL regression); REQ-DOMAIN-002 rewritten (autonomous inventory, zero-ghost, movement traceability); NEW REQ-DOMAIN-006 (FO independent inventory roots, deprecate fiber_variants). |

## Level A: Operational & Ergonomic Requirements (UI & API Contracts)
*These requirements address interface frictions, payload corrections, and identifier abstractions without fundamentally changing the core business models.*

### 1. Identifier Abstraction
* **[REQ-UI-001]** The frontend SHALL NOT display the `ID Lista` across any view, including Tables, Forms, `Auditoría` logs, or `Buscador a granel`.
* **[REQ-UI-002]** The frontend SHALL display a dynamic, 1-indexed sequential row number (`número de lista`) for all inventory data grids for display purposes only.

### 2. Absolute Deletion Handling
* **[REQ-API-001]** While a material is marked as deleted in the database, the backend API SHALL completely omit this record from all active operational endpoint responses, including the catalog list, transfer selectors, section stock (`stock_seccion`), and team inventory reads.
* **[REQ-UI-003]** When a material is deleted from `Inventario General`, the frontend SHALL immediately remove it from all active grids, dropdowns, and transfer selectors, preventing any ghost records.

### 3. Flexible Field Mutation & Immutability Compliance
* **[REQ-UI-004]** The frontend SHALL allow administrators to edit the `STOCK ACTUAL` and `CÓDIGO (SKU)` fields directly within the `Modificar Material` form of `Inventario General`. This scope SHALL NOT extend to team or fiber optic inventories in this iteration.
* **[REQ-API-002]** When an API modification payload for a `Inventario General` material includes a change in the `STOCK ACTUAL` field, the backend SHALL calculate the numerical delta (New Stock − Old Stock) instead of performing a direct overwrite.
* **[REQ-API-003]** If the `STOCK ACTUAL` delta is non-zero, then the backend SHALL emit a counter-adjustment exclusively through the PostgreSQL stored function `fn_ajustar_stock_almacen` with a mandatory, non-empty `motivo`, and the database SHALL enforce non-negative stock at the constraint level, preserving historical immutability.

### 4. Category Persistence
* **[REQ-API-004]** When a user assigns or modifies a `Categoría`, the backend SHALL successfully persist this value in the PostgreSQL database.
* **[REQ-API-005]** The backend API SHALL include the `Categoría` field in the standard material JSON payload response.
* **[REQ-UI-005]** The frontend `Inventario General` table SHALL display the `Categoría` column to enable accurate user filtering.

### 5. Audit & Bulk Search Ergonomics
* **[REQ-UI-006]** The `Auditoría` view SHALL display and filter records using the `Descripción` parameter instead of the deprecated `ID Lista`.
* **[REQ-UI-007]** The `Buscador a granel` SHALL accept ranges "Desde número de lista a número de lista" and "Desde descripción a descripción" and render continuous 1-indexed list numbers from the backend `start_index` without downloading the full catalog.
* **[REQ-API-006]** Where the `Buscador a granel` requests a range by `número de lista`, the backend SHALL translate `desde_numero_lista` and `hasta_numero_lista` into deterministic ordinal positioning applying a stable secondary ordering (`ORDER BY descripcion ASC, id_lista ASC`), `OFFSET = X − 1` and `LIMIT = Y − X + 1`. The response SHALL include `start_index = X` so the frontend renders continuous list numbers.
* **[REQ-API-007]** The backend SHALL filter the `Buscador a granel` by `desde_descripcion` and `hasta_descripcion` using deterministic range ordering consistent with the ordering defined in REQ-API-006.
* **[REQ-API-008]** The `Auditoría` API SHALL resolve material names via a `LEFT JOIN` to the material catalog WITHOUT applying the `is_active` filter, guaranteeing that historical events remain fully readable with `descripcion`, `codigo`, and `categoria`. The response SHALL include an `estado_activo` flag so the frontend MAY render a discreet `[Inactivo]` label.
* **[REQ-API-009]** The TEAMS and DEVOL movement flows SHALL remain functionally identical after inventory isolation changes: existing contracts, stored functions, and regression tests SHALL NOT be altered or broken.

## Level B: Domain Evolution Requirements (Architecture)
*These requirements address fundamental changes in how the business conceptualizes inventory isolation across different operational departments.*

### 6. Team Autonomous Inventory (`Equipos`)
* **[REQ-DOMAIN-001]** The backend SHALL enforce strict inventory isolation for each `Equipo`: every team SHALL possess its own autonomous inventory structure (`inventario_equipos`), physically independent from the global `Inventario General` catalog.
* **[REQ-DOMAIN-002]** If a new `Equipo` is created, then the backend SHALL initialize an empty autonomous inventory for it, and it SHALL NOT inherit the global `Inventario General` catalog by default. The team inventory SHALL only register stock when physical stock is received via an audited TEAMS/DEVOL transfer, SHALL NOT render zero-stock or inactive ghost rows, and every entry SHALL trace back to its originating movement.

### 7. Fiber Optics Standardization (`Fibra Óptica`)
* **[REQ-DOMAIN-003]** The `Fibra Óptica` modules (`Paquete` and `En uso`) SHALL become independent inventory roots with the standard inventory schema constraints, ceasing to be sections of the central `Inventario General`.
* **[REQ-DOMAIN-004]** The frontend and backend SHALL represent `Fibra Óptica` assets using standard fields (`CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`) instead of the legacy "carretes en stock / metros disponibles" specific schema.
* **[REQ-DOMAIN-005]** The system SHALL determine the specific measurement metric of a `Fibra Óptica` asset exclusively via its `U.M.` (Unidad de Medida) field.
* **[REQ-DOMAIN-006]** The backend SHALL deprecate the legacy `fiber_variants` table (and any `carretes`/`metros` columns) and the `FO_PAQUETE`/`FO_EN_USO` section types, migrating their data into the new independent standard-schema inventories.
