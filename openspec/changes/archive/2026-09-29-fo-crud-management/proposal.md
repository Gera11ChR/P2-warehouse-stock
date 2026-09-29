# OpenSpec Change Proposal

## Change ID
`2026-09-29-fo-crud-management`

## Summary
Dotar a las secciones de Fibra Óptica ("Fibra Óptica - Paquete" y "Fibra
Óptica - En Uso") del mismo comportamiento CRUD flexible, autónomo e
independiente que posee el Inventario General (según `docs/fo_report.md`):

1. Las tablas de cada módulo FO permiten seleccionar un material y
   desplegar las acciones **Ver Detalle**, **Modificar** y **Eliminar**,
   con modals equivalentes a los de la Sección General.
2. El modal "Modificar Material" FO edita los campos de catálogo
   (Descripción, Código/SKU, Categoría, U.M., Stock Mínimo) y, si el
   operador altera el **STOCK ACTUAL**, exige un motivo obligatorio,
   calcula el diferencial en PostgreSQL y registra la transacción en el
   módulo de Auditoría mediante los endpoints/servicios de fibra.
3. INVARIANTE: los nuevos endpoints y modals no alteran el inventario de
   fibra ni el ruteo de transferencias (TEAMS/DEVOL); cada módulo FO
   conserva su aislamiento de datos sobre `inventario_fibra`.

## Business Problem
- **Tablas FO de solo lectura:** `GET /fibra/<modulo>` se consume en
  tablas sin interacción alguna; no es posible ver el detalle de un
  material, modificar sus propiedades de catálogo, ajustar su stock
  manualmente ni eliminarlo desde la propia sección.
- **Gestión de stock fragmentada:** el stock FO solo puede alterarse vía
  Transferencias o endpoints aislados (`/fibra/ajuste`,
  `/fibra/carga-inicial`), sin una experiencia integrada de edición con
  motivo obligatorio y auditoría trazable.
- **Falta de paridad operativa:** la Sección General dispone de CRUD
  completo (REQ-UI-004); las secciones FO carecen de esa paridad,
  obligando al operador a gestionar el catálogo desde otra pantalla.

## Proposed Changes
1. **Backend:** nuevo `PATCH /fibra/{modulo}/materiales/{material_id}`
   atómico que actualiza los campos de catálogo del material
   (`descripcion`, `codigo`, `categoria_id`/`nueva_categoria`, `u_m`,
   `stock_minimo`) y, si `stock_actual` viene en el payload, exige
   `motivo` no vacío (validator del schema) y enruta el ajuste a
   `fn_ajustar_stock_fibra` (diferencial, bloqueo FOR UPDATE y auditoría
   'AJUSTE_INVENTARIO_FO' en PostgreSQL) — espejo de
   `actualizar_material` de catalog.py, con atomicidad en un único
   `session.begin()`.
2. **Backend:** nuevo `DELETE /fibra/{modulo}/materiales/{material_id}`
   que elimina únicamente la fila física de `inventario_fibra` del módulo
   seleccionado vía la stored function    `fn_eliminar_inventario_fibra`
   (nueva; migración alembic 0015) con auditoría 'ELIMINACION_FO'
   (snapshot completo: modulo, material_id, stock_eliminado, motivo). NO
   toca `catalogo_materiales`, ni el stock del otro módulo FO, ni el
   Inventario General. Nota de semántica: una devolución DEVOL posterior
   recrea la fila vía el UPSERT preexistente de `fn_procesar_movimiento`
   (traza auditable ELIMINACION_FO → DEVOL_DEVOLUCION).
3. **Frontend:** `pages/FibraOptica.tsx` replica el patrón de
   SeccionGeneral: selección de fila, botones Ver Detalle / Modificar /
   Eliminar, `MaterialDetailDrawer`, modal con el nuevo
   `FibraMaterialForm` (edición de catálogo + STOCK ACTUAL con motivo
   obligatorio) y `ConfirmDialog` de eliminación. Invalidaciones de
   `['fibra', modulo]` tras cada mutación.
4. **Frontend:** `services/fibra.ts` añade `updateFibraMaterial()` y
   `eliminarFibraMaterial()`; tipos nuevos en `types.ts`.

## Impact Assessment
- **Backend:** `app/api/v1/fibra.py`, `app/schemas/inventario.py`,
  `app/services/transaccional.py` (invocación de la función de
  eliminación), `backend/db/ddl.sql` + migración alembic
  `0015_fo_crud_management`.
- **Frontend:** `pages/FibraOptica.tsx`, nuevo
  `components/FibraMaterialForm.tsx`, `services/fibra.ts`, `types.ts`
  (incluye etiqueta `ELIMINACION_FO` en `TIPOS_ACCION_AUDITORIA`).
- **Contrato:** `openspec/openspec.yaml` — registrar
  `PATCH/DELETE /api/v1/fibra/{modulo}/materiales/{material_id}` y añadir
  `fn_eliminar_inventario_fibra` + `fn_ajustar_stock_fibra` a
  `mandatory_functions`.
- **Tests:** `tests/test_fibra.py`, `tests/test_fo_transferencias.py`
  (regresión del invariante, incluye resurrección DEVOL post-eliminación),
  nuevo `frontend/src/components/__tests__/FibraOptica.test.tsx`.

## Out of Scope
- Botón "Agregar material" en las páginas FO (el alta sigue por Carga
  Inicial ruteada desde SeccionGeneral, REQ-CARGA-001/002).
- Cambios en la lógica transaccional TEAMS/DEVOL
  (`fn_procesar_movimiento` / `fn_cancelar_movimiento` permanecen
  intactos).
- Aritmética de stock en Python (prohibida por Constitution 2.4; todo
  diferencial vive en PostgreSQL).
- Eliminación global (soft-delete) del material del catálogo desde FO.
