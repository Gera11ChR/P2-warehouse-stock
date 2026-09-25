# Traceability Matrix — Fase 4 (Requirement-Based Testing & QA)
**Change:** `2026-09-22-frontend-backend-alignment`
**Agents:** @tester, @qa-agent
**Fecha:** 2026-09-25
**Baseline:** EARS.md v1.1 (22 REQ) · tasks.md v1.1 (Nota de ejecución Task 3.10) · Constitution 7.1

Cadena de trazabilidad verificada: `Issue → Proposal Item → EARS REQ → Task → Implementation → Test Artifact`.
Cada uno de los 22 REQ del paquete posee **al menos un artefacto de verificación automatizada** (Constitution 7.1). Los REQ-UI (frontend) están bloqueados por la regla Backend-First y se mapean a sus Tasks F.x; el artefacto de verificación ejecutable hoy es el test backend del contrato subyacente que el frontend consumirá.

## Matriz completa

| # | Issue (issues-breakdown) | Proposal | REQ-ID | Task backend | Task frontend (bloqueado) | Test Artifact(s) — backend |
|---|---|---|---|---|---|---|
| 1 | 1. ID LISTA innecesario | 3.1 | REQ-UI-001 | — | F.1 | `tests/test_catalogo.py::test_patch_con_id_lista_en_body_422` · `tests/test_esquemas.py::TestMetaInvariantes::test_id_lista_ausente_en_todo_schema_entrada` · `tests/test_esquemas.py::TestExtraForbid::test_material_update_rechaza_id_lista` |
| 2 | 1. ID LISTA innecesario · 4. Numeración comienza en 10 | 3.1 | REQ-UI-002 | — | F.1 | `tests/test_busqueda_granel.py::test_rango_ordinal_determinista` (`start_index`) · `tests/test_busqueda_granel.py::test_sin_rangos_ordinales_comportamiento_historico` (`start_index=1`) |
| 3 | 2. Ghost records | 3.2 | REQ-API-001 | 3.1 | — | `tests/test_catalogo.py::test_delete_soft_delete_y_no_reutilizacion` · `tests/test_inventario_equipos.py::test_material_inactivo_no_aparece_en_inventario_equipo` · `tests/test_fibra.py::test_material_soft_deleted_omitido_de_lectura_fibra` |
| 4 | 2. Ghost records | 3.2 | REQ-UI-003 | — | F.2 | Backend subyacente: `tests/test_catalogo.py::test_delete_soft_delete_y_no_reutilizacion` · `tests/test_inventario_equipos.py::test_material_inactivo_no_aparece_en_inventario_equipo` |
| 5 | 3. Campos bloqueados | 3.3 | REQ-UI-004 | 3.3 · 3.4 | F.3 | `tests/test_ajuste_desde_material.py::test_stock_actual_con_motivo_ajusta_por_delta` · `tests/test_ajuste_desde_material.py::test_stock_actual_sin_motivo_422` · `tests/test_ajuste_desde_material.py::test_edicion_aislada_sku_auditada` |
| 6 | 3. Campos bloqueados | 3.3 | REQ-API-002 | 3.4 | — | `tests/test_ajuste_desde_material.py::test_stock_actual_con_motivo_ajusta_por_delta` (delta 100→60, diferencial −40) |
| 7 | 3. Campos bloqueados | 3.3 | REQ-API-003 | 3.4 · 2.5 | — | `tests/test_ajuste_desde_material.py::test_stock_actual_sin_motivo_422` · `tests/test_ajuste_desde_material.py::test_atomicidad_ajuste_fallido_revierte_edicion` · `tests/test_ajustes.py::test_ajuste_motivo_vacio_422` |
| 8 | 10. Categorías no persisten | 3.6 | REQ-API-004 | 2.1 · 2.2 · 3.2 | — | `tests/test_catalogo.py::test_crear_con_nueva_categoria` · `tests/test_catalogo.py::test_patch_modifica_categoria_persiste` |
| 9 | 10. Categorías no persisten | 3.6 | REQ-API-005 | 2.2 · 3.2 | — | `tests/test_catalogo.py::test_crear_con_nueva_categoria` (`categoria`/`categoria_id` en payload) · `tests/test_catalogo.py::test_patch_modifica_categoria_persiste` |
| 10 | 10. Categorías no persisten | 3.6 | REQ-UI-005 | — | F.4 | Backend subyacente: REQ-API-004/005 artifacts (columna `Categoría` alimentada por el payload) |
| 11 | 8. Descripción en Auditoría | 3.5 | REQ-UI-006 | 3.8 | F.5 | `tests/test_auditoria.py::test_filtro_descripcion_ilike` |
| 12 | 9. Buscador masivo incompleto | 3.5 | REQ-UI-007 | 3.9 | F.6 | `tests/test_busqueda_granel.py` (suite completa: rangos ordinales y de descripción con `start_index`) |
| 13 | 9. Buscador masivo incompleto | 3.5 | REQ-API-006 | 3.9 | — | `tests/test_busqueda_granel.py::test_rango_ordinal_determinista` · `::test_solo_hasta_numero_lista_limita` ⚠️ · `::test_solo_desde_numero_lista_desplaza` · `::test_rango_invertido_422` · `::test_desde_numero_lista_cero_422` |
| 14 | 9. Buscador masivo incompleto | 3.5 | REQ-API-007 | 3.9 | — | `tests/test_busqueda_granel.py::test_rango_descripcion_lexicografico` · `::test_filtro_descripcion_antes_de_offset` |
| 15 | 8. Descripción en Auditoría | 3.5 | REQ-API-008 | 3.8 | — | `tests/test_auditoria.py::test_payload_evento_con_datos_legibles_material` · `::test_material_soft_deleted_sigue_visible_en_auditoria` |
| 16 | Condición vinculante (gobernanza Fase 0) | 3.7.4 | REQ-API-009 | 3.10 (nota de ejecución) | — | `tests/test_teams.py` · `tests/test_devol.py` · `tests/test_cancelaciones.py` · `tests/test_e2e_flujo.py` (lógica de movimientos intacta; aserciones de presentación migradas al contrato autónomo) |
| 17 | 5. Modelo sparse Equipos · 7. Equipos nacen con inventario | 3.4 | REQ-DOMAIN-001 | 2.3 · 3.5 | — | `tests/test_inventario_equipos.py::test_equipo_nuevo_inventario_vacio_200` · `::test_sin_registro_fisico_no_aparece` · `tests/test_equipos.py::test_equipo_nuevo_inventario_vacio_200` |
| 18 | 5. Modelo sparse Equipos · 7. Equipos nacen con inventario | 3.4 | REQ-DOMAIN-002 | 2.3 · 3.5 · 3.6 | — | `tests/test_inventario_equipos.py::test_con_stock_real` (`ultimo_movimiento_id`) · `tests/test_teams.py::test_teams_cantidad_exacta_luego_devol_total_elimina_fila` · `tests/test_devol.py::test_devol_exitoso` · `tests/test_e2e_flujo.py::test_flujo_completo_11_pasos` (pasos 6-7) · `tests/test_equipos.py::test_inventario_tras_teams_con_trazabilidad` |
| 19 | 6. FO inventarios independientes | 3.4 | REQ-DOMAIN-003 | 2.4 · 3.7 | — | `tests/test_fibra.py::test_modulos_independientes_sin_cruce` · `::test_carga_inicial_fibra_ok_y_lectura_esquema_estandar` · `tests/test_inventario_equipos.py::test_secciones_solo_general_activa` |
| 20 | 6. FO inventarios independientes | 3.4 | REQ-DOMAIN-004 | 2.4 · 3.7 | F.7 | `tests/test_fibra.py::test_carga_inicial_fibra_ok_y_lectura_esquema_estandar` (campos CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK) |
| 21 | 6. FO inventarios independientes | 3.4 | REQ-DOMAIN-005 | 2.4 · 3.7 | — | `tests/test_fibra.py::test_carga_inicial_fibra_ok_y_lectura_esquema_estandar` (métrica gobernada por `u_m` del catálogo) |
| 22 | 6. FO inventarios independientes | 3.4 | REQ-DOMAIN-006 | 2.4 | — | `tests/test_inventario_equipos.py::test_secciones_solo_general_activa` (secciones FO soft-inactivas) · verificación estructural: `alembic upgrade head` en `tests/conftest.py::pytest_configure` aplica 0012 (DROP `fiber_variants`, `team_inventory`, vista sparse) |

