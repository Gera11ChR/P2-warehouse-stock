# EARS: Ergonomía — Justificación opcional en inventario y transferencias

Requisitos del cambio `2026-10-04-ergonomia-justificacion-opcional` en notación
EARS (Ubiquitous / Event-driven / State-driven / Option-driven / Unwanted).
Clasificación de severidad: **CRÍTICO** (constitucional) · **ALTO** · **MEDIO**.

> Convenciones: "usuario autorizado" = actor autenticado con alcance sobre la
> sección/material involucrada. "motivo" se refiere indistintamente al campo
> `motivo` (ajustes/edición/cancelación) y a `observaciones` (borradores
> TEAMS/DEVOL).

## 1. Ergonómica general (decisión de producto)

- **REQ-ERG-001 (Ubiquitous / ALTO).** El sistema **deberá** tratar el campo
  de justificación (`motivo` / `observaciones`) como OPCIONAL en la
  modificación de materiales, en los ajustes administrativos de stock, en las
  transferencias TEAMS y DEVOL y en la cancelación de movimientos: un payload
  que lo envíe como `null`, como cadena vacía `""`, o que lo omita, **deberá**
  ser aceptado sin bloqueo en frontend ni backend.
- **REQ-ERG-002 (Unwanted / CRÍTICO).** El sistema **no deberá** degradar la
  trazabilidad del ledger inmutable (Constitution 2.4): cada operación que
  mute stock **deberá** seguir registrando su evento en `auditoria_eventos`;
  solo el texto del motivo puede quedar vacío/nulo.

## 2. Modificación de materiales (Inventario General)

- **REQ-ERG-003 (State-driven / ALTO).** **Cuando** un usuario autorizado
  modifique datos de un material de Inventario General incluyendo
  `stock_actual`, **el sistema deberá** aceptar el PATCH con `motivo`
  ausente, `null` o `""`, enrutar el ajuste a
  `fn_ajustar_stock_general → fn_ajustar_stock_almacen` y auditar el evento
  `AJUSTE_INVENTARIO` con el motivo tal como fue recibido (`NULL` permitido).

## 3. Modificación de materiales (Fibra Óptica)

- **REQ-ERG-004 (State-driven / ALTO).** **Cuando** un usuario autorizado
  modifique un material de un módulo FO incluyendo `stock_actual`, **el
  sistema deberá** aceptar el PATCH con `motivo` ausente, `null` o `""`,
  enrutar el ajuste a `fn_ajustar_stock_fibra` y auditar el evento
  `AJUSTE_INVENTARIO_FO` con el motivo tal como fue recibido.

## 4. Ajustes administrativos independientes

- **REQ-ERG-005 (State-driven / ALTO).** **Cuando** un usuario autorizado
  ejecute `POST /api/v1/ajustes/stock-almacen` o `POST /api/v1/fibra/ajuste`
  con `motivo` ausente, `null` o `""`, **el sistema deberá** procesar el
  ajuste con normalidad (sin 422 por motivo vacío) manteniendo el diferencial,
  el bloqueo FOR UPDATE y la auditoría en PostgreSQL.

## 5. Transferencias TEAMS y DEVOL

- **REQ-ERG-006 (Event-driven / ALTO).** **Cuando** un usuario autorizado
  confirme una transferencia TEAMS o DEVOL con el campo "Motivo /
  Observaciones" en blanco, **el sistema deberá** crear el borrador con
  `observaciones` `null` (o cadena vacía), procesarlo vía
  `fn_procesar_movimiento` y registrar el evento de auditoría con
  `observaciones: null` sin excepción de validación.
- **REQ-ERG-007 (Ubiquitous / MEDIO).** La interfaz **deberá** eliminar la
  etiqueta "(obligatorio)" del campo "Motivo / Observaciones" en las vistas
  TEAMS y DEVOL, y **deberá** mantener habilitado el botón de confirmación
  con el campo vacío.

## 6. Cancelación de movimientos

- **REQ-ERG-008 (Event-driven / MEDIO).** **Cuando** un usuario autorizado
  cancele un movimiento CONFIRMADO con el campo de motivo en blanco, **el
  sistema deberá** aceptar la cancelación (motivo `null` o default SQL de
  `fn_cancelar_movimiento`) y auditar `motivo_cancelacion` en consecuencia.
