# Matriz de Trazabilidad — 2026-10-fo-unificado-valor-unitario

**Tarea:** T7 (Fase 8) · **Responsable de este artefacto:** `@tester` · **Fecha:** 2026-10-16
**Fuentes normativas:** `spec.md` (RF-1..RF-10, escenarios, E1..E15, C-1..C-7), `plan.md` §5, `tasks.md` (T5/T6/T7).
**Convenciones:** las rutas de prueba son relativas a `backend/tests/` (BE) y `frontend/src/` (FE). Las pruebas BE usan PostgreSQL real (`p2_test`) y aseveran respuesta HTTP **y** estado de BD; las FE (vitest + Testing Library) aseveran comportamiento visible / contrato de servicio. Todo nombre listado fue verificado con `grep` sobre el repositorio.

> Escenarios: se identifican como `RF-n·S<k>` en el orden en que aparecen en `spec.md`. Casos límite: `E1..E15` de §3.1.
> Marcas: ✅ cubierto y en verde · 🆕 prueba añadida en T7 · ⚠️ cubierto con hallazgo de producción abierto (ver §4).

---

## 1. Matriz por requisito

### RF-1 `[REQ-FO-001]` Inventario FO unificado

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-1·S1** Una sola existencia tras la migración (10 + 5 = 15; evento 10/5/15) | `test_migracion_0027.py::test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` | — | BD: `inventario_fibra` con 1 fila/material (15.000 y 7.000), sin columna `modulo`; evento `FO_UNIFICADO` por material con `valores_anteriores {PAQUETE:10, EN_USO:5}` y `valores_nuevos 15` |
| **RF-1·S2** Sin subapartados en la interfaz | — | `components/__tests__/NomenclaturaFo.test.tsx` › «el Sidebar ofrece «Inventario FO» y ningún «Paquete»/«En Uso»» y «navega a la página fibra-optica sin `sub`»; 🆕 `FibraOpticaValorTotal.test.tsx` › «RF-1/RF-10: la página muestra UNA sola tabla «Inventario FO», sin pestañas ni subapartados» | UI: una única entrada en la navegación; 1 sola `table`, sin `tablist`/`tab`, sin textos Paquete/En Uso |
| **RF-1·S3** `{"modulo":"PAQUETE"}` → 422 sin efectos | `test_fo_unificado.py::test_RF_001_una_fila_por_material_y_modulo_rechazado`, `::test_RF_001_modulo_rechazado_en_toda_operacion_fo` (carga inicial, ajuste y PATCH); `test_fibra.py::test_rf_1_inventario_fo_unico_sin_subapartados`, `::test_lectura_fibra_ruta_con_modulo_desaparece_404`; `test_esquemas.py::TestExtraForbid::test_fibra_carga_inicial_rechaza_modulo`, `::test_operadores_rechazan_campos_de_modulo`, `TestMetaInvariantes::test_modulo_ausente_en_dtos_del_dominio_vivo` | `utils/__tests__/operadorPayload.test.ts` (payload sin `modulo`); `utils/__tests__/errorMensaje.test.ts` › «RF-1: 422 por campo no declarado (p. ej. modulo)…» | HTTP 422 con `modulo` en el detalle; BD: stock sin cambio y 0 eventos `AJUSTE_INVENTARIO_FO` |
| Cláusula Ubiquitous (una sola existencia en UI/API/BD) | `test_fo_unificado.py::test_RF_001_una_fila_por_material_y_modulo_rechazado` (PK `material_id`, sin `modulo` en `information_schema` ni en la API) | `FibraOptica.test.tsx` › «RF-3: la tabla única muestra el título Inventario FO…» | HTTP: filas sin `modulo`; BD: columnas de `inventario_fibra` |
| **E6** Material con filas en Paquete y En Uso → se suman + evento por material | `test_migracion_0027.py::test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` (material `m1`) · 🆕 `::test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos` (4 + 6 = 10) | — | BD: suma exacta, 1 evento `FO_UNIFICADO` |
| **E7** Material solo en una partición → se conserva, fila única | `test_migracion_0027.py::test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` (material `m2`: 7 → 7.000) | — | BD: 1 fila, 7.000 |
| **E12** Eliminación física de material FO con stock (motivo + auditoría, sin `modulo`) | `test_fibra.py::test_REQ_DEL_001_003_delete_stock_positivo_con_motivo_204_aislado_y_auditado`, `::test_REQ_DEL_004_delete_stock_positivo_sin_motivo_422_fila_intacta`, `::test_REQ_DEL_004_delete_stock_cero_sin_motivo_204_opcional` | `FibraOptica.test.tsx` › «REQ-DEL-004/REQ-TRF-INV-002: eliminar con stock exige motivo…»; 🆕 `FibraOpticaValorTotal.test.tsx` › «RF-4/RF-5: eliminar un material FO… invalida resumen-general» | HTTP 204 / 422; BD: fila FO eliminada, catálogo y General intactos, evento `ELIMINACION_FO` con `stock_eliminado`, `motivo` y sin `modulo` |
| **E13** Migración repetida / reintento idempotente | 🆕 `test_migracion_0027.py::test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos` | — | BD: tras `upgrade 0027` + `upgrade head` repetidos, mismo stock, mismo nº de eventos `FO_UNIFICADO` (1), ledger idéntico, `valor_unitario` igual |

### RF-2 `[REQ-VALOR-001]` Atributo Valor Unitario

