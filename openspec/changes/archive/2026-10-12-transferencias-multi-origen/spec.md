# Spec: Transferencias multi-origen (carrito combinado)

**Change ID:** `2026-10-12-transferencias-multi-origen` · Prefijo `REQ-TRFM-NNN`
**Fuente única:** `docs/migracion-dms-telecom/1 Changes.docx` (Error_Transf.png, Error_400_Transf.png). `[DOCX]` fiel al documento; `[DIRECTIVA]` decisión del paquete.
**Override:** Unidad / TRANSF / Confirmar Devolución / Inventario FO. El enum técnico `TEAMS` no se renombra aquí (nomenclatura de botones = otro paquete).

## Resumen

Un movimiento TEAMS (TRANSF) puede combinar en un mismo carrito materiales de Inventario General y de Fibra Óptica (Paquete / En Uso). Cada línea conserva y valida su sección de origen real. La confirmación es UNA operación atómica con un folio único: acta e historial amparan toda la operación y la trazabilidad de cada línea llega hasta su origen.

## Premisas verificadas

- Hoy el origen es único por cabecera y las líneas no lo registran.
- El 400 nace en el frontend: el carrito sobrevive al cambio de origen y se envía con el último origen elegido.
- `/movimientos/procesar` solo recibe `movimiento_id`: su contrato no cambia.

## Decisiones aprobadas

1. Solo TEAMS/TRANSF; DEVOL queda fuera de alcance.
2. `movimientos_cabecera.origen_almacen_id` = origen común si todas las líneas lo comparten; `NULL` si el carrito es mixto. La verdad vive en el detalle.
3. Trazabilidad unificada por operación: una sola acta (folio único) y una sola fila de historial con todas las líneas.
4. Cada línea agregada corresponde a un material único; la PK `(movimiento_id, material_id)` de `movimientos_detalle` no cambia (un material por movimiento).
5. No se crea `TransferenciasContext`: no existe y el carrito permanece como estado local de la página.

## Requisitos funcionales (EARS)