## Notas de cobertura

* ✅ `test_solo_hasta_numero_lista_limita` verifica el **DEFECT-1** ya CERRADO (ver `qa-report.md` §4): con solo `hasta_numero_lista` el servicio `app/services/catalogo.py` aplica `LIMIT = Y` con `desde` implícito = 1, cumpliendo el contrato ordinal de REQ-API-006.
* Los 7 REQ-UI (001-007) permanecen **bloqueados** por la regla Backend-First (SDD v7.1) y se mapean a sus Tasks F.x. Su verificación ejecutable actual es el test del contrato backend subyacente (columna "Test Artifact(s) — backend"); la verificación frontend formal se ejecutará en la Fase F una vez aprobadas las Fases 1–5 del backend.
* REQ-API-009: la interpretación vinculante de la Nota de ejecución (Task 3.10) es que la lógica de movimientos permanece intacta y las aserciones de presentación sparse se migran al contrato autónomo `GET /api/v1/equipos/{id}/inventario` — migración ejecutada en esta fase (ver `qa-report.md` §3).
* Cobertura total: **22/22 REQ con ≥1 artefacto** (Constitution 7.1 ✓). Suites nuevas creadas en Fase 4: `test_fibra.py`, `test_busqueda_granel.py`, `test_ajuste_desde_material.py`, `test_inventario_equipos.py` (renombrado desde `test_sparse_inventario.py`).