| Escenario / E-n | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-2·S1** Valor con decimales `12.345` | `test_valor_unitario.py::test_RF_002_persistencia_exacta_12_345`; `test_esquemas.py::TestValorUnitario::test_valor_con_3_decimales_aceptado` | `utils/__tests__/valorUnitario.test.ts` › «acepta 12.345» | HTTP 200 con número JSON `12.345`; BD `valor_unitario = 12.345` |
| **RF-2·S2** Fuera de rango (`-1`, `1.2345`, `1000000000`) → 422, valor previo intacto | `test_valor_unitario.py::test_RF_002_valor_fuera_de_rango_422_sin_cambios[-1/1.2345/1000000000]`; `::test_RF_008_entradas_decimales_invalidas_422`; `test_esquemas.py::TestValorUnitario::test_valor_fuera_de_rango_rechazado` | `valorUnitario.test.ts` › «rechaza «%s» con un mensaje…»; `MaterialForm.test.tsx` › «el Valor Unitario inválido %s bloquea el envío…» | HTTP 422; BD: valor `1.000` y 0 eventos `MATERIAL_MODIFICADO` |
| **E2** Valor `0` permitido, aporta 0 | 🆕 `test_fo_valor_casos_limite.py::test_RF_002_E2_valor_unitario_cero_permitido_aporta_cero`; `test_esquemas.py::TestValorUnitario::test_valor_cero_aceptado` | `valorUnitario.test.ts` › «acepta 0»; `MaterialForm.test.tsx` › «0 es un Valor Unitario válido y se envía» | HTTP 200 `valor_unitario 0`; BD `0.000`; Valor Total excluye su aporte; evento 1.000 → 0.000 |
| **E3** `1.2345` → 422 sin redondeo | `test_valor_unitario.py::test_RF_002_valor_fuera_de_rango_422_sin_cambios[1.2345]`, `::test_RF_008_entradas_decimales_invalidas_422[1.0005]`; `test_stock_decimal.py::test_RF_006_sobre_precision_1_0005_422_sin_efectos` | `valorUnitario.test.ts` (`'1.2345'` → /3 decimales/); `FibraOptica.test.tsx` › «un Valor Unitario con 4 decimales (1.2345) bloquea el envío» | HTTP 422; BD sin cambios |
| **E4** Desbordamiento `> 999 999 999.999`: 422 en API **y** rechazo en BD | `test_valor_unitario.py::test_RF_002_valor_fuera_de_rango_422_sin_cambios[1000000000]`, `::test_RF_002_check_en_bd_defensa_en_profundidad` (CHECK ≥ 0) · 🆕 `test_fo_valor_casos_limite.py::test_RF_002_E4_bd_rechaza_desbordamiento_aunque_se_salte_la_api` (`DataError` NUMERIC(12,3); el máximo exacto sí cabe) · `::test_RF_008_desbordamiento_sql_22003_400_canonico` | `valorUnitario.test.ts` (`'1000000000'` → /máxima/) | HTTP 422 (API) / 400 canónico (SQLSTATE 22003); BD: valor previo intacto |
| **E5** Notación científica `1e-4` rechazada por sobre-precisión | `test_valor_unitario.py::test_RF_008_entradas_decimales_invalidas_422[1e-4]`; `test_esquemas.py::TestValorUnitario::test_valor_fuera_de_rango_rechazado["1e-4"]` · 🆕 `test_fo_valor_casos_limite.py::test_RF_006_E5_cantidad_en_notacion_cientifica_sobre_precisa_422[1e-4/1E-4/1.5e-3]` (cantidades: carga inicial, ajuste, FO) | `valorUnitario.test.ts` (`'1e-4'` → /científica/); `utils/__tests__/cantidad.test.ts` (notación científica negativa E5) | HTTP 422; BD: stocks `3.000` y 0 eventos de ajuste |
| Cláusula: CHECK `>= 0` en BD | `test_valor_unitario.py::test_RF_002_check_en_bd_defensa_en_profundidad` | — | BD: `IntegrityError`, valor `1.000` |

### RF-3 `[REQ-VALOR-002]` Valor inicial, visualización y edición

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-3·S1** Valor por defecto `1.000` (catálogo existente) | `test_migracion_0027.py::test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` (catálogo sembrado en 0026 → 1.000), `::test_RF_E14_downgrade_aborta_con_fracciones_y_upgrade_limpio` (vuelve 1.000); `test_valor_unitario.py::test_RF_003_default_1_000_en_todo_el_catalogo` (material nuevo) | — | BD: `valor_unitario = 1.000` en todos los materiales; HTTP `1.0` número JSON |
| **RF-3·S2** Edición con decimales (`2.5` → `2.50 MXN` en las tres tablas) | `test_valor_unitario.py::test_RF_003_edicion_decimal_visible_en_las_tres_tablas` (General, FO y Unidad) | 🆕 `InventarioGeneralValorUnitario.test.tsx` › «RF-3/RF-5: guardar 2.5 en Modificar Material… la tabla y el indicador muestran lo persistido» (General); 🆕 `FibraOpticaValorTotal.test.tsx` › «RF-3/RF-5: guardar 2.5… la tabla FO muestra 2.50 MXN» (FO); `FibraOptica.test.tsx` › «editar el Valor Unitario a 2.5 envía valor_unitario: 2.5 y NO stock_actual»; `MaterialForm.test.tsx` › igual | HTTP: las 3 lecturas devuelven `2.5`; UI: `2.50 MXN` tras refrescar, payload `valor_unitario: 2.5` |
| Cláusula: columna **VALOR UNITARIO** con cifra a la izquierda y `MXN` a la derecha (General, FO, Unidad) | — | 🆕 `InventarioGeneralValorUnitario.test.tsx` › «RF-3: la tabla del Inventario General muestra VALOR UNITARIO…» (`1.00 MXN`, `12.345 MXN`); `FibraOptica.test.tsx` › «RF-3: la tabla única… columna Valor Unitario con cifra y MXN», «RF-3: un valor entero se presenta con dos decimales (1 → 1.00 MXN)»; `InventarioPorUnidad.test.tsx` › «RF-3: la tabla muestra la columna Valor Unitario de solo lectura con cifra y MXN»; `utils/__tests__/valorUnitario.test.ts` › `formatMxn` / `formatMxnConMoneda` | UI: encabezado `Valor Unitario` + `n.nn MXN` (mín. 2, máx. 3 decimales) |
| Cláusula Event-driven: Modificar precarga el valor actual (admin) y permite guardarlo | — | `MaterialForm.test.tsx` › «precarga el Valor Unitario con el valor persistido y label asociado»; `FibraOptica.test.tsx` › «precarga el Valor Unitario con el valor persistido» | UI: campo `Valor Unitario (MXN)` con el valor actual |
| Cláusula: C-3 el alta **no** recibe Valor Unitario (nace en 1.000) | `test_esquemas.py::TestExtraForbid::test_material_create_no_acepta_valor_unitario`; `test_valor_unitario.py::test_RF_003_default_1_000_en_todo_el_catalogo` | `MaterialForm.test.tsx` › «el modo create NO tiene campo Valor Unitario (nace en 1.000)» | UI sin campo en alta; BD `1.000` |
| Cláusula Option-driven: en el Inventario por Unidad el Valor Unitario es **solo lectura** | `test_valor_unitario.py::test_RF_003_edicion_decimal_visible_en_las_tres_tablas` (viene del catálogo por JOIN) | `InventarioPorUnidad.test.tsx` › columna solo lectura (sin `textbox`/`spinbutton`) ✅ 🆕 `ValorUnitarioRbacYUnidad.test.tsx` › «RF-3: el formulario Modificar Unidad muestra el Valor Unitario (12.345 MXN) como texto, sin control editable» | La **columna** de Unidad y el bloque «Material (solo lectura)» de «Modificar Unidad» muestran el Valor Unitario sin control editable ✅ (H-2 resuelto en T7) |

