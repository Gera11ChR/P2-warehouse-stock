# Proposal: Catálogo Oficial de 53 SKUs y Consolidación de Custodia en CENTRAL

## Why

El catálogo actual contiene 58 materiales demo (53 generales + 5 fibra) con códigos inventados (`CBL-FO-001`, `FO-MONO-001`…), mientras que la operación real exige el catálogo oficial de 53 ítems definido en la plantilla DMS (`data/1 FORMATO BASE ALMACENAMIENTO DMS.xlsm`) con estructura de SKU normalizada `[PREFIJO]-[VARIANTE/MEDIDA]-[SUFIJO_OPCIONAL]`. La especificación activa `REQ-MAT-003` exige 58 materiales, por lo que debe enmendarse antes de tocar código (Constitution 1.1/1.3).

## What Changes

- Nuevo catálogo oficial de **53 SKUs exactos**: 5 de fibra óptica (`CF-*`, tipo `FIBRA`) + 48 generales (herrajes/soporte, conectividad y consumibles, splitters desbalanceados y splitters PLC, tipo `GENERAL`), con descripciones, unidades y categorías alineadas a la plantilla DMS.
- **Desactivación no destructiva** (soft-delete) de los 58 SKUs demo que poseen historial (FK `RESTRICT` en `stock_movements`, `warehouse_inventory`, `transfer_line_items`): se marcan `is_active = false`; nunca se eliminan físicamente.
- Nueva columna `skus.is_active` (migración expand-only) y filtrado por SKU activo en las superficies de catálogo (`/materials`, `/inventory`, `/kpis`, `/fiber-optics`).
- `DELETE /materials` pasa a **soft-delete** (`is_active = false`) en lugar de borrado físico, preservando la integridad referencial y el ledger inmutable.
- `seed.py` reescrito como proceso **estrictamente idempotente**: upsert de los 53 SKUs oficiales (reactivándolos si existieran), desactivación de los no oficiales, stock inicial 0 en `CENTRAL` (fiel a la plantilla DMS: STOCK ACTUAL 0 / STOCK MÍNIMO 0 / "SIN STOCK"), sin movimientos RECEIPT ficticios.
- **Consolidación de custodia en `CENTRAL`**: todo el stock del catálogo oficial se siembra en `CENTRAL`; el esquema multi-almacén (NORTE/SUR) y las transferencias inter-sitio existentes se preservan intactos.
- **BREAKING** (alcance acotado): `DELETE /materials` ya no elimina filas físicamente; materiales desactivados dejan de aparecer en listados, búsquedas y KPIs.

## Capabilities

### New Capabilities

<!-- Ninguna. La gobernanza del catálogo se especifica como requisitos ADDED dentro de
     003_inventory_dashboard, que ya cubre el contrato de materiales/inventario/seed. -->

### Modified Capabilities

- `003_inventory_dashboard`: `REQ-MAT-003` cambia a un catálogo oficial de 53 SKUs exactos (48 generales + 5 fibra) con seed idempotente y desactivación segura; `REQ-MAT-001` cambia DELETE a desactivación lógica; se añaden requisitos de gobernanza de catálogo (`REQ-CAT-*`) para visibilidad solo-activos, soft-delete y custodia CENTRAL preservando multi-almacén.

## Impact

- **Datos**: migración Alembic `0009` (add column `skus.is_active`, expand-only, no destructiva); filas demo conservadas con historial intacto.
- **Backend**: `app/seed.py` reescrito; filtros `is_active` en `api/v1/materials.py`, `api/v1/inventory.py`, `api/v1/kpis.py`, `api/v1/fiber_optics.py`; soft-delete en `DELETE /materials`.
- **Frontend**: sin cambios estructurales; la tabla principal pasa a mostrar exactamente las 53 filas activas (53 SKUs × CENTRAL) y la búsqueda por código resuelve cualquier SKU oficial.
- **Pruebas**: nuevo `test_official_catalog.py`; ajuste de `test_inventory_dashboard.py` para el nuevo contrato de soft-delete. Sin cambios en RBAC, `user_warehouse_scopes`, autenticación, `stock-transfers` ni historiales.
- **Verificación**: `pytest` 100 %, `npm run build` sin errores/warnings, `openspec validate --specs --strict` (Constitution 7.2).
