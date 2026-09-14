# Tasks — manual-stock-and-transfer-fix

## 1. Backend: listado de almacenes

- [x] 1.1 Crear `backend/app/schemas/warehouse.py` con `WarehouseOut` (warehouse_id, name, is_active) y `WarehouseListOut` (warehouses)
- [x] 1.2 Crear `backend/app/api/v1/warehouses.py` con `GET /warehouses` (join `user_warehouse_scopes` → `warehouses` activos del actor) y registrar el router en `backend/app/main.py`
- [x] 1.3 Verificar que un actor sin scope recibe `{"warehouses": []}` sin error de autorización

## 2. Backend: ajuste manual de stock en PATCH /materials/{codigo}

- [x] 2.1 Añadir `on_hand_quantity: int | None (ge=0)` y `warehouse_id: str | None` a `MaterialUpdate` en `backend/app/schemas/material.py`
- [x] 2.2 Añadir `InventoryService.set_on_hand_quantity` en `backend/app/services/inventory.py`: lock de fila, 422 si no existe fila, `StockMovement(MANUAL_ADJUSTMENT)`, audit `STOCK_ADJUST_MANUAL` con old/new quantities, no-op si el valor no cambia
- [x] 2.3 En `backend/app/api/v1/materials.py` `update_material`: extraer `on_hand_quantity`/`warehouse_id` del loop de campos, `assert_scope` sobre el almacén destino (default `CENTRAL`) y llamar al servicio cuando aplique
- [x] 2.4 Verificar que PATCH sin `on_hand_quantity` mantiene el comportamiento actual (solo metadatos + `MATERIAL_UPDATE`)

## 3. Frontend: STOCK ACTUAL editable

- [x] 3.1 Añadir `on_hand_quantity?: number` y `warehouse_id?: string` a `MaterialPayload` en `frontend/src/services/materials.ts`
- [x] 3.2 En `frontend/src/components/MaterialForm.tsx`: input numérico editable en modo edición (estado local iniciado en `stockActual`), display solo-lectura en modo creación; nueva prop `almacenId`
- [x] 3.3 Incluir `on_hand_quantity`/`warehouse_id` en el payload solo en modo edición y solo si el valor cambió
- [x] 3.4 En `frontend/src/pages/SeccionGeneral.tsx` pasar `almacenId={selected.almacen_id}` a `MaterialForm`

## 4. Frontend: almacenes destino en Transferir Stock

- [x] 4.1 Crear `frontend/src/services/warehouses.ts` con `listWarehouses()` → `{ id, name, is_active }[]`
- [x] 4.2 En `SeccionGeneral.tsx` cargar almacenes desde el nuevo endpoint (reemplazar derivación desde `listInventory`)
- [x] 4.3 En `frontend/src/components/TransferDialog.tsx` filtrar destinos: `w.id !== material.almacen_id && w.is_active` y mapear a opciones
- [x] 4.4 Añadir `STOCK_ADJUST_MANUAL: 'Ajuste manual'` a `ACCIONES_AUDITORIA` en `frontend/src/types.ts`

## 5. Pruebas backend

- [x] 5.1 Crear `backend/tests/test_manual_stock_adjust.py`: PATCH actualiza `on_hand_quantity`; audit + `stock_movements` con old/new; default `CENTRAL`; 422 negativos/fila inexistente; 403 almacén sin scope; `GET /warehouses` scoped activos
- [x] 5.2 Ejecutar `pytest` completo sin regresiones

## 6. Pruebas frontend

- [x] 6.1 Añadir devDeps Vitest (`vitest`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`), script `test` y bloque `test` en `vite.config.ts`
- [x] 6.2 Crear `MaterialForm.test.tsx`: input editable en modo edición, payload con `on_hand_quantity`/`warehouse_id`, display solo-lectura en creación
- [x] 6.3 Crear `TransferDialog.test.tsx`: opciones excluyen origen e inactivos, incluyen otros activos
- [x] 6.4 Ejecutar `vitest run`, `npm run lint` y `npm run build` sin errores

## 7. Verificación final y archivo

- [x] 7.1 `openspec validate` del cambio
- [x] 7.2 Archivar el cambio con `openspec archive`