### RF-4 `[REQ-VALOR-003]` Cálculo transaccional del Valor Total

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-4·S1** Consolidación General + FO = `22.500` | `test_valor_unitario.py::test_RF_004_caso_exacto_spec_general_4x2_5_fo_10x1_25_22_500` | `SeccionGeneral.test.tsx` › «RF-4/RF-5: muestra «Valor Total»… con el valor de GET /inventario/resumen-general» | HTTP 200 `{"valor_total": 22.5, "moneda": "MXN"}` (número JSON); UI: cifra de la API sin recalcular |
| **RF-4·S2** Inventario vacío = `0` | `test_valor_unitario.py::test_RF_004_inventario_vacio_devuelve_0` | `KpiCards.test.tsx` › «RF-5: inventario vacío muestra 0.00 MXN (nunca nulo ni error)» | HTTP `valor_total 0` / UI `0.00 MXN` |
| **RF-4·S3** Material inactivo deja de contar | `test_valor_unitario.py::test_RF_004_material_inactivo_excluido` | — | HTTP 204 + total 50 → 0 |
| Cláusula Event-driven: refleja toda mutación (carga, ajuste, +Cantidad, Mover, TRANSF, devolución, cancelación, eliminación, valor) sin caché | `test_valor_unitario.py::test_RF_004_refleja_cambios_de_stock_y_de_valor` · 🆕 `test_fo_valor_casos_limite.py::test_RF_004_valor_total_refleja_cada_mutacion_de_existencias` (20→30→30→24→26→24→30→22; `fn_valor_total_inventario()` = 22.000) | `hooks/__tests__/resumenGeneral.test.tsx` › «+Cantidad y Mover… invalidan el Valor Total», «confirmar TRANSF/Devolución y las mutaciones de seguimiento…»; `Transferencias.test.tsx` › «RF-4/RF-5: tras confirmar una TRANSF…», «cancelar un movimiento invalida el Valor Total»; `OperadoresRapidosFlujo.test.tsx`, `operadoresHooks.test.tsx` | HTTP: total exacto tras cada operación; BD: función SQL coincide; UI: invalidación de `['inventario','resumen-general']` |
| **E1** Ajustar stock a `0` (fila conservada, aporta 0, se audita) | 🆕 `test_fo_valor_casos_limite.py::test_RF_006_E1_ajuste_a_cero_conserva_fila_aporta_cero_y_audita` (General y FO) | `utils/__tests__/cantidad.test.ts` › «permitirCero acepta 0 (ajustes y Valor Unitario) pero no negativos»; `MaterialForm.test.tsx` › «el stock con 4 decimales bloquea el envío con mensaje; 0 es válido» | HTTP 200 y fila visible con 0; BD `0.000`; total 38 → 6; eventos `AJUSTE_INVENTARIO` / `AJUSTE_INVENTARIO_FO` con `cantidad 0.000` y diferencial −4 / −6 |
| **E9** Suma de productos > 12 dígitos no se trunca ni falla | `test_valor_unitario.py::test_RF_004_E9_valores_grandes_sin_truncar_ni_error` | — | HTTP 200 número JSON; BD `fn_valor_total_inventario() = 999999999998000000.000` |
| Cláusula: respuesta con `moneda: "MXN"` y default-deny | `test_valor_unitario.py::test_RF_008_resumen_general_default_deny`, `::test_RF_004_caso_exacto_spec_general_4x2_5_fo_10x1_25_22_500` (`moneda`) | `hooks/__tests__/resumenGeneral.test.tsx` › «consulta GET /inventario/resumen-general y expone el valor del servidor» | HTTP 422 sin `X-Actor`, 403 sin scope; `moneda: "MXN"` |

### RF-5 `[REQ-VALOR-004]` Posición del indicador Valor Total

