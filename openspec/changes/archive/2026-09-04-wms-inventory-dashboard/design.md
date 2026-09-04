# Design: WMS Inventory Dashboard

## Context

The backend already implements the domain model and transfer surface (specs 001/002): FastAPI + async SQLAlchemy + PostgreSQL, models `Sku` (`sku`, `description`, `unit_of_measure`, `min_stock`), `Warehouse`, `WarehouseInventory` (`on_hand_quantity`, DB-enforced non-negative), `StockTransfer`/`TransferLineItem`/`StockMovement` (append-only ledger), `AuditLog`, `Vehicle`/`FleetAllocation`, and `UserWarehouseScope`. Actor context comes from the `X-Actor` header via `security.get_current_actor`, scoped to warehouse IDs; there is no login/session layer.

The frontend is a Vite + React + Tailwind v4 (`@tailwindcss/vite`) starter with `axios`, `lucide-react`, and `recharts` already installed, and a dev proxy `/api` → `http://localhost:8000`. No `pages/`/`components/`/`services/`/`hooks/`/`layouts/` exist yet.

Motivation and full scope are in proposal.md; requirements are in specs/003_inventory_dashboard/spec.md.

## Goals / Non-Goals

**Goals:**
- A usable Spanish-language WMS operator surface over the existing per-warehouse inventory model, with no writable global stock column (preserves spec 002).
- New persistable concepts: fiber-optic variants/remaining-meters and team inventory assignments.
- Material CRUD + per-(SKU+Almacén) inventory query + KPI aggregation, all behind the existing actor/scope machinery.

**Non-Goals:**
- Authentication/login, session management, and full RBAC UI — a fixed demo `X-Actor` is used.
- Changing the transfer lifecycle, ledger, or MFA logic (spec 002 is untouched).
- "Reportes" content beyond a stub page (Auditoría gets a real audit-log table).
- Renaming existing shipped English DB columns (see Decisions).

## Decisions

### 1. Spanish terminology at the contract boundary, preserve existing DB columns
New DTOs and API responses use Spanish field names (`codigo`, `descripcion`, `um`, `stock_actual`, `stock_minimo`, `alerta_stock`, `almacen`, `categoria`, `variante`, `metros_restantes`, `equipo`, `usuario`, `cantidad`, `ultima_modificacion`). New DB tables use Spanish column names. Existing `Sku`/`Warehouse`/`WarehouseInventory`/`StockTransfer` columns stay as-is (English) to avoid breaking the shipped transfer surface and its FKs — a service-layer mapping translates English columns to Spanish DTO fields.

*Alternatives considered:* fully renaming existing DB columns (`description`→`descripcion`, etc.) — rejected because it is a destructive migration that breaks spec 002's tested FK references and migrations, conflicting with the Priority-1 "data model consistency" for the shipped system. English-column-vs-Spanish-DTO mapping is the narrowest way to satisfy "no mixed English/Spanish in the UI/API" while keeping the existing model intact.

### 2. Extend `Sku`; do not add a writable stock column
Add `categoria: String(100)` and `tipo: String(20)` (`GENERAL` | `FIBRA`) to `skus`, and widen `unit_of_measure` from `String(20)` to `String(50)` (units like `CARRETE (1 KM)` exceed 20 chars). `STOCK ACTUAL` and `ALERTA STOCK` remain derived: on-hand from `warehouse_inventory`, alert from `on_hand <= min_stock`. No client-writable stock field (spec 002 REQ-STOCK-002).

*Alternatives considered:* adding `current_stock`/`alerta` columns — rejected; violates the derived-aggregate invariant and would drift from the ledger.

### 3. New models `FiberVariant` and `TeamInventory`
- `fiber_variants`: `id` (PK), `sku` FK→`skus.sku`, `variante` String(100), `metros_restantes` Integer, `cantidad` Integer, `warehouse_id` FK→`warehouses.warehouse_id` (nullable). Powers the "En Uso" view (CÓDIGO, DESCRIPCIÓN, VARIANTE, METROS RESTANTES, STOCK ACTUAL where STOCK ACTUAL = `cantidad`).
- `team_inventory`: `id` (PK), `equipo` String(100), `usuario` String(100), `sku` FK→`skus.sku`, `cantidad` Integer, `ultima_modificacion` DateTime (server default `now()`, refreshed on update). `Descripción` is **derived** (joined from `skus.description`), not stored — the frontend auto-fills it from the SKU (REQ-TEAM-002).

