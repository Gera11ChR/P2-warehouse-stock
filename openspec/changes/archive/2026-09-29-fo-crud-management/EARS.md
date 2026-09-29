# EARS Requirements Specification

## Domain: Autonomía CRUD en tablas FO
- **REQ-CRUD-001:** WHEN un operador selecciona una fila en la tabla "Fibra Óptica - Paquete" o "Fibra Óptica - En Uso", THE SYSTEM SHALL desplegar las acciones Ver Detalle, Modificar y Eliminar con modals equivalentes a los de la Sección General.
- **REQ-CRUD-002:** WHEN el operador elige Ver Detalle, THE SYSTEM SHALL mostrar la información del material (código, descripción, U.M., stock actual, stock mínimo y alerta) del módulo FO seleccionado sin habilitar edición accidental.

## Domain: Edición de parámetros del catálogo FO
- **REQ-CATFO-001:** WHEN el operador guarda el modal Modificar Material de una sección FO, THE SYSTEM SHALL actualizar Descripción, Código/SKU, Categoría, U.M. y Stock Mínimo mediante `PATCH /fibra/{modulo}/materiales/{material_id}` en una única transacción atómica.
- **REQ-CATFO-002:** IF el valor de U.M. enviado no existe en la tabla `ums` activa, THEN THE SYSTEM SHALL rechazar la operación con 422 determinístico (validación dinámica, sin Enum estático).

## Domain: Gestión manual de stock con auditoría
- **REQ-STOCK-001:** WHEN el operador modifica el campo STOCK ACTUAL en el modal de edición FO, THE SYSTEM SHALL exigir un motivo no vacío; IF el motivo está vacío, THEN THE SYSTEM SHALL rechazar la operación con 422 sin aplicar cambios.
- **REQ-STOCK-002:** WHEN un ajuste de STOCK ACTUAL FO es aceptado, THE SYSTEM SHALL calcular el diferencial (nuevo vs anterior) en PostgreSQL vía `fn_ajustar_stock_fibra` y registrar el evento de auditoría `AJUSTE_INVENTARIO_FO` (modulo, diferencial y motivo) — CERO aritmética de stock en Python.
- **REQ-STOCK-003:** THE SYSTEM SHALL preservar la atomicidad: la edición de catálogo y el ajuste de stock ocurren dentro del mismo `session.begin()`; si el ajuste falla, la edición del material también revierte.

## Domain: Eliminación de inventario FO por módulo
- **REQ-DEL-001:** WHEN el operador confirma Eliminar en una sección FO, THE SYSTEM SHALL eliminar únicamente la fila física de `inventario_fibra` correspondiente al módulo seleccionado vía `fn_eliminar_inventario_fibra`, auditando el evento `ELIMINACION_FO` cuyo `detalles` jsonb SHALL capturar el snapshot completo de la fila: `{modulo, material_id, stock_eliminado, motivo, usuario}` (Constitution 6.2: exact change context — el stock eliminado queda reconstruible en el ledger).
- **REQ-DEL-002:** IF la fila (modulo, material_id) no existe en `inventario_fibra`, THEN THE SYSTEM SHALL responder 404 sin efectos colaterales.
- **REQ-DEL-003:** THE SYSTEM SHALL mantener intactos `catalogo_materiales`, el inventario del otro módulo FO y el Inventario General al eliminar desde FO (aislamiento por módulo).
- **REQ-DEL-004:** IF la fila a eliminar tiene `stock_actual > 0`, THEN THE SYSTEM SHALL exigir un motivo no vacío (422 si está vacío, sin aplicar cambios); IF `stock_actual = 0`, el motivo es opcional. En ambos casos el evento `ELIMINACION_FO` registra el snapshot completo (REQ-DEL-001).

## Domain: Invariante transaccional de Transferencias
- **REQ-TRF-INV-001:** THE SYSTEM SHALL preservar íntegro el ruteo de transferencias: `fn_procesar_movimiento`, `fn_cancelar_movimiento` y la consulta de inventario de origen TEAMS / destino DEVOL no sufren cambios; los nuevos endpoints FO no alteran el inventario de fibra consumido por Transferencias.
- **REQ-TRF-INV-002:** WHEN una mutación CRUD FO (edición, ajuste o eliminación) se completa, THE SYSTEM SHALL invalidar la clave de caché `['fibra', modulo]` en el frontend para evitar stock obsoleto en la UI.
- **REQ-TRF-INV-003:** IF una fila de `inventario_fibra` eliminada recibe posteriormente una devolución DEVOL, THEN THE SYSTEM SHALL recrearla vía el UPSERT existente de `fn_procesar_movimiento` (comportamiento preexistente, sin cambios): la traza `ELIMINACION_FO` → `DEVOL_DEVOLUCION` hace la secuencia auditable y sin corrupción de stock.
