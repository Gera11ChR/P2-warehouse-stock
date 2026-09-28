# Implementation Tasks: 2026-09-28-equipos-despliegue-management

## Phase 1: Governance & Spec Sign-off
- [x] **1.1 Architecture Sign-off (`@arq-reviewer`)**: Verify that `proposal.md` and `EARS.md` align with system invariants (non-negative stock, immutable ledgers). — Governance work.
- [x] **1.2 Specification Audit (`@auditor`)**: Confirm zero specification drift between `dapp-context.md` and EARS requirements. — Governance work.

## Phase 2: Database & Security (BD & Schemas)
- [x] **2.1 Migration Design (`@dba-guard`)** — [REQ-CATALOG-001/002/003, REQ-TEAM-001/002/003/004, REQ-DEPLOY-001/002/003/004/005/006, REQ-FO-001/002]:
  - Create Alembic migration `0014` (down_revision `0013`).
  - Create table `ums` (`id`, `nombre` UNIQUE, `is_active`) seeded from `SUPPORTED_UNITS`.
  - Create table `equipo_material_config` (`equipo_id`, `material_id`, `stock_minimo_local` CHECK >= 0, `categoria_local_id` FK `categorias`, `um_local_id` FK `ums`, `updated_at`; PK `(equipo_id, material_id)`). Local parameters have an independent lifecycle from `inventario_equipos` stock rows (sparse model preserved).
  - Create table `despliegues` (`id`, `equipo_id` FK, `fecha`, `observaciones`, `usuario`, `estado` CHECK IN ('ABIERTA','CERRADA'), `created_at`, `updated_at`, `closed_at`; partial unique index `(equipo_id) WHERE estado='ABIERTA'`).
  - Create table `despliegue_items` (`id`, `despliegue_id` FK, `material_id` FK `catalogo_materiales.id_lista`, `cantidad_tomada` CHECK > 0, `cantidad_sobrante` CHECK 0..tomada, `cantidad_consumida` GENERATED STORED, UNIQUE `(despliegue_id, material_id)`).
  - Implement `fn_crear_despliegue` and `fn_cerrar_despliegue` (state machine, FOR UPDATE locks, stock math 100% in PostgreSQL, per-line audit events).
  - Extend `fn_procesar_movimiento` / `fn_cancelar_movimiento` additively with routing by `secciones.tipo` (GENERAL → `inventario_almacen`; FO_PAQUETE/FO_EN_USO → `inventario_fibra`).
  - Add audit triggers for `categorias` (modify/remove) and `equipo_material_config` (local parameter changes).
- [x] **2.2 Migration Execution (`@dba-guard`)**: Apply migration `0014` to development database `p2`. — Governance work.
- [x] **2.3 Security Review (`@sec-ops`)**: Verify RBAC scopes and header validations (`X-Actor`) for new tables and endpoints. — Governance work.

## Phase 3: Backend Implementation
- [x] **3.1 Catalog Endpoints (`@coder`)** — [REQ-CATALOG-001/002/003]:
  - Implement `PUT /api/v1/catalogo/categorias/{id}` and `DELETE /api/v1/catalogo/categorias/{id}` (soft-delete, admin-only, audited).
  - Implement `PUT /api/v1/catalogo/um/{id}` and `DELETE /api/v1/catalogo/um/{id}` (soft-delete, admin-only, audited).
- [x] **3.2 Transfer Multi-Warehouse Extension (`@coder`)** — [REQ-FO-001/002]:
  - Update movement processing to accept the FO sections (`FO_PAQUETE`, `FO_EN_USO`) as valid source/destination via `secciones.tipo` routing inside the stored functions; draft validation whitelists active sections by type.
- [x] **3.3 Team Local Parameters (`@coder`)** — [REQ-TEAM-001/002/003/004]:
  - Implement `PATCH /api/v1/equipos/{equipo_id}/inventario/{material_id}` for upserting `equipo_material_config` (only `stock_minimo_local`, `categoria_local_id`, `um_local_id`; `stock_actual`/`codigo`/`descripcion` rejected by schema).
  - Extend `GET /api/v1/equipos/{equipo_id}/inventario` with `COALESCE` local/master parameters.
- [x] **3.4 DESPLIEGUE Service (`@coder`)** — [REQ-DEPLOY-001/002/003/004/005/006]:
  - Implement `POST /api/v1/equipos/{equipo_id}/despliegues` (create deployment list) → `fn_crear_despliegue` (409 if an open deployment exists).
  - Implement `POST /api/v1/equipos/{equipo_id}/despliegues/{despliegue_id}/cerrar` (register remaining items, adjust team inventory) → `fn_cerrar_despliegue` (409 double-close, 400 invalid sobrantes).
  - Implement `GET /api/v1/equipos/{equipo_id}/despliegues` (team deployment list) for the report module.
- [x] **3.5 Operational Reporting Endpoint (`@coder`)** — [REQ-REPORT-001/002]:
  - Implement `GET /api/v1/reportes/despliegues` returning deployment movements with CSV format generator (`format=csv`, streamed, CSV-injection sanitized, team-scoped).
- [x] **3.6 Backend Compliance Audit (`@auditor`)**: Audit `@coder` implementation to guarantee inventory logic remains inside database transactions. — Governance work.

## Phase 4: Frontend Implementation & Testing
- [x] **4.1 UI Catalog Modals (`@ui-agent`, `@form-agent`)** — [REQ-CATALOG-001/002]:
  - Add "Modificar" and "Eliminar" display modals for Categories and Units of Measure in General Inventory.
- [x] **4.2 Transfer Warehouse Selector (`@ui-agent`, `@state-agent`)** — [REQ-FO-001]:
  - Add "Fibra Óptica - Paquete" and "Fibra Óptica - En Uso" to origin/destination dropdowns in Transfer view.
- [x] **4.3 Team Inventory Configuration & Safe View (`@ui-agent`, `@ux-agent`)** — [REQ-TEAM-001/002/003/004, REQ-VIEW-001]:
  - Build dedicated Read-Only consultation drawer/modal for team inventories (separate affordance from editing).
  - Build local parameter edit form (`stock_minimo_local`, `categoria_local_id`, `um_local_id`) preventing edit of code, description, or current stock.
- [x] **4.4 DESPLIEGUE Workflow UI (`@form-agent`, `@ux-agent`, `@state-agent`)** — [REQ-DEPLOY-001/002/003/004/005]:
  - Build interactive Deployment view per team for selecting materials, logging field quantities, capturing remaining stock, and concluding the session.
- [x] **4.5 Operational Reporting UI (`@ui-agent`, `@state-agent`)** — [REQ-REPORT-001/002]:
  - Refactor Reports view to show deployment activity and provide CSV export button.
- [x] **4.6 Integration Test Suite (`@tester`)** — All REQ-*:
  - Write Pytest integration tests mapped to `EARS.md` requirement IDs (incl. `test_despliegues.py`, `test_fo_transferencias.py`, `test_catalogo_admin.py`, `test_config_local.py`, `test_reportes.py`).
- [x] **4.7 Zero-Drift QA Audit (`@qa-agent`)**: Execute end-to-end audit verifying frontend consumption matches backend OpenAPI contract. — Governance work.

## Phase 5: Consolidation & Archive
- [x] **5.1 Final Integration (`@auditor`)**: Merge feature branch to `main`, run full regression test suite, and archive OpenSpec change set. — Governance work.