- **RF-1 [REQ-TRFM-001] [DOCX] (Ubiquitous).** El carrito de transferencia **deberá** permitir agregar materiales de Inventario General y de Fibra Óptica simultáneamente, sin bloquear ni deshabilitar la selección.
- **RF-2 [REQ-TRFM-002] [DIRECTIVA] (Ubiquitous).** Cada línea del borrador TEAMS **deberá** registrar su sección de origen (`movimientos_detalle.origen_almacen_id`) y el borrador **deberá** aceptar `origen_almacen_id` por línea.
- **RF-3 [REQ-TRFM-003] (Ubiquitous).** Un borrador con `origen_almacen_id` solo en la cabecera **deberá** seguir siendo válido; cada línea sin origen propio **deberá** heredar el de la cabecera.
- **RF-4 [REQ-TRFM-004] [DIRECTIVA] (Ubiquitous).** La cabecera **deberá** registrar `origen_almacen_id` cuando todas las líneas comparten origen y `NULL` cuando el carrito es mixto.
- **RF-5 [REQ-TRFM-005] (Unwanted).** **Si** una línea TEAMS no resuelve ningún origen, o su sección no existe, o es una GENERAL inactiva, **entonces** el sistema **deberá** responder 422 sin crear el borrador.
- **RF-6 [REQ-TRFM-006] (Unwanted).** **Si** el actor no es administrador y carece de scope sobre ALGUNA de las secciones de origen del borrador, **entonces** el sistema **deberá** responder 403 sin crear el borrador (§3.1/§3.2).
- **RF-7 [REQ-TRFM-007] [DOCX] (Event-driven).** **Cuando** se confirme un borrador mixto, `fn_procesar_movimiento` **deberá** validar y descontar cada línea contra el inventario de SU origen (`inventario_almacen` o `inventario_fibra` por módulo) en una sola transacción, devolver 200 y acreditar la unidad destino.
- **RF-8 [REQ-TRFM-008] (Unwanted).** **Si** el stock de cualquier línea es insuficiente en su origen, **entonces** el sistema **deberá** responder 400 con el origen real de esa línea y revertir TODO (ningún origen, unidad, acta ni auditoría modificados; el borrador permanece BORRADOR).
- **RF-9 [REQ-TRFM-009] (Ubiquitous).** Los bloqueos `FOR UPDATE` de líneas mixtas **deberán** tomarse en orden determinista (origen, material) para evitar interbloqueos (§2.3).
- **RF-10 [REQ-TRFM-010] (Ubiquitous).** Cada evento `TEAMS_TRANSFERENCIA` **deberá** registrar el origen de su línea (`almacen_origen_id` y, si es FO, `modulo_fo`).
- **RF-11 [REQ-TRFM-011] [DIRECTIVA] (Ubiquitous).** La confirmación **deberá** generar UNA sola acta de entrega (folio único) con todas las líneas y el origen de cada línea en el snapshot; el historial **deberá** mostrar la operación como una sola fila con todos sus orígenes.
- **RF-12 [REQ-TRFM-012] (Event-driven).** **Cuando** se cancele un movimiento confirmado mixto, `fn_cancelar_movimiento` **deberá** restituir cada línea a SU origen y auditarla, atómicamente.
- **RF-13 [REQ-TRFM-013] (Ubiquitous).** Las actas y eventos ya emitidos son inmutables (§2.4); los movimientos existentes **deberán** conservar su origen por backfill desde su cabecera.
- **RF-14 [REQ-TRFM-014] (Unwanted).** **Si** un borrador DEVOL incluye origen por línea, **entonces** el sistema **deberá** responder 422 (DEVOL no cambia).
- **RF-15 [REQ-TRFM-015] [DOCX] (Event-driven).** **Cuando** el usuario cambie la sección que consulta, el carrito **deberá** conservar sus líneas; cada línea agregada **deberá** llevar el origen de la sección desde la que se agregó y mostrarlo en una columna "Origen".
- **RF-16 [REQ-TRFM-016] (Ubiquitous).** El payload TEAMS **deberá** incluir `origen_almacen_id` en cada línea; el saldo proyectado por línea es solo presentación y la autoridad sigue siendo PostgreSQL.
- **RF-17 [REQ-TRFM-017] (Ubiquitous).** El contrato de `/movimientos/procesar` y los flujos DEVOL, consumo y FO **no deberán** cambiar.
- **RF-18 [REQ-TRFM-018] (Ubiquitous).** Todas las suites y gates (§7.2) **deberán** pasar al 100%.

## Casos límite

Carrito solo General / solo FO (cabecera con origen) · General + Paquete + En Uso · una línea sin stock en su origen · origen FO inactivo (permitido: son manejadores de ruteo) · GENERAL inactiva · actor sin scope en un solo origen · confirmaciones concurrentes con líneas en orden inverso · cancelación con la unidad sin stock (400). Borradores históricos incoherentes (p. ej. el 83 de la captura): el backfill les asigna el origen de su cabecera y seguirán fallando con 400; deben eliminarse y recrearse.

## Fuera de alcance

DEVOL multi-destino · nomenclatura TRANSF y botones · unificación Inventario FO · valor unitario · referencia · reparación automática de borradores incoherentes.

## Criterios de finalización

RF-1..RF-18 con test; contrato congelado antes del frontend; gates §7.2; aprobación humana.

## Matriz de trazabilidad

| RF | Tareas | Verificación |
| --- | --- | --- |
| RF-2..RF-6, RF-14 | T4, T5, T7 | pytest `test_REQ_TRFM_002..006,014_*` |
| RF-7..RF-10, RF-12 | T4, T6 | pytest + sql_tests |
| RF-11, RF-13 | T4, T6, T8 | pytest (acta única, backfill) |
| RF-1, RF-15, RF-16 | T12, T13 | vitest |
| RF-17, RF-18 | T9, T15 | suites + diff OpenAPI |
