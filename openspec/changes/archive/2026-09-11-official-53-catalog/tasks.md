## 1. Modelo de Datos

- [x] 1.1 Crear migración Alembic `0009_official_catalog.py` con `add_column skus.is_active (Boolean, nullable=False, server_default=true)` expand-only y verificar `alembic upgrade head` aplica limpio en dev y `p2_test`
- [x] 1.2 Añadir `is_active` al modelo `Sku` en `backend/app/models/sku.py` y verificar `from app.models import Sku` resuelve con el nuevo campo

## 2. Seed Oficial Idempotente

- [x] 2.1 Reescribir `backend/app/seed.py` con `OFFICIAL_CATALOG` de los 53 ítems exactos (sku, descripción, categoría de los 5 módulos, unidad del vocabulario soportado, tipo FIBRA/GENERAL, stock 0, min_stock 0) y verificar que el módulo importa sin errores
- [x] 2.2 Implementar upsert de los 53 SKUs (reactivar `is_active=True` y actualizar campos si existen) y verificar contra una base con SKUs preexistentes que no falla
- [x] 2.3 Implementar barrido de desactivación (`is_active=False` para SKUs no oficiales con historial) sin DELETE físico y verificar que ningún FK queda huérfana
- [x] 2.4 Crear `warehouse_inventory` (on_hand=0) solo para SKUs nuevos en CENTRAL, sin movimientos RECEIPT de cantidad 0, y verificar conteos tras ejecutar

## 3. API de Catálogo

- [x] 3.1 Filtrar `GET /materials` por `is_active=True` y verificar que los SKUs demo desaparecen del listado
- [x] 3.2 Hacer que `GET/PATCH /materials/{codigo}` traten los inactivos como "Material no encontrado" (422) y verificar con un SKU desactivado
- [x] 3.3 Cambiar `DELETE /materials/{codigo}` a soft-delete (`is_active=False` + evento `MATERIAL_DELETE`) y verificar que la fila persiste y deja de listarse
- [x] 3.4 Filtrar `GET /inventory` por SKU activo y verificar que devuelve exactamente las 53 filas oficiales (una por SKU en CENTRAL)
- [x] 3.5 Filtrar `GET /kpis` (total_materiales, stock_total, alertas_stock) por SKU activo y verificar que `total_materiales` = 53 tras el seed
- [x] 3.6 Filtrar `GET /fiber-optics` por SKU activo (join) y verificar que variantes de SKUs inactivos no se listan

## 4. Pruebas

- [x] 4.1 Crear `backend/tests/test_official_catalog.py`: 53 activos exactos iguales a la lista oficial, `CF-*` con `tipo=FIBRA`, demo inactivos, seed ×2 idempotente, historiales no decrecientes, soft-delete del API; verificar que pasa
- [x] 4.2 Actualizar `test_inventory_dashboard.py::test_material_delete_blocked_with_stock` al contrato de soft-delete (204 y fila inactiva) y verificar que la suite completa pasa al 100 %

## 5. Verificación Final (Constitution 7.2)

- [x] 5.1 Ejecutar `python -m app.seed` dos veces en dev y verificar 53 activos exactos, sin duplicados ni errores
- [x] 5.2 Verificar vía SQL que `stock_transfers`, `transfer_line_items`, `audit_logs` y `stock_movements` no decrecen y que no existen FKs huérfanas
- [x] 5.3 Ejecutar `pytest` al 100 %, `npm run build` sin errores ni warnings y `openspec validate --specs --strict` con 0 violaciones
- [x] 5.4 Actualizar README (catálogo oficial de 53: 48 generales + 5 fibra) y verificar coherencia del texto
