# Plan técnico (Backend-First): Transferencias multi-origen

**Change ID:** `2026-10-12-transferencias-multi-origen` · **Spec:** `spec.md` (RF-1..RF-18)

## 1. Impacto constitucional

§2.1 (no negativo) y §4.1 (atomicidad) se conservan en PL/pgSQL. §2.3: orden de bloqueo (origen, material). §2.4: no se tocan `auditoria_eventos` ni `actas_reportes` históricas; el backfill solo rellena una columna nueva de `movimientos_detalle`. §3.1/§3.2: scope por cada origen. Sin enmienda constitucional.

## 2. Migración `0026_transferencias_multi_origen` (`down_revision = "0025"`)

`upgrade()`:
1. `ADD COLUMN movimientos_detalle.origen_almacen_id INT NULL` con FK `secciones(almacen_id) ON DELETE RESTRICT` e índice.
2. Backfill: `UPDATE movimientos_detalle d SET origen_almacen_id = c.origen_almacen_id FROM movimientos_cabecera c WHERE d.movimiento_id = c.id AND c.tipo_movimiento = 'TEAMS'`.
3. Relajar `ck_movimientos_cabecera_extremos`: TEAMS exige solo `destino_equipo_id`; DEVOL igual que hoy.
4. `CREATE OR REPLACE` de `fn_procesar_movimiento(INT)`, `fn_cancelar_movimiento(INT, TEXT)` y `fn_generar_acta_entrega()` (firmas idénticas).

`downgrade()`: aborta con mensaje claro si existe un movimiento con cabecera TEAMS `NULL` (mixto); si no, restaura las 3 funciones (cuerpos de 0025 verbatim), el CHECK y elimina la columna. Verificación: upgrade → downgrade → upgrade con md5 de las funciones y conteos del backfill.

## 3. PL/pgSQL

- `fn_procesar_movimiento`: bucle sobre el detalle `ORDER BY origen efectivo, material_id`. Origen de la línea = `COALESCE(md.origen_almacen_id, cabecera.origen_almacen_id)`; si es NULL → `RAISE 'La línea del material ID LISTA % no tiene sección de origen.'`. El tipo de sección se resuelve POR LÍNEA (GENERAL → `inventario_almacen`; FO_* → `inventario_fibra` por módulo) con `FOR UPDATE` y los mismos textos "Stock insuficiente en Origen (Sección ID % / Módulo FO %)". Auditoría por línea con su `almacen_origen_id` (+ `modulo_fo`). DEVOL sin cambios.
- `fn_cancelar_movimiento`: la restitución usa el origen de la línea (misma resolución).
- `fn_generar_acta_entrega`: `items[].origen {almacen_id, nombre, tipo}` y `origenes` (arreglo distinto); `origen` = el de cabecera o JSON null si es mixto; el evento `ACTA_ENTREGA_GENERADA` usa `NEW.origen_almacen_id` (puede ser NULL) y añade `origen_almacen_ids`.

## 4. FastAPI / Pydantic v2 (solo `backend/app`)

- `schemas/movimiento.py`: `DetalleLine += origen_almacen_id: int | None (gt=0)`; `DetalleOut += origen_almacen_id`; en TEAMS cada línea debe resolver origen (línea o cabecera); en DEVOL el origen por línea es 422; `extra="forbid"` intacto.
- `models/movimiento.py`: `MovimientoDetalle.origen_almacen_id` y CHECK de cabecera actualizado.
- `services/movimientos.py`: valida cada origen distinto (existencia, GENERAL activa, FO permitido) y aplica `assert_scope` sobre el CONJUNTO de orígenes; persiste origen por línea; cabecera = común o NULL; `actualizar_borrador` recalcula igual.
- `schemas/reporte.py` y `services/reportes.py`: `ActaItemOut += origen_almacen_id / origen_nombre` (aditivo).
- `openspec/openspec.yaml`: `DetalleLine` y `MovimientoOut`. `/movimientos/procesar` sin cambios. Cero aritmética de stock en Python.

## 5. Tests backend (`REQ-TRFM-NNN`)

Nuevo `tests/test_transferencias_multi_origen.py` (borrador mixto, homogéneo, payload legado, procesar mixto, rollback total, 403 por scope, 422, auditoría por línea, acta única, cancelación, concurrencia en orden inverso, migración con backfill en BD aparte, OpenAPI). Ajustar tests que asumen origen solo en cabecera.

## 6. Frontend (bloqueado hasta T10; solo `frontend/src`)

- Sin `TransferenciasContext`; el carrito sigue local.
- `types.ts` / `services/movimientos.ts`: `CartLine.origen_almacen_id`, detalle con origen, payload TEAMS con origen por línea.
- `pages/Transferencias.tsx`: el selector pasa a "Consultar origen"; agregar copia la sección activa a la línea; el carrito NO se vacía al cambiar de sección; saldo proyectado por línea; payload con origen por línea y sin origen de cabecera.
- Carrito con columna Origen; historial "Recorrido" con todos los orígenes; invalidaciones de TODOS los orígenes.

## 7. Decisiones y riesgos

D1 Origen por línea en detalle + cabecera NULL si mixto. D2 Contrato aditivo (payload legado válido). D3 Un material por movimiento. D4 Folio único: un acta por operación.
Riesgos: `fn_cancelar_movimiento` con cabecera NULL (mitigado + test) · downgrade con mixtos (aborta) · borradores históricos incoherentes (se eliminan) · interbloqueos (orden determinista + test).
