## 1. Data Model & Migrations

- [x] 1.1 Extend `Sku` with `categoria` (String(100)) and `tipo` (String(20)) columns and widen `unit_of_measure` to String(50); verify the expand-only migration applies cleanly and the new columns exist
- [x] 1.2 Add `FiberVariant` model (`fiber_variants`: id, sku FK, variante, metros_restantes, cantidad, warehouse_id FK) and create its table; verify the table is created with the expected columns
- [x] 1.3 Add `TeamInventory` model (`team_inventory`: id, equipo, usuario, sku FK, cantidad, ultima_modificacion with server default now()); verify the table is created
- [x] 1.4 Register new models in `app/models/__init__.py` and verify `from app.models import FiberVariant, TeamInventory` resolves

## 2. Schemas (DTOs)

- [x] 2.1 Add Spanish material DTOs (`MaterialCreate`/`MaterialUpdate`/`MaterialOut` with `codigo`, `descripcion`, `um`, `stock_minimo`, `categoria`, `tipo`); verify Pydantic validation accepts the supported units and rejects unknown ones
- [x] 2.2 Add inventory DTOs (`InventoryRowOut` with `codigo`, `descripcion`, `um`, `stock_actual`, `stock_minimo`, `alerta_stock`, `almacen`, `categoria`) and filter/range query params; verify serialization maps English columns to Spanish fields
- [x] 2.3 Add team inventory DTOs (`TeamInventoryCreate`/`TeamInventoryOut` with `equipo`, `usuario`, `codigo`, `descripcion` (derived), `cantidad`, `ultima_modificacion`); verify `descripcion` is populated from the SKU join
- [x] 2.4 Add fiber DTOs (`FiberVariantCreate`/`FiberVariantOut` with `codigo`, `descripcion`, `variante`, `metros_restantes`, `stock_actual`); verify serialization
- [x] 2.5 Add KPI DTO (`KpisOut` with `total_materiales`, `stock_total`, `alertas_stock`, `transferencias_hoy`); verify field types

## 3. API Routers

- [x] 3.1 Implement `/api/v1/materials` CRUD (create/read/update/delete) with Spanish DTOs, unit-vocabulary validation, and an `AuditLog` write per mutation; verify a create→read→update→delete round-trip via a test
- [x] 3.2 Implement `/api/v1/inventory` returning one row per (SKU+Almacén) with derived `stock_actual` and `alerta_stock`, plus `buscar`/`categoria`/`um`/`almacen` filters and `desde_sku`/`hasta_sku` range; verify a query returns rows grouped by warehouse
- [x] 3.3 Implement `/api/v1/team-inventory` CRUD where the server sets `ultima_modificacion` on every mutation; verify the timestamp updates after an update
- [x] 3.4 Implement `/api/v1/fiber-optics` list/create with `metros_restantes`; verify a variant round-trip preserves remaining meters
- [x] 3.5 Implement `/api/v1/kpis` returning the four aggregates (distinct SKU count, SUM on-hand, alert count, transfers created today); verify against seeded data
- [x] 3.6 Register all new routers in `app/main.py` and verify each route is reachable via `/docs`

## 4. Seed Data

- [x] 4.1 Implement `backend/app/seed.py` loading 53 general + 5 fiber materials, warehouses, and initial `warehouse_inventory` rows using the supported units (PZ, LT, CARRETE (1 KM), METRO (M), CARRETE (5 KM), BOLSA (500 PZ), PAQUETE (100 PZ), ROLLO, EQUIPO, UNIDAD); verify counts after running
- [x] 4.2 Write initial balances as `RECEIPT` `stock_movements` and make seeding idempotent (skip existing SKUs); verify a second run adds no duplicates

## 5. Frontend Foundation

- [x] 5.1 Create `services/` axios client (baseURL `/api`, sends demo `X-Actor` header) and per-resource service modules; verify the client is configured against the vite `/api` proxy
- [x] 5.2 Create `layouts/MainLayout.tsx` implementing the three-column layout (dark sidebar, light workspace, white drawer); verify the layout renders all three regions
- [x] 5.3 Create `Sidebar` (nav hierarchy: Sección General, Fibra Óptica→Paquete/En Uso, Inventario por Equipos, Transferencias, Reportes, Auditoría) and `Header` (breadcrumbs + global search with placeholder and Ctrl+K badge); verify navigation and search render

## 6. Dashboard Components

- [x] 6.1 Create `KpiCards` rendering the four cards (Total Materiales blue, Stock Total green, Alertas Stock amber, Transferencias Hoy purple) above tables; verify against `/kpis`
- [x] 6.2 Create `FilterToolbar` (Buscar, Categoría, U.M., Almacén) and action buttons (+ Agregar green, Modificar yellow, Eliminar red, Transferir Stock blue); verify controls and colors render
- [x] 6.3 Create `InventoryTable` for Sección General with columns CÓDIGO/DESCRIPCIÓN/U.M./STOCK ACTUAL/STOCK MÍNIMO/ALERTA STOCK/ALMACÉN and stock color coding (green/amber/red); verify row-per-warehouse and colors
- [x] 6.4 Create `MaterialDetailDrawer` (close button, mandatory field order DESCRIPCIÓN→STOCK ACTUAL→STOCK MÍNIMO→ALERTA STOCK→U.M.→CÓDIGO, footer Modificar/Eliminar/Transferir Stock, blue METROS RESTANTES card for fiber En Uso); verify field order and fiber card
- [x] 6.5 Create the bottom tabbed section ("1 Buscador" browse/pagination, "2 Buscador a granel" with Desde SKU/Hasta SKU range table); verify range search returns filtered rows
- [x] 6.6 Create a green bottom-right toast system and wire it to transfer/material create/modify/delete success events; verify toasts appear on success

## 7. Modules & Pages

- [x] 7.1 Build `SecciónGeneral` page composing KPI cards, filter toolbar, inventory table, tabs, and drawer; verify the full Sección General workflow
- [x] 7.2 Build `FibraOptica` pages (Paquete and En Uso) where En Uso shows CÓDIGO/DESCRIPCIÓN/VARIANTE/METROS RESTANTES/STOCK ACTUAL; verify remaining meters is present and not replaced by stock count
- [x] 7.3 Build `InventarioPorEquipos` page (Equipo/Usuario/Código SKU/Descripción/Cantidad/Última Modificación) with SKU→descripción auto-fill and auto timestamp; verify auto-fill and timestamp behavior
- [x] 7.4 Build `Transferencias` page against the existing `/stock-transfers` API (list/detail); verify transfers render
- [x] 7.5 Build `Reportes` stub page and `Auditoría` page rendering the audit-log table; verify both nav entries load

## 8. Verification

- [x] 8.1 Run the backend test suite and verify all tests pass (100% per Constitution 7.2)
- [x] 8.2 Run `npm run build` in `frontend/` and verify zero type errors and zero build warnings
- [x] 8.3 Run `openspec validate --specs --strict` and verify zero schema violations