*Alternatives considered:* storing a denormalized `descripcion` on `team_inventory` — rejected; it can drift from the SKU catalog and violates single-source-of-truth.

### 4. New API routers under `/api/v1`
- `materials` (`/materials`): SKU CRUD (create/read/update/delete) with Spanish DTOs; create/update validate `um` against the supported-units vocabulary and validate SKU format.
- `inventory` (`/inventory`): list one row per (SKU+Almacén), joining `skus` + `warehouse_inventory` + `warehouses`, with derived `stock_actual` and `alerta_stock`; supports `buscar`, `categoria`, `um`, `almacen` filters and a `desde_sku`/`hasta_sku` range.
- `team-inventory` (`/team-inventory`): CRUD; server sets `ultima_modificacion` on every mutation.
- `fiber-optics` (`/fiber-optics`): list/create variants with `metros_restantes`.
- `kpis` (`/kpis`): returns four aggregates — Total Materiales (distinct SKUs), Stock Total (SUM on-hand), Alertas Stock (rows where `on_hand <= min_stock`), Transferencias Hoy (transfers with `created_at::date = today`).
- All read/write endpoints depend on `get_current_actor` (demo `X-Actor`); `inventory`/`materials` reads are not scope-restricted (catalog is global) while `team-inventory`/`fiber-optics` writes assert scope where they reference a warehouse. CRUD mutations write an `AuditLog` row (Constitution 6.2) and a `StockMovement` row where balances change.

*Alternatives considered:* one monolithic `/dashboard` endpoint — rejected; separate routers keep contracts testable and match the existing `/stock-transfers` organization.

### 5. Frontend structure and field-order enforcement
New `src/` layout: `layouts/MainLayout.tsx` (three columns), `components/` (Sidebar, Header, KpiCards, FilterToolbar, InventoryTable, MaterialDetailDrawer, Tabs, Toast, ConfirmDialog, forms), `pages/` (SecciónGeneral, FibraOptica/Paquete, FibraOptica/EnUso, InventarioPorEquipos, Transferencias, Reportes, Auditoría), `services/` (axios client + per-resource modules), `hooks/` (query/mutation hooks). The mandatory field order (DESCRIPCIÓN → STOCK ACTUAL → STOCK MÍNIMO → ALERTA STOCK → U.M. → CÓDIGO) is defined once as a single ordered field descriptor consumed by the drawer, CRUD form, view modal, transfer dialog, and edit screen, so the sequence cannot drift between surfaces (REQ-DASH-008).

*Alternatives considered:* relying on component library defaults — rejected; ordering is a Priority-1 requirement and must be explicit.

### 6. Seed routine
`backend/app/seed.py` is idempotent (upsert by SKU) and loads 53 general + 5 fiber materials with the supported units, creating the warehouses and initial `warehouse_inventory` rows. Initial balances are written as `RECEIPT` `stock_movements` so the append-only ledger invariant (REQ-STOCK-003) holds from the first row; re-runs skip existing SKUs.

## Risks / Trade-offs

- **[Spanish DTO vs English DB columns] drift risk** → Mitigation: a single, tested mapping module per resource; `openspec validate --strict` and contract tests lock the DTO field names.
- **[Widening `unit_of_measure`] existing data truncation** → Mitigation: expand/contract migration only widens (no data loss); seed uses the full vocabulary.
- **[No auth] demo `X-Actor` is spoofable** → Mitigation: documented as dev-only; production auth is an explicit non-goal and a future change.
- **[Derived stock vs CRUD "Stock Actual" field]** the CRUD form lists STOCK ACTUAL as read-only, which could confuse operators → Mitigation: the field is rendered disabled/derived with a clear read-only affordance.
- **[KPI "Transferencias Hoy" timezone]** `created_at::date` depends on server TZ → Mitigation: compute in the API using the DB session's `CURRENT_DATE` so it is consistent.

## Migration Plan

- Add `categoria`/`tipo` columns and widen `unit_of_measure` via an expand-only migration (no destructive change).
- Create `fiber_variants` and `team_inventory` tables.
- Deploy backend routers, then run `seed.py` (idempotent) to populate.
- Build the frontend against the `/api` proxy; rollback is additive-only (drop new tables/columns) with no effect on the existing transfer data.

## Open Questions

None — all decisions that affect specs or task breakdown are resolved above.
