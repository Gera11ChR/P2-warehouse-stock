# Proposal: WMS Inventory Dashboard [REQ-DASH-001..999 / REQ-FIBER / REQ-TEAM / REQ-MAT]

## Why

The backend implements the core logistics (spec 001) and inter-site transfer (spec 002) domains, but there is no operator-facing surface to view or manage material — the frontend is still the Vite starter scaffold and no material CRUD, inventory query, team inventory, or seed data exists. Operators cannot browse stock, act on alerts, assign material to field teams, or track fiber-optic spools, so the platform is not usable as a warehouse management system.

## What Changes

- New React + Tailwind frontend replacing the starter scaffold: three-column enterprise WMS layout (dark sidebar, light inventory workspace, white material-detail drawer), KPI dashboard, filter toolbar, and per-module inventory tables.
- New backend domain models: `Sku.categoría`/`Sku.tipo` (classification + filter), `FiberVariant` (variant + `metros_restantes` for fiber-optic spools), and `TeamInventory` (equipo/usuario/SKU/cantidad with auto `updated_at`).
- New API surface under `/api/v1`: `/materials` (SKU CRUD), `/inventory` (one row per SKU+Almacén, derived stock + alert flag), `/team-inventory` (CRUD with SKU→description autofill), `/fiber-optics` (variant + remaining meters), and `/kpis` (four aggregate cards).
- New `backend/app/seed.py` seeding 53 general materials + 5 fiber-optic materials across the supported units.
- Strict Spanish domain language across all labels, schemas, DTOs, API responses, and components.
- Mandatory field ordering (DESCRIPCIÓN, STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK, U.M., CÓDIGO) enforced in the drawer, CRUD forms, view modals, transfer dialogs, and edit screens.
- Frontend auth via the existing development/demo `X-Actor` header (reusing `security.get_current_actor`); full login/session flow is out of scope for this change.

## Capabilities

### New Capabilities
- `003_inventory_dashboard`: enterprise WMS operator surface — layout and navigation, KPI dashboard, filter toolbar, per-(SKU+Almacén) inventory table, material detail drawer, bulk search, fiber-optic module (Paquete/En Uso with metros restantes), team inventory assignment, Spanish naming, mandatory field ordering, and success feedback toasts. Also covers the material CRUD, inventory query, team inventory, fiber-optic, and KPI API contracts and the seed data set.

### Modified Capabilities
<!-- None. The Sku classification fields and CRUD behavior are additive (no existing
     001_core_logistics requirement changes); they are specified as ADDED requirements
     under 003_inventory_dashboard. -->

## Impact

- **Data model**: `Sku` columns `categoría` + `tipo` added and `unit_of_measure` widened; new `fiber_variants` and `team_inventory` tables; derived `STOCK ACTUAL` / `ALERTA STOCK` remain aggregates (no writable stock column — preserves spec 002).
- **Backend**: new routers (`materials`, `inventory`, `team-inventory`, `fiber-optics`, `kpis`) registered in `app/main.py`; new schemas; `seed.py` idempotent seeding.
- **Frontend**: full `src/` restructure into `layouts/`, `pages/`, `components/`, `services/`, `hooks/`; axios client proxied to `/api`.
- **Auth**: new endpoints read the existing demo `X-Actor` header through the existing actor/scope machinery; MFA and scope enforcement unchanged.
- **Verification**: `openspec validate --specs --strict`, backend tests for CRUD/seed/idempotency, frontend build with zero type errors and warnings (Constitution 7.2).