| Escenario / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración UI |
| :-- | :-- | :-- | :-- |
| **RF-5·S1** Orden de tarjetas (`Valor Total` segunda) | — | `KpiCards.test.tsx` › «RF-5: el orden de tarjetas es Total Materiales, Valor Total, Stock Total, Alertas Stock, Transferencias Hoy»; `SeccionGeneral.test.tsx` › «RF-4/RF-5: muestra «Valor Total» como segunda tarjeta…» | Orden DOM de las 5 tarjetas |
| **RF-5·S2** Refresco tras editar el valor | `test_valor_unitario.py::test_RF_004_refleja_cambios_de_stock_y_de_valor` (la API devuelve el nuevo total) | `KpiCards.test.tsx` › «RF-5: tras una mutación… se refresca con el valor persistido»; 🆕 `InventarioGeneralValorUnitario.test.tsx` (editar Valor Unitario → invalida `resumen-general` → indicador muestra `10.00` de la API); 🆕 `FibraOpticaValorTotal.test.tsx` (Modificar FO invalida `resumen-general`) | `getResumenGeneral` llamado 2 veces; el indicador muestra el valor de la API |
| Cláusula: cifra con `MXN` a la derecha, sin recalcular | — | `KpiCards.test.tsx` › «RF-5: muestra la cifra de la API con 2-3 decimales y la etiqueta MXN…», «conserva hasta 3 decimales (12.345 → 12.345 MXN)» | UI |
| Cláusula State-driven: estados de carga / error explícitos (nunca un valor inventado) | — | `KpiCards.test.tsx` › «mientras carga muestra un estado de carga explícito…», «si la consulta falla muestra un error explícito (no 0)…»; `resumenGeneral.test.tsx` › «un error de API no se reinterpreta como 0 (fail-closed)» | UI: estado de carga / error |
| C-1: el Valor Total no reacciona al filtro de sección; las otras tarjetas no cambian | — | `KpiCards.test.tsx` › «las otras cuatro tarjetas no cambian…» | UI |

### RF-6 `[REQ-DEC-001]` Existencias y cantidades decimales

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-6·S1** Ajuste fraccionario `7.250` | `test_stock_decimal.py::test_RF_006_ajuste_fraccionario_7_250`, `::test_RF_006_evento_auditoria_con_cantidad_decimal` (FO) | `MaterialForm.test.tsx` › «editar el stock a 7.25 envía stock_actual: 7.25»; `FibraOptica.test.tsx` › «editar el stock a 7.25 envía stock_actual: 7.25» | HTTP `7.25`; BD `7.250`; evento con `cantidad 7.250` y `diferencial 2.250` / `4.250` |
| **RF-6·S2** Transferencia `2.5` y cancelación exacta | `test_stock_decimal.py::test_RF_006_transferencia_2_5_y_cancelacion_reversion_exacta` · 🆕 `test_fo_valor_casos_limite.py::test_RF_006_devolucion_fraccionaria_y_cancelacion_exacta` (DEVOL 1.5) | `Transferencias.test.tsx` › «RF-6: el carrito acepta una cantidad decimal (2.5) y la envía como cantidad: 2.5» | HTTP 200; BD: origen y Unidad vuelven exactamente; `movimientos_detalle.cantidad = 2.500`; evento `MOVIMIENTO_CANCELADO` 2.500 |
| **RF-6·S3** Sobre-precisión `1.0005` → 422 sin efectos | `test_stock_decimal.py::test_RF_006_sobre_precision_1_0005_422_sin_efectos`; `test_esquemas.py::TestExtremosMovimiento::test_cantidad_sobre_precisa_rechazada`; `test_operadores_rapidos.py::test_cantidad_fuera_de_rango_422` | `Transferencias.test.tsx` › «RF-6: una cantidad con más de 3 decimales deshabilita Confirmar»; `utils/__tests__/cantidad.test.ts`; `valorUnitario.test.ts` (esquemas zod) | HTTP 422; BD: sin existencias ni evento `STOCK_INICIAL` |
| **RF-6·S4** Concurrencia con decimales (8 vs 7 sobre 10) | `test_stock_decimal.py::test_RF_006_concurrencia_8_vs_7_sobre_stock_10` (`asyncio.gather`, `FOR UPDATE`) | — | HTTP `[200, 400]`; BD: stock final ∈ {2,3}, nunca negativo, Unidad coherente |
| Cláusula: saldo no negativo con decimales | `test_stock_decimal.py::test_RF_006_saldo_nunca_negativo_con_decimales` | — | HTTP 400 canónico; BD stock `2.4` intacto, 0 eventos |
| Cláusula: seguimientos (tomadas/consumidas) y cierre decimales | `test_stock_decimal.py::test_RF_006_seguimiento_con_cantidades_decimales` | `SeguimientoCierreForm.test.tsx` › «RF-6: el campo Consumido admite decimales», «un consumido decimal (1.5) es válido…», «con 4 decimales bloquea el envío»; `SeguimientoNuevaListaForm.test.tsx` › «cantidades decimales (RF-6)» | BD `cantidad_tomada 2.500`, `cantidad_consumida 1.250`; evento `SEGUIMIENTO_CERRADO` decimal |
| Cláusula: +Cantidad / Mover decimales | 🆕 `test_fo_valor_casos_limite.py::test_RF_006_sumar_cantidad_y_mover_aceptan_decimales` | `OperadoresRapidosDialogs.test.tsx` › «acepta la cantidad decimal «%s»…»; `operadorPayload.test.ts` › «acepta la cantidad decimal %s…» | HTTP 200 (`3.5`; `2.25/2.25`); BD `2.250`/`2.250`; ledger `0.500` / `1.250` |
| Cláusula: identificadores enteros y `stock_minimo` entero | 🆕 `test_fo_valor_casos_limite.py::test_RF_006_identificadores_y_stock_minimo_permanecen_enteros` | `operadorPayload.test.ts` › «rechaza material_id %s» (1.2) | HTTP 422 en `material_id`/`almacen_id`/`stock_minimo` fraccionarios; BD: `stock_minimo = 5` (int) y sin altas |
| Cláusula: aritmética solo en PostgreSQL | `test_operadores_rapidos.py::test_cero_aritmetica_de_stock_en_la_capa_de_aplicacion` (AST) | — | Guarda estática de `app/` |
| **E11** Cantidad decimal en U.M. `PZ` permitida | 🆕 `test_fo_valor_casos_limite.py::test_RF_006_E11_cantidad_decimal_en_um_piezas_permitida` | — | HTTP 200 `2.75`; BD `2.750` |

