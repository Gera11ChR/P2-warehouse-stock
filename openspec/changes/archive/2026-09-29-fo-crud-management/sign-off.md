# Architecture Sign-Off — 2026-09-29-fo-crud-management

- **Rol:** @arq-reviewer · **Fecha:** 2026-09-29 · **Rama:** `feat/fo-crud-management`
- **Veredicto:** ✅ SIGN-OFF APPROVED (tras enmiendas re-verificadas)

## Invariantes auditados
| # | Invariante | Veredicto |
|---|---|---|
| 1 | `transaction_delegation` — ajuste FO vía `fn_ajustar_stock_fibra`, eliminación vía `fn_eliminar_inventario_fibra`; CERO aritmética en Python | ✅ PASA |
| 2 | Transferencias TEAMS/DEVOL — `fn_procesar_movimiento`/`fn_cancelar_movimiento` intactos | ✅ PASA |
| 3 | Aislamiento por módulo FO — DELETE solo toca la fila (modulo, material_id) | ✅ PASA |
| 4 | Atomicidad — catálogo + ajuste en el mismo `session.begin()` | ✅ PASA |
| 5 | `immutable_id_lista` — nada renumbra ni reutiliza | ✅ PASA |

## Enmiendas aplicadas antes de la aprobación
1. `REQ-DEL-001`: evento `ELIMINACION_FO` con snapshot jsonb completo `{modulo, material_id, stock_eliminado, motivo, usuario}` (Constitution 6.2).
2. `REQ-DEL-004`: eliminación con `stock_actual > 0` exige motivo no vacío (422); con stock 0 es opcional.
3. `REQ-TRF-INV-003`: resurrección DEVOL por UPSERT preexistente documentada y trazable.
4. `tasks 2.2`: detalles jsonb completo + atribución de actor vía `set_config('app.actor')` + actualización canónica de `ddl.sql`.
5. `tasks 2.3`: `fn_ajustar_stock_fibra` + `fn_eliminar_inventario_fibra` en `mandatory_functions`.
6. `tasks 4.1/4.2`: tests del contenido del evento, de REQ-DEL-004 y de resurrección DEVOL.
7. `tasks 3.1`: etiqueta `ELIMINACION_FO` en `TIPOS_ACCION_AUDITORIA`.
8. `proposal.md`: Impact Assessment + nota de semántica de resurrección DEVOL.

## Notas no bloqueantes (aceptadas)
- La eliminación FO es física sobre `inventario_fibra` (estado actual, no ledger); la traza forense queda en `ELIMINACION_FO`. Coherente con el modelo sparse "cero fantasmas".
- `fn_ajustar_stock_fibra`/`fn_cargar_stock_inicial_fibra` atribuyen auditoría a `CURRENT_USER` (precedente preexistente); `fn_eliminar_inventario_fibra` usa el patrón `app.actor`.
- Ausencia de scope SEC-002 en `/fibra/*` es deuda preexistente, fuera del alcance de este paquete.
