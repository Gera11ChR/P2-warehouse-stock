# Spec: Nomenclatura visual TRANSF / Confirmar Devolución

**Change ID:** `2026-10-12-nomenclatura-transf` · Prefijo `REQ-NOM-NNN`
**Fuente única:** `docs/migracion-dms-telecom/1 Changes.docx` (Cambiar_a_TRANSF.png, DEVOL.png). Solo frontend.

## Resumen

Erradicar "TEAMS" de la interfaz (se muestra "TRANSF") y rotular el botón de DEVOL como "Confirmar Devolución". Los valores técnicos `TEAMS`/`DEVOL` del contrato no cambian.

## Decisiones aprobadas

1. La pestaña `DEVOL` NO cambia de nombre (el .docx solo cambia su botón de confirmación).
2. Se incluyen los textos secundarios (aviso del acta, Auditoría, Reportes).
3. Contrato, BD, enums, tipos y claves de consulta conservan `TEAMS`/`DEVOL`.

## Requisitos funcionales (EARS)

- **RF-1 [REQ-NOM-001] (Ubiquitous).** La pestaña de transferencia **deberá** mostrarse como "TRANSF".
- **RF-2 [REQ-NOM-002] (State-driven).** **Mientras** la pestaña TRANSF esté activa, el botón del carrito **deberá** decir "Confirmar Transferencia".
- **RF-3 [REQ-NOM-003] (State-driven).** **Mientras** la pestaña DEVOL esté activa, el botón del carrito **deberá** decir "Confirmar Devolución"; la pestaña seguirá llamándose "DEVOL".
- **RF-4 [REQ-NOM-004] (Ubiquitous).** La columna TIPO del historial y el modal de cancelación **deberán** mostrar "TRANSF" para los movimientos TEAMS; los DEVOL siguen como "DEVOL".
- **RF-5 [REQ-NOM-005] (Ubiquitous).** Los textos secundarios **deberán** usar la nomenclatura oficial: aviso del acta ("La transferencia hacia…"), etiqueta de Auditoría ("TRANSF — transferencia") y la descripción de Reportes > Entrega.
- **RF-6 [REQ-NOM-006] (Ubiquitous).** Una única función de etiquetas (`etiquetaTipoMovimiento`) **deberá** producir el texto visible, para que ninguna vista se desincronice.
- **RF-7 [REQ-NOM-007] (Unwanted).** **Si** se envía un movimiento, el payload **deberá** conservar `tipo_movimiento: 'TEAMS' | 'DEVOL'` (contrato intacto; no se toca backend).
- **RF-8 [REQ-NOM-008] (Ubiquitous).** Un test de barrido **deberá** fallar si "TEAMS" aparece en un texto visible (valores técnicos y comentarios exentos).
- **RF-9 [REQ-NOM-009] (Ubiquitous).** vitest, `tsc -b`, eslint, build y `openspec validate --strict` **deberán** pasar al 100%.

## Casos límite

Movimientos históricos TEAMS en el historial · eventos de auditoría legacy (se mapean en lectura; el ledger no se modifica) · claves de consulta y rutas internas con "TEAMS" (no se renombran).

## Fuera de alcance

Backend, enums, auditoría almacenada, comentarios de código, nombre de la pestaña DEVOL, los demás requerimientos del .docx.

## Criterios de finalización

RF-1..RF-9 con test; gates §7.2; aprobación humana.