### RF-7 `[REQ-VALOR-005]` Auditoría de Valor Unitario y de la unificación

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-7·S1** Evento de cambio de valor (anterior `1.000`, nuevo `2.500`, actor y fecha) | `test_valor_unitario.py::test_RF_007_evento_material_modificado_con_anterior_y_nuevo` · 🆕 `test_fo_valor_casos_limite.py::test_RF_007_evento_de_valor_registra_material_fecha_y_es_consultable` · ✅ 🆕 `::test_RF_007_evento_de_valor_atribuye_al_actor_http` | `AuditoriaEtiquetas.test.ts` › 🆕 «RF-7/RF-10: etiqueta la fusión FO_UNIFICADO y el cambio de Valor Unitario…» | BD/API: `MATERIAL_MODIFICADO` con `valores_anteriores/nuevos.valor_unitario`, `material_id` y `created_at` ✅; `usuario` = actor HTTP (`admin-qa`) en BD y en `GET /auditoria` ✅ (H-1 resuelto en T7) |
| **RF-7·S2** Ledger intacto tras migrar (conteo y contenido) | `test_migracion_0027.py::test_RF_001_007_fusion_fo_unificado_y_ledger_intacto`, 🆕 `::test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos` | — | BD: filas previas idénticas (id, usuario, tipo, cantidad, detalles, `created_at`) |
| Cláusula: eventos del ledger íntegros (sin UPDATE/DELETE) | 🆕 `test_fo_valor_casos_limite.py::test_RF_007_ledger_inmutable_update_y_delete_rechazados` | — | BD: trigger `append-only` rechaza UPDATE y DELETE; evento intacto |
| Cláusula: eventos históricos con `modulo` siguen consultables | 🆕 `test_fo_valor_casos_limite.py::test_RF_007_evento_historico_con_modulo_sigue_consultable_por_api` | `NomenclaturaFo.test.tsx` › «los eventos de auditoría históricos con `modulo` se presentan como «Inventario FO» sin mutar el dato» | HTTP 200 con `detalles {modulo: PAQUETE}` intacto; BD sin mutar; UI rotula «Inventario FO» |
| Cláusula Unwanted: sin evento si el valor no cambia | `test_valor_unitario.py::test_RF_007_sin_evento_si_el_valor_no_cambia`; `::test_RF_008_admin_con_null_noop_sin_evento` (E15) | `FibraOptica.test.tsx`/`MaterialForm.test.tsx` › «no tocar el Valor Unitario NO lo incluye en el payload» | HTTP 200; BD: 0 eventos |
| **E10** Dos ediciones concurrentes del mismo Valor Unitario | 🆕 `test_fo_valor_casos_limite.py::test_RF_007_E10_ediciones_concurrentes_ultima_escritura_prevalece` (`asyncio.gather`) | — | HTTP 200 + 200; BD: valor final ∈ {2.500, 3.500} = API; 2 eventos encadenados (1.000→x, x→final) |

### RF-8 `[REQ-VALOR-006]` Contrato API y seguridad

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-8·S1** Propiedad extra → 422 | `test_valor_unitario.py::test_RF_008_campo_extra_422`; `test_esquemas.py::TestMetaInvariantes::test_todos_los_schemas_entrada_tienen_extra_forbid`; `test_fo_unificado.py::test_RF_001_modulo_rechazado_en_toda_operacion_fo` | `errorMensaje.test.ts` › «RF-1: 422 por campo no declarado…» | HTTP 422 |
| **RF-8·S2** Actor sin privilegios → 403, valor sin cambios | `test_valor_unitario.py::test_RF_008_no_admin_con_valor_403_y_valor_sin_cambios` (con `2.5` y con `null`), `::test_RF_008_no_admin_en_patch_fibra_con_valor_403` | `errorMensaje.test.ts` › «RF-8: 403 muestra el mensaje canónico del backend»; `MaterialForm.test.tsx` › «con esAdmin=false el campo está deshabilitado y valor_unitario nunca viaja»; 🆕 `ValorUnitarioRbacYUnidad.test.tsx` › «con esAdmin=false… (FibraMaterialForm)» | HTTP 403 `AUTHORIZATION_FAILED`; BD `3.500` intacto; UI (RBAC visual, no seguridad) |
| **RF-8·S3** Representación numérica (número JSON, no string) | `test_valor_unitario.py::test_RF_008_respuestas_con_numero_json_no_string`, `::test_RF_002_persistencia_exacta_12_345` | `KpiCards.test.tsx` › «RF-5: muestra la cifra de la API… sin recalcular»; `hooks/__tests__/resumenGeneral.test.tsx` (el valor del servidor se expone tal cual) | HTTP: `float` en `valor_unitario`, `stock_actual`, `valor_total` |
| Cláusula: `NaN`/`Infinity` rechazados (nunca 200/500) | `test_valor_unitario.py::test_RF_008_entradas_no_finitas_rechazadas_sin_cambios[NaN/Infinity/-Infinity]` | — | HTTP 422 `finite_number`; BD y ledger sin cambios |
| Cláusula: error de regla de PostgreSQL → 400/422 canónico, nunca 500 | `test_valor_unitario.py::test_RF_008_desbordamiento_sql_22003_400_canonico`; `test_stock_decimal.py::test_RF_006_saldo_nunca_negativo_con_decimales` | `errorMensaje.test.ts` › «RF-6: 400 canónico se muestra tal cual» | HTTP 400; BD intacta |
| Cláusula: `resumen-general` exige actor (default-deny) | `test_valor_unitario.py::test_RF_008_resumen_general_default_deny` | — | HTTP 422 sin header; 403 sin scope |
| **E15** `valor_unitario: null` explícito → no-op | `test_valor_unitario.py::test_RF_008_admin_con_null_noop_sin_evento` (admin), `::test_RF_008_no_admin_con_valor_403_y_valor_sin_cambios` (no admin → 403); `test_esquemas.py::TestValorUnitario::test_valor_null_explicito_permitido_en_schema` | — | HTTP 200 sin escritura; BD `1.000`; 0 eventos; nunca 500 |

### RF-9 `[REQ-FO-002]` Compatibilidad con movimientos históricos

