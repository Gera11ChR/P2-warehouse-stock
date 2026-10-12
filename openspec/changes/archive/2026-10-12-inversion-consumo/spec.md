# Spec: Inversión profunda de la lógica de consumo (Registro de Consumido)

**Change ID:** `2026-10-12-inversion-consumo`
**Fuente única:** `docs/migracion-dms-telecom/1 Changes.docx` (sección *Consumido.png*) + directiva del Paquete 2.
**Override vigente:** Unidad / TRANSF / Confirmar Devolución / Inventario FO.
**Origen de cada requisito:** `[DOCX]` fiel al documento; `[DIRECTIVA]` decisión del Paquete 2. Identificadores `RF-n [REQ-CONSUMO-NNN]` (Constitución §1.5).

## Resumen

El técnico entrega con el conteo del consumo. El sistema registra lo **consumido** y lo resta del inventario de la unidad; lo no consumido permanece en el inventario sin movimiento (el stock no sale al abrir el seguimiento, solo al cerrarlo, por lo que el remanente ya está en el inventario y **no se suma**). El concepto "Sobrante" se elimina de la BD, la API, las actas nuevas y la interfaz.

## Premisas verificadas

- Endpoint afectado: `POST /api/v1/equipos/{equipo_id}/seguimientos/{seguimiento_id}/cerrar`. `/api/v1/movimientos/procesar` no interviene (solo recibe `movimiento_id`).
- Hoy `fn_cerrar_seguimiento` descuenta `tomada − sobrante`; el sobrante nunca se suma al inventario.

## Decisiones aprobadas en el Gate T3

1. El campo **Consumido** inicia **vacío** y su captura es obligatoria antes de enviar el cierre.
2. El remanente **no se suma**: solo se descuenta la cantidad consumida del stock de la unidad.
3. Nombres: `consumidos` en la API y `p_consumidos` en PL/pgSQL.
4. `docs/migracion-dms-telecom/1 Changes.docx` se versiona en el commit del paquete.

## Requisitos funcionales (EARS)

- **RF-1 [REQ-CONSUMO-001] [DOCX] (Ubiquitous).** El formulario de cierre **deberá** solicitar por material la cantidad "Consumido", con el campo inicialmente vacío, y **no deberá** permitir enviar mientras algún campo esté vacío; ningún texto visible **deberá** contener "Sobrante".
- **RF-2 [REQ-CONSUMO-002] [DOCX] (Event-driven).** **Cuando** se cierre el seguimiento, el sistema **deberá** descontar del inventario de la unidad exactamente la cantidad consumida informada, sin sumar nada al inventario.
- **RF-3 [REQ-CONSUMO-003] [DIRECTIVA] (Ubiquitous).** `POST …/cerrar` **deberá** aceptar `consumidos: [{material_id, cantidad_consumida}]` con `extra="forbid"`; un cuerpo con `sobrantes` **deberá** rechazarse con 422.
- **RF-4 [REQ-CONSUMO-004] [DIRECTIVA] (Unwanted).** **Si** falta la línea de algún material del seguimiento, el sistema **deberá** responder 422 sin modificar inventario, ítems ni estado del seguimiento.
- **RF-5 [REQ-CONSUMO-005] (Unwanted).** **Si** `cantidad_consumida` es negativa o está duplicada, el sistema **deberá** responder 422; **si** es mayor que la tomada o el material no pertenece al seguimiento, **deberá** responder 400; en todos los casos con rollback total.
- **RF-6 [REQ-CONSUMO-006] (Unwanted).** **Si** el consumido supera el stock actual de la unidad, el sistema **deberá** responder 400 "Stock insuficiente en la Unidad…" con rollback total (Constitución §2.1, §4.1).
- **RF-7 [REQ-CONSUMO-007] [DIRECTIVA] (Ubiquitous).** `fn_cerrar_seguimiento` **deberá** recibir `p_consumidos JSONB` y ejecutar validación, bloqueo `FOR UPDATE`, descuento, auditoría y acta en una sola transacción; Python **no deberá** calcular stock.
- **RF-8 [REQ-CONSUMO-008] (Ubiquitous).** `seguimiento_items` **deberá** persistir `cantidad_consumida` como columna real (0 ≤ consumida ≤ tomada) y **no deberá** existir `cantidad_sobrante`.
- **RF-9 [REQ-CONSUMO-009] (Ubiquitous).** Los eventos `SEGUIMIENTO_CERRADO` y las actas nuevas **deberán** registrar `cantidad_tomada` y `cantidad_consumida`, sin clave de sobrante.
- **RF-10 [REQ-CONSUMO-010] (Ubiquitous).** Los eventos y actas ya emitidos son inmutables (§2.4): **deberán** conservar su contenido y seguir siendo consultables mostrando su cantidad consumida.
- **RF-11 [REQ-CONSUMO-011] (Ubiquitous).** Los seguimientos ya cerrados **deberán** conservar el mismo consumido tras la migración (backfill `tomada − sobrante`); los ABIERTOS **deberán** quedar con consumido NULL.
- **RF-12 [REQ-CONSUMO-012] [DIRECTIVA] (Ubiquitous).** Reportes > Consumo **deberá** mostrar Tomada y Consumida sin columna Sobrante, y la API de reportes **no deberá** exponer `cantidad_sobrante`.
- **RF-13 [REQ-CONSUMO-013] (Ubiquitous).** Un segundo cierre del mismo seguimiento **deberá** seguir siendo 409 sin doble descuento; apertura, "Agregar todo" y `/movimientos/procesar` **no deberán** cambiar.
- **RF-14 [REQ-CONSUMO-014] (Ubiquitous).** Todas las suites y gates (§7.2) **deberán** pasar al 100%; un test de barrido **deberá** fallar si "sobrante" aparece en texto visible del frontend.

## Casos límite

Consumido 0 en todas las líneas · consumido = tomada · consumido > stock actual de la unidad · duplicados · material ajeno · seguimiento ya cerrado · actas antiguas con clave sobrante · seguimientos abiertos durante la migración · cierres concurrentes.

## Fuera de alcance

Resto de requerimientos del `.docx` (transferencias mixtas, FO unificado, valor unitario, referencia, TRANSF, Confirmar Devolución) · movimientos · apertura de seguimientos · reescritura de histórico.

## Criterios de finalización

RF-1..RF-14 con test; contrato congelado antes del frontend; gates §7.2; aprobación humana.

## Matriz de trazabilidad

| RF | Tareas | Verificación |
| --- | --- | --- |
| RF-3, RF-4, RF-5 | T4, T5, T7 | pytest `test_REQ_CONSUMO_003..005_*` |
| RF-2, RF-6, RF-7 | T4, T6, T7 | pytest + sql_tests |
| RF-8, RF-11 | T4, T6 | test de migración (backfill) |
| RF-9, RF-10, RF-12 | T4, T8 | pytest (actas con snapshot antiguo y nuevo) |
| RF-13 | T4 | pytest |
| RF-1, RF-14 | T12, T13 | vitest + barrido |
