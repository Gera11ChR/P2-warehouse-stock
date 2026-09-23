# Specification Document (EARS): Frontend-Backend Alignment & Domain Adjustments
**Document Status:** Approved for Implementation
**Source Proposal:** `proposal.md` (Based on user UI/UX feedback)

## Level A: Operational & Ergonomic Requirements (UI & API Contracts)
*These requirements address interface frictions, payload corrections, and identifier abstractions without fundamentally changing the core business models.*

### 1. Identifier Abstraction
* **[REQ-UI-001]** The frontend SHALL NOT display the `ID Lista` across any view, including Tables, Forms, `Auditoría` logs, or `Buscador a granel`.
* **[REQ-UI-002]** The frontend SHALL display a dynamic, 1-indexed sequential row number (`número de lista`) for all inventory data grids for display purposes only.

### 2. Absolute Deletion Handling
* **[REQ-API-001]** While a material is marked as deleted in the database, the backend API SHALL completely omit this record from all active operational endpoint responses.
* **[REQ-UI-003]** When a material is deleted from `Inventario General`, the frontend SHALL immediately remove it from all active grids, dropdowns, and transfer selectors, preventing any ghost records.

### 3. Flexible Field Mutation & Immutability Compliance
* **[REQ-UI-004]** The frontend SHALL allow administrators to edit the `STOCK ACTUAL` and `CÓDIGO (SKU)` fields directly within the `Modificar Material` form.
* **[REQ-API-002]** When an API modification payload includes a change in the `STOCK ACTUAL` field, the backend SHALL calculate the numerical delta instead of performing a direct overwrite.
* **[REQ-API-003]** If the `STOCK ACTUAL` delta is non-zero, then the backend SHALL automatically emit a counter-adjustment event to the `Auditoría` ledger to preserve historical immutability.

### 4. Category Persistence
* **[REQ-API-004]** When a user assigns or modifies a `Categoría`, the backend SHALL successfully persist this value in the PostgreSQL database.
* **[REQ-API-005]** The backend API SHALL include the `Categoría` field in the standard material JSON payload response.
* **[REQ-UI-005]** The frontend `Inventario General` table SHALL display the `Categoría` column to enable accurate user filtering.

### 5. Audit & Bulk Search Ergonomics
* **[REQ-UI-006]** The `Auditoría` view SHALL display and filter records using the `Descripción` parameter instead of the deprecated `ID Lista`.
* **[REQ-UI-007]** The `Buscador a granel` SHALL filter ranges using "Desde número de lista a número de lista" and "Desde descripción a descripción" input parameters.


## Level B: Domain Evolution Requirements (Architecture)
*These requirements address fundamental changes in how the business conceptualizes inventory isolation across different operational departments.*

### 6. Team Catalog Isolation (`Equipos`)
* **[REQ-DOMAIN-001]** The backend SHALL enforce strict catalog isolation for each created `Equipo`.
* **[REQ-DOMAIN-002]** If a new `Equipo` is created, then it SHALL possess an independent, empty inventory catalog and SHALL NOT inherit the global `Inventario General` catalog by default.

### 7. Fiber Optics Standardization (`Fibra Óptica`)
* **[REQ-DOMAIN-003]** The `Fibra Óptica` modules (`Paquete` and `En uso`) SHALL adopt the standard inventory schema constraints.
* **[REQ-DOMAIN-004]** The frontend and backend SHALL represent `Fibra Óptica` assets using standard fields (`CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`) instead of the legacy "carretes en stock / metros disponibles" specific schema.
* **[REQ-DOMAIN-005]** The system SHALL determine the specific measurement metric of a `Fibra Óptica` asset exclusively via its `U.M.` (Unidad de Medida) field.