| Escenario / E-n / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración HTTP · BD · UI |
| :-- | :-- | :-- | :-- |
| **RF-9·S1** Cancelación de un TRANSF legacy (origen FO En Uso, cantidad 3) | `test_fo_unificado.py::test_RF_009_cancelar_transf_confirmado_origen_legacy_en_uso_restaura`; `test_fo_transferencias.py::test_RF_9_cancelar_teams_legacy_restituye_fo_unificado` | `Transferencias.test.tsx` › «cancelar un movimiento invalida el Valor Total y ["fibra"]» | HTTP 200; BD: FO 7 → 10, movimiento `CANCELADO`, evento `MOVIMIENTO_CANCELADO` con motivo y `almacen_origen_id` legacy |
| **RF-9·S2** Orígenes antiguos no seleccionables | `test_fo_unificado.py::test_RF_009_secciones_legacy_no_seleccionables`; `test_fo_transferencias.py::test_RF_9_secciones_transferibles_incluyen_fo_excluyen_legacy` | 🆕 `Transferencias.test.tsx` › «RF-9/RF-10: el selector de Sección Origen ofrece solo «Inventario General» e «Inventario FO»…»; `operadorPayload.test.ts` › «mapea GENERAL y FO 1:1 y rechaza otros (incl. orígenes FO históricos)»; `OperadoresRapidosDialogs.test.tsx` › «no ofrece como destino un tipo FO histórico…» | HTTP: solo `GENERAL`/`FO`; UI: ningún `option` Paquete/En Uso |
| Cláusula: movimientos/eventos históricos consultables con datos originales | 🆕 `test_fo_valor_casos_limite.py::test_RF_009_movimiento_historico_legacy_consultable_con_datos_originales` | `Transferencias.test.tsx` › «RF-9: un movimiento histórico con origen_almacen_id fuera de las secciones transferibles se rotula «Inventario FO»»; `TransferenciasMultiOrigen.test.tsx` › «RF-9: un origen de línea… FO histórico se rotula «Inventario FO»» | HTTP: detalle y listado con `origen_almacen_id = 3`, cantidad 3; BD sin reescribir |
| Cláusula: TRANSF nuevo desde origen legacy enruta al FO unificado | `test_fo_transferencias.py::test_RF_9_teams_desde_origen_legacy_en_uso_enruta_fo_unificado` | — | HTTP 200; BD FO 50 → 20, Unidad 30, evento con `almacen_origen_id` legacy |
| Cláusula: etiquetas históricas = «Inventario FO» | — | `NomenclaturaFo.test.tsx` › «el Inventario FO y los orígenes FO históricos se muestran como «Inventario FO»», «un id de sección no listado… se rotula «Inventario FO»» | UI |
| **E8** BORRADOR en curso con origen FO antiguo: confirmable o cancelable | `test_fo_unificado.py::test_RF_009_borrador_legacy_origen_paquete_procesable` (confirmar) · 🆕 `test_fo_valor_casos_limite.py::test_RF_009_E8_borrador_legacy_origen_en_uso_descartable_sin_tocar_stock` (descartar vía `DELETE`; `POST …/cancelar` en borrador → 409) | — | HTTP 200 (FO 20 → 12, Unidad 8) / 204 + 404 posterior; BD: stock intacto (9.000) y cabecera eliminada |

### RF-10 `[REQ-FO-003]` Nomenclatura oficial Inventario FO

| Escenario / cláusula | Prueba(s) backend | Prueba(s) frontend | Aseveración |
| :-- | :-- | :-- | :-- |
| **RF-10·S1** Barrido de nomenclatura (sin coincidencias fuera de excepciones) | — | `NomenclaturaFo.test.tsx` › «ningún texto visible usa «Paquete», «En Uso», «FO Paquete» ni «FO En Uso»…», «el barrido encuentra el código fuente de la aplicación» | Barrido sobre todo `src/**` (excluye tests): 0 ofensores |
| Cláusula Unwanted: el barrido **debe fallar** ante un nombre deprecado (caso positivo del detector) | — | `NomenclaturaFo.test.tsx` › «el detector reconoce los nombres deprecados y respeta las excepciones» | Detector dispara con casos positivos; respeta U.M. `PAQUETE (100 PZ)` |
| Cláusula: navegación con una única entrada sin subentradas | — | `NomenclaturaFo.test.tsx` › «el Sidebar ofrece «Inventario FO» y ningún «Paquete»/«En Uso»», «navega a la página fibra-optica sin `sub`»; `Sidebar.test.tsx`; `FibraOptica.test.tsx` › «estado vacío: «Sin materiales en el Inventario FO.»» | UI |
| Cláusula: selectores TRANSF/Mover/+Cantidad, auditoría y mensajes | — | `Transferencias.test.tsx` (🆕 selector de origen), `FibraOptica.test.tsx` › «Mover ofrece como destino los demás inventarios (sin el origen Inventario FO)»; `AuditoriaEtiquetas.test.ts` (🆕); `NomenclaturaFo.test.tsx` (auditoría histórica) | UI |

---

## 2. Verificación de cobertura de escenarios y casos límite

### 2.1 Escenarios `#### Scenario` (24)

| Id | Escenario | Cubierto | Id | Escenario | Cubierto |
| :-- | :-- | :-: | :-- | :-- | :-: |
| RF-1·S1 | Una sola existencia tras la migración | ✅ | RF-6·S1 | Ajuste fraccionario | ✅ |
| RF-1·S2 | Sin subapartados en la interfaz | ✅ | RF-6·S2 | Transferencia fraccionaria y cancelación | ✅ |
| RF-1·S3 | Módulo rechazado | ✅ | RF-6·S3 | Sobre-precisión | ✅ |
| RF-2·S1 | Valor con decimales | ✅ | RF-6·S4 | Concurrencia con decimales | ✅ |
| RF-2·S2 | Valor fuera de rango | ✅ | RF-7·S1 | Evento de cambio de valor | ✅ |
| RF-3·S1 | Valor por defecto | ✅ | RF-7·S2 | Ledger intacto | ✅ |
| RF-3·S2 | Edición con decimales | ✅ | RF-8·S1 | Propiedad extra | ✅ |
| RF-4·S1 | Consolidación General + FO | ✅ | RF-8·S2 | Actor sin privilegios | ✅ |
| RF-4·S2 | Inventario vacío | ✅ | RF-8·S3 | Representación numérica | ✅ |
| RF-4·S3 | Material inactivo | ✅ | RF-9·S1 | Cancelación de un movimiento legacy | ✅ |
| RF-5·S1 | Orden de tarjetas | ✅ | RF-9·S2 | Orígenes antiguos no seleccionables | ✅ |
| RF-5·S2 | Refresco tras editar el valor | ✅ | RF-10·S1 | Barrido de nomenclatura | ✅ |

