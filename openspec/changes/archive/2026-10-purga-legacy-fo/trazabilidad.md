# Trazabilidad: 2026-10-purga-legacy-fo

Matriz RF → implementación → prueba (cobertura 8/8 RF; E1-E13 en `spec.md` §5).

| RF | Alias | Implementación | Pruebas |
| :-- | :-- | :-- | :-- |
| RF-1 | REQ-PURGA-001 | `backend/alembic/versions/0028_purga_legacy_fo.py` (pasos 2-8, predicado `_PRED_EVENTOS`) | `test_migracion_0028.py::test_RF_001_003_purga_conserva_dominio_vivo_y_ledger_no_legacy`, `::test_E6_actor_con_scope_solo_legacy_pierde_el_scope_sin_recibir_nada` (E1-E6, E13) |
| RF-2 | REQ-PURGA-001 / REQ-FO-002 | 0028 pasos 9-10 (`ck_secciones_tipo`, `fn_procesar_movimiento`, `fn_cancelar_movimiento`) | `::test_RF_002_006_esquema_funciones_y_triggers_tras_la_purga` |
| RF-3 | REQ-PURGA-001 | 0028 paso 0/12 (instantánea, saldos fila a fila, md5 de eventos conservados) | `::test_RF_001_003_...` (stock, ledger no legacy, secuencias, E8) |
| RF-4 | REQ-PURGA-003 | `models/inventario.py`, `services/{movimientos,inventario,transaccional}.py`, `schemas/inventario.py`, `api/v1/{fibra,inventario}.py` | `test_fo_unificado.py::test_RF_4_*` (3: 422 con ids 2 y 3 como origen TEAMS y destino DEVOL; selector solo GENERAL/FO), `test_fo_transferencias.py::test_RF_4_secciones_transferibles_solo_general_y_fo` |
| RF-5 | REQ-PURGA-003 | `frontend/src/types.ts`, `utils/seccionLabel.ts`, `utils/auditoriaPresentacion.ts` (eliminado), `pages/{Auditoria,Transferencias}.tsx`, `utils/operadorPayload.ts` | `NomenclaturaFo.test.tsx`, `Transferencias.test.tsx`, `TransferenciasMultiOrigen.test.tsx`, `operadorPayload.test.ts`, `AuditoriaEtiquetas.test.ts` |
| RF-6 | REQ-PURGA-002 | 0028 (guardia E-1, `DISABLE/ENABLE TRIGGER`, `PURGA_LEGACY_FO`, `downgrade`) | `::test_RF_006_abortos_con_rollback_total` (3), `::test_RF_006_trigger_previamente_deshabilitado_aborta`, `::test_RF_006_guardia_e1_aborta_fuera_de_p2_y_p2_test` (E12), `::test_E7_...`, `::test_RF_006_downgrade_solo_esquema_y_reupgrade_noop` (E11), `::test_RF_006_downgrade_emite_notice_de_datos_no_restaurados`, `::test_RF_008_ciclo_head_0026_head_en_p2_test_limpia` |
| RF-7 | REQ-PURGA-001..003 (gobernanza) | `openspec/specs/001_core_logistics` (REQ-FO-001/002 reescritos, REQ-PURGA-001..003), `003_inventory_dashboard` (REQ-FO-003), `openspec.yaml` | `openspec validate --specs --strict` 3/3 |
| RF-8 | — | Suites retiradas/ajustadas: `test_fo_unificado.py`, `test_fo_transferencias.py`, `test_fo_valor_casos_limite.py`, `test_migracion_0027.py` (resiembra legacy en 0026), `helpers/fabrica.py`, `sql_tests/conftest.py` | pytest 453, sql_tests 25, mypy 0/85, tsc 0, eslint 0, vitest 531, vite build sin advertencias |

## Casos límite
| Caso | Cobertura |
| :-- | :-- |
| E1 mixto, E2 borrador, E3 `FO_UNIFICADO`, E4 `movimiento_id`/`acta_id`, E5 «PAQUETE (100 PZ)»/CATALOGO, E13 puntero | `test_RF_001_003_...` |
| E6 actor con scope solo legacy | `test_E6_...` |
| E7 sin secciones legacy | `test_E7_...` |
| E8 reaplicar | `test_RF_001_003_...` (segundo `upgrade 0028` = no-op) |
| E9 rollback y reintento | `test_RF_006_abortos_con_rollback_total` (rollback verificado; los datos se limpian y `esquema_en` reaplica 0028 con éxito) |
| E10 ids purgados | `test_RF_4_*` |
| E11 downgrade/re-upgrade | `test_RF_006_downgrade_solo_esquema_y_reupgrade_noop` |
| E12 guardia en otra base | `test_RF_006_guardia_e1_aborta_fuera_de_p2_y_p2_test` (unidad sobre la guardia; no se puede crear otra base: el rol de QA no posee CREATEDB) |

## Dispensas registradas
- Los abortos por las verificaciones internas 12(c) (stock) y 12(d) (md5 de eventos conservados) no se disparan desde pruebas externas: son aserciones de defensa en profundidad sobre el propio borrado; su rama de aborto es ejecutada por las verificaciones de 12(a), (d2) y de saldo legacy, y el resultado correcto se verifica en la prueba de conservación (stock fila a fila y md5).

## Evidencia operativa en `p2` (2026-10-16)
Respaldo previo `/tmp/opencode/p2_pre_0028.dump` (formato custom, permisos 600). Vista previa = resultado: 31 movimientos, 69 líneas, 13 actas, 2 scopes, 7 claves de idempotencia, 34 punteros, 129 eventos eliminados; ledger 1016 − 129 + 1 = 888; secciones restantes `GENERAL` y `FO`; ambos triggers `O`; `DELETE` posterior bloqueado.