### 2.2 Casos límite E1..E15

| E-n | Caso | Prueba principal | Estado |
| :-- | :-- | :-- | :-- |
| E1 | Ajustar stock a 0 | 🆕 `test_RF_006_E1_ajuste_a_cero_conserva_fila_aporta_cero_y_audita` | ✅ |
| E2 | Valor Unitario 0 | 🆕 `test_RF_002_E2_valor_unitario_cero_permitido_aporta_cero` | ✅ |
| E3 | Valor con > 3 decimales | `test_RF_002_valor_fuera_de_rango_422_sin_cambios[1.2345]` | ✅ |
| E4 | Desbordamiento (API 422 + BD) | `test_RF_002_valor_fuera_de_rango_422_sin_cambios[1000000000]` + 🆕 `test_RF_002_E4_bd_rechaza_desbordamiento_aunque_se_salte_la_api` | ✅ |
| E5 | Notación científica `1e-4` | `test_RF_008_entradas_decimales_invalidas_422[1e-4]` + 🆕 `test_RF_006_E5_cantidad_en_notacion_cientifica_sobre_precisa_422` | ✅ |
| E6 | Filas Paquete + En Uso → suma + evento | `test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` | ✅ |
| E7 | Solo una partición | `test_RF_001_007_fusion_fo_unificado_y_ledger_intacto` (`m2`) | ✅ |
| E8 | BORRADOR legacy confirmable/cancelable | `test_RF_009_borrador_legacy_origen_paquete_procesable` + 🆕 `test_RF_009_E8_borrador_legacy_origen_en_uso_descartable_sin_tocar_stock` | ✅ |
| E9 | Suma > 12 dígitos | `test_RF_004_E9_valores_grandes_sin_truncar_ni_error` | ✅ |
| E10 | Ediciones concurrentes de Valor Unitario | 🆕 `test_RF_007_E10_ediciones_concurrentes_ultima_escritura_prevalece` | ✅ |
| E11 | Decimales en U.M. `PZ` | 🆕 `test_RF_006_E11_cantidad_decimal_en_um_piezas_permitida` | ✅ |
| E12 | Eliminación física de material FO con stock | `test_REQ_DEL_001_003_delete_stock_positivo_con_motivo_204_aislado_y_auditado` | ✅ |
| E13 | Migración repetida idempotente | 🆕 `test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos` | ✅ |
| E14 | `downgrade()` con stock fraccional aborta | `test_RF_E14_downgrade_aborta_con_fracciones_y_upgrade_limpio` | ✅ |
| E15 | `valor_unitario: null` → no-op | `test_RF_008_admin_con_null_noop_sin_evento` | ✅ |

**E-n verificables solo manualmente:** ninguna. Todas tienen prueba automatizada. *Nota de alcance (no es una E-n):* el aspecto **visual real** (alineación de `MXN`, rejilla `lg:grid-cols-5`, contraste) solo puede apreciarse en navegador; las pruebas jsdom aseveran orden del DOM, texto y estados, no píxeles. Se recomienda una inspección visual manual en el cierre de QA (no bloqueante).

---

## 3. Resumen de cobertura

| Dimensión | Cubiertos / Total | % |
| :-- | :-: | :-: |
| Requisitos `RF-1..RF-10` con prueba automatizada | 10 / 10 | **100 %** |
| Escenarios `#### Scenario` | 24 / 24 | **100 %** |
| Casos límite `E1..E15` | 15 / 15 | **100 %** |
| E-n solo verificables manualmente | 0 / 15 | 0 % |
| Escenarios/E-n con hallazgo de producción abierto | 0 (H-1 y H-2 resueltos en T7; ver §4) | — |

> Cobertura = existencia de al menos una prueba automatizada que asevera la regla. Los hallazgos H-1 y H-2 detectados por `@tester` se corrigieron durante T7 (ver §4) y sus pruebas (antes `xfail(strict)` / `it.fails`) son ahora pruebas ordinarias en verde.

### Pruebas añadidas en T7

Backend (`backend/tests/`, 19 casos de `@tester` + 3 de T7 en `test_valor_unitario.py`: RBAC FO con `null`/mixto, admin FO + null no-op, `modulo` en catálogo → 422):

- `test_fo_valor_casos_limite.py` (nuevo): `test_RF_006_E1_ajuste_a_cero_conserva_fila_aporta_cero_y_audita`, `test_RF_002_E2_valor_unitario_cero_permitido_aporta_cero`, `test_RF_002_E4_bd_rechaza_desbordamiento_aunque_se_salte_la_api`, `test_RF_006_E5_cantidad_en_notacion_cientifica_sobre_precisa_422` (×3), `test_RF_007_E10_ediciones_concurrentes_ultima_escritura_prevalece`, `test_RF_006_E11_cantidad_decimal_en_um_piezas_permitida`, `test_RF_006_identificadores_y_stock_minimo_permanecen_enteros`, `test_RF_006_sumar_cantidad_y_mover_aceptan_decimales`, `test_RF_006_devolucion_fraccionaria_y_cancelacion_exacta`, `test_RF_007_evento_de_valor_registra_material_fecha_y_es_consultable`, `test_RF_007_evento_de_valor_atribuye_al_actor_http`, `test_RF_007_ledger_inmutable_update_y_delete_rechazados`, `test_RF_007_evento_historico_con_modulo_sigue_consultable_por_api`, `test_RF_009_movimiento_historico_legacy_consultable_con_datos_originales`, `test_RF_009_E8_borrador_legacy_origen_en_uso_descartable_sin_tocar_stock`, `test_RF_004_valor_total_refleja_cada_mutacion_de_existencias`.
- `test_migracion_0027.py` (ampliado): `test_RF_001_E13_migracion_repetida_es_idempotente_sin_duplicar_eventos`.

Frontend (`frontend/src/`, 9 casos nuevos):

- `components/__tests__/InventarioGeneralValorUnitario.test.tsx` (nuevo, 2): columna VALOR UNITARIO del Inventario General; editar a 2.5 → `valor_unitario: 2.5`, invalida `resumen-general`, tabla `2.50 MXN` e indicador con el valor de la API.
- `components/__tests__/FibraOpticaValorTotal.test.tsx` (nuevo, 3): editar FO a 2.5 → invalida `resumen-general` y `2.50 MXN`; eliminar FO invalida `resumen-general`; una sola tabla sin pestañas Paquete/En Uso.
- `components/__tests__/ValorUnitarioRbacYUnidad.test.tsx` (nuevo, 2): RBAC visual de `FibraMaterialForm` (`esAdmin=false`); prueba **H-2** resuelta (Valor Unitario solo lectura en «Modificar Unidad»).
- `components/__tests__/Transferencias.test.tsx` (+1): selector de Sección Origen solo con «Inventario General» e «Inventario FO».
- `components/__tests__/AuditoriaEtiquetas.test.ts` (+1): etiquetas `FO_UNIFICADO` y `MATERIAL_MODIFICADO` sin nomenclatura deprecada.

---

## 4. Hallazgos de `@tester` y su resolución en T7

| Id | Severidad | RF / cláusula | Hallazgo | Resolución (T7) |
| :-- | :-- | :-- | :-- | :-- |
| **H-1** | ALTA (confirmada por `@qa-agent`/`@arq-reviewer`) — *Logic Drift* de auditoría | RF-7 (evento «con **actor**…») | El evento `MATERIAL_MODIFICADO` por cambio de `valor_unitario` registraba `usuario = 'p2admin'` (rol de BD). **Doble causa raíz:** (1) el trigger `fn_auditar_modificacion_material` usaba `CURRENT_USER`; (2) `catalogo_svc.actualizar` fijaba `app.actor` DESPUÉS del `setattr` y el `session.execute` auto-vaciaba (autoflush) el `UPDATE` antes del `set_config`. | (1) `0027` §1.5: `COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER)` (corrección in situ, precedente Drift T5-1; la BD de desarrollo `p2` y `p2_test` recibieron el `CREATE OR REPLACE`). (2) `services/catalogo.py`: `_set_actor` ahora ANTES de mutar el ORM. Contrato OpenAPI sin cambios. Prueba `test_RF_007_evento_de_valor_atribuye_al_actor_http` (marcador `xfail` retirado) ✅. |
| **H-2** | BAJA — ambigüedad spec/plan | RF-3 Option-driven | «Modificar Unidad» (`ConfigLocalForm`) no mostraba el Valor Unitario (solo la columna). | Se aplicó la lectura de RF-3 (L3 superior al plan §4.2): `ConfigLocalForm` muestra «Valor Unitario» como texto `MonedaMxn` sin control editable (compatible con C-2: se sigue editando solo desde General/FO). Prueba `ValorUnitarioRbacYUnidad.test.tsx` (marcador `it.fails` retirado) ✅. |

**Observaciones heredadas de T6 (siguen vigentes, fuera del alcance de pruebas):**
La advertencia de chunk > 500 kB de `vite build` se eliminó en T7 con `React.lazy` por página (bundle principal 260 kB); el RBAC visual depende de la prop `esAdmin` (default `true`; el 403 del backend es la autoridad); las secciones FO históricas no se emiten en `/secciones/transferibles` (el historial rotula «Inventario FO» todo `almacen_id` no listado; candidato a RFC con campo de tipo explícito en `MovimientoOut`).

**Observaciones de la ejecución de pruebas:** la BD `p2_test` es compartida; dos ejecuciones simultáneas de `pytest` provocan `DeadlockDetected` en el `TRUNCATE` del fixture `clean_db` y falsos rojos. Ejecutar la suite backend en serie.

---

## 5. Evidencia de ejecución final (2026-10-16, serializada)

| Compuerta | Resultado |
| :-- | :-- |
| `uv run pytest -q -p no:cacheprovider` | **443 passed** (421 base + 22 nuevas; sin `xfail`) |
| `sql_tests` (suite SQL legacy adaptada a 0027) | **25 passed** |
| `uv run mypy app/ tests/` | `Success: no issues found in 84 source files` |
| `npx tsc -b` · `npx eslint .` | 0 errores · 0 errores |
| `npx vitest run` | 43 archivos · **533 passed** (sin `it.fails`) |
| `npx vite build` | OK, **sin advertencias** (mayor chunk 260 kB) |
| `openspec validate --specs --strict` · `openspec validate <cambio> --strict` | 3/3 pasan · válido |

- La BD `p2_test` es compartida: no ejecutar dos corridas de `pytest` simultáneas (deadlock en el `TRUNCATE` de `clean_db`).
- Nota (ledger): los 87 eventos `MATERIAL_MODIFICADO` históricos de `p2` con `usuario='p2admin'` son anteriores al fix de H-1; el ledger es append-only y no se reescribe.
- RF-9 cláusula 3 («todo movimiento **nuevo** con FO referencia el Inventario FO unificado»): **cubierta parcialmente — fe de erratas D-1 aplicada en `spec.md` RF-9**: la UI y el contrato no ofrecen los orígenes legacy (probado); la API conserva por diseño la aceptación de borradores legacy (E8, probado en `test_fo_unificado.py`).
