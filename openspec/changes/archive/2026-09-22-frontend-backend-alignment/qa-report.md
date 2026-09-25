# QA Report — Fase 4 (Requirement-Based Testing & QA)
**Change:** `2026-09-22-frontend-backend-alignment`
**Agents:** @tester, @qa-agent
**Fecha:** 2026-09-25
**Alcance de escritura:** `backend/tests/**` y este reporte + `traceability-matrix.md`. **Cero modificaciones** en `backend/app/**`, `backend/alembic/**`, `backend/db/**`, `frontend/**`, `openspec/specs/**` (no leído ni tocado).

---

## 1. Resumen de ejecución

| Comando | Resultado |
|---|---|
| `pytest` (suite completa, receta de entorno Fase 4 sobre `p2_test`, `alembic upgrade head` → cadena 0001–0013) | **129 passed** (100 %) — tras cierre de DEFECT-1 en el mismo ciclo (ver §4) |
| `.venv/bin/python -m mypy app` | ✅ **0 errores** — `Success: no issues found in 38 source files` |
| `.venv/bin/python -m mypy tests` | ✅ **0 errores** — `Success: no issues found in 18 source files` (el config lo permite y se ejecutó) |
| `openspec validate "2026-09-22-frontend-backend-alignment" --strict --no-interactive` | ✅ **Change is valid** |

**Receta de entorno** (nunca se imprimen credenciales): `dotenv` carga `backend/.env`; la URL de `p2_test` se construye con `make_url(...).set(database="p2_test")`; `P2_ADMIN_DATABASE_URL` apunta a `p2` con `PGPASSWORD` inyectado vía entorno.

**Estado de entrada (baseline):** la suite NO podía arrancar — `INTERNALERROR` en `tests/conftest.py::_ensure_test_database`: el hack `ADMIN_DB_URL.replace("/p2", "/p2_test")` corrompía la URL (`p2admin` → `p2_testadmin`, autenticación fallida). Baseline efectiva: **0 tests ejecutados**.

**Estado de salida:** 129 tests recolectados; **129 verdes (100 %)** tras cierre de DEFECT-1.

---

## 2. Totales por suite

| Suite | Antes | Después | Observaciones |
|---|---|---|---|
| `test_ajuste_desde_material.py` | — (nueva) | 6/6 | REQ-API-002/003, REQ-UI-004 |
| `test_ajustes.py` | 8 | 8/8 | Sin cambios (contrato verde) |
| `test_auditoria.py` | 4 | 7/7 | +3 (REQ-API-008, REQ-UI-006) |
| `test_busqueda_granel.py` | — (nueva) | 8/8 | DEFECT-1 cerrado en el ciclo |
| `test_cancelaciones.py` | 7 | 7/7 | Aserciones de presentación migradas |
| `test_catalogo.py` | 10 | 11/11 | +1 (PATCH categoría, REQ-API-004) |
| `test_devol.py` | 4 | 4/4 | Aserciones migradas |
| `test_e2e_flujo.py` | 1 | 1/1 | Pasos 6-7 migrados |
| `test_equipos.py` | 5 | 8/8 | +3 (contrato autónomo) |
| `test_esquemas.py` | 32 | 32/32 | Sin cambios |
| `test_fibra.py` | — (nueva) | 11/11 | REQ-DOMAIN-003/004/005/006, REQ-API-001 |
| `test_inventario_equipos.py` | 5 (como `test_sparse_inventario.py`) | 7/7 | Renombrada (`git mv`) + reescrita al contrato autónomo |
| `test_seguridad.py` | 5 | 7/7 | +2 (RBAC admin vía tabla `administradores`) |
| `test_teams.py` | 12 | 12/12 | Aserciones migradas; 1 test renombrado/reescrito |
| **Total** | **93 (0 ejecutables)** | **129 (129 ✅)** | |

---

## 3. Defectos encontrados y RESUELTOS (capa de tests — Fase 4)

1. **Bootstrap roto (`tests/conftest.py`)** — el `.replace("/p2", "/p2_test")` corrompía URLs cuyo usuario empieza por "p2". **Resuelto**: construcción correcta con `make_url(ADMIN_DB_URL).set(database="p2_test").render_as_string(hide_password=False)`. Además: `inventario_fibra` añadida a `TABLAS_DOMINIO` (TRUNCATE/RESTART IDENTITY entre tests) y `SECCIONES_SEMILLA` reducida a solo `("Inventario General", "GENERAL")` (FO deprecadas por 0012). Se añadió `administradores` a `TABLAS_DOMINIO` para aislamiento determinista de los tests RBAC-admin.
2. **Aserciones de presentación del Modelo Sparse (migración vinculante de la Nota de ejecución Task 3.10)** — migradas al contrato autónomo `GET /api/v1/equipos/{equipo_id}/inventario` (clave `material_id`, cero filas fantasma):
   * `test_teams.py::test_teams_exitoso_descuenta_y_suma` → `filas[material_id]["stock_actual"] == 40`.
   * `test_teams_cantidad_exacta_deja_fila_viva_con_cero` → renombrado `test_teams_cantidad_exacta_luego_devol_total_elimina_fila`: tras DEVOL total la fila **desaparece** (`material_id not in inventario_equipo`).
   * `test_devol.py::test_devol_exitoso` → tras DEVOL total, `not in`; `test_devol_bloqueado_por_falta_stock_400` → fila viva con stock 10 vía clave `material_id`.
   * `test_e2e_flujo.py` pasos 6-7 → tras cancelar TEAMS la fila desaparece; material sin movimientos NO aparece. Comentarios "sparse" eliminados.
   * `test_cancelaciones.py` → `test_cancelar_teams_restituye_exacto` (fila desaparece) y `test_cancelar_devol_restituye_inverso` (`filas[material_id]["stock_actual"] == 40`).
   * `test_sparse_inventario.py` → **renombrada** (`git mv`) a `tests/test_inventario_equipos.py` y reescrita: `test_sin_registro_fisico_no_aparece`, `test_con_stock_real` (con `ultimo_movimiento_id`), `test_secciones_solo_general_activa`, `test_stock_seccion_inexistente_404`, `test_alerta_stock_bandera`, `test_material_inactivo_no_aparece_en_inventario_equipo`.
3. **Helper legacy `catalogo_equipo`** → renombrado `inventario_equipo` apuntando al endpoint canónico; imports actualizados en los 5 módulos consumidores; helpers nuevos: `fibra_carga_inicial`, `fibra_ajuste`, `patch_material`.
4. **Expectativa incorrecta en un test nuevo** (`test_rango_descripcion_lexicografico`) — el rango `[B, G]` excluye `Gamma` ("Gamma" > "G"). Corregido en el test; el backend era correcto (no defecto).

---

## 4. Defectos ABIERTOS para @coder (repro exacto)

### DEFECT-1 — `Buscador a granel`: solo `hasta_numero_lista` no aplica LIMIT (REQ-API-006)
* **Severidad:** Media (desviación de contrato ordinal; no corrompe datos).
* **Archivo:** `backend/app/services/catalogo.py` (`listar`, bloque de posicionamiento ordinal, ~líneas 116-125).
* **Comportamiento esperado (contrato REQ-API-006):** con solo `hasta_numero_lista=Y`, `desde` implícito = 1 → `OFFSET=0`, `LIMIT=Y`, `start_index=1`. (Interpretación ratificada: el operador pide "las primeras Y filas".)
* **Comportamiento observado:** cuando `desde_numero_lista is None` y solo `hasta_numero_lista` viene informado, NO se aplicaba `limit(...)` — se devolvían **todas** las filas activas ordenadas.
* **Repro (pytest):** `tests/test_busqueda_granel.py::test_solo_hasta_numero_lista_limita` (5 filas devueltas, esperadas 2).
* **Estado: CERRADO (orquestador, cierre de Fase 4).** Corrección quirúrgica en `backend/app/services/catalogo.py`: rama `elif hasta_numero_lista is not None:` → `stmt.limit(hasta_numero_lista)` (desde implícito = 1). Suite completa re-ejecutada: **129/129 passed**, `mypy app` 0 errores, `mypy tests` 0 errores, `openspec validate --strict` válido.
* **Impacto en DoD:** resuelto. Sin bloqueantes pendientes.

---

## 5. Cobertura REQ

* **22/22 REQ con ≥1 artefacto** de verificación (Constitution 7.1 ✓). Detalle completo en `traceability-matrix.md`.
* REQ-UI-001…007 (7) → Tasks F.1–F.7 (bloqueadas por Backend-First) con test backend del contrato subyacente como artefacto ejecutable actual.
* REQ-API-001…009 (9) y REQ-DOMAIN-001…006 (6) → tests de integración en ejecución real contra PostgreSQL (`p2_test`) con aserción dual (HTTP + estado persistido) y auditoría verificada vía `auditoria_eventos`.

---

## 6. Evidencia de invariantes constitucionales en la suite

| Invariante | Verificación en tests |
|---|---|
| 2.1 Non-Negative Balance | `test_stock_insuficiente_400_con_mensaje_pg`, `test_devol_bloqueado_por_falta_stock_400`, `test_ajuste_fibra_nuevo_stock_negativo_422`, CHECKs DB en 0012 |
| 2.3 State Serialization | `test_concurrencia_dos_teams_serializados` (FOR UPDATE; exactamente un 200 y un 400) |
| 2.4 Immutable Ledger | `test_ajuste_con_diferencial_auditado`, `test_ajuste_fibra_ok_con_motivo_y_diferencial_auditado`, `test_material_soft_deleted_sigue_visible_en_auditoria` |
| 3.1/3.2 Default-Deny & Scope | `test_actor_sin_scope_403_escritura`, `test_actor_sin_scope_sin_admin_sigue_403`, `test_admin_registrado_pase_directo_sin_scope` |
| 4.1 Atomicity | `test_atomicidad_ajuste_fallido_revierte_edicion` (descripción NO persiste si el ajuste falla) |
| 6.2 Audit Events | `test_patch_catalogo_genera_auditoria_trigger`, `test_edicion_aislada_sku_auditada` (migración 0013) |

---

## 7. Veredicto de ship-readiness (backend)

**SHIP-READY (tras cierre de DEFECT-1 en el mismo ciclo de Fase 4).**

* pytest: **129/129 verdes (100%)** tras la corrección de DEFECT-1 (rama `hasta_numero_lista` sin `desde`).
* mypy (`app` y `tests`): 0 errores.
* `openspec validate --strict`: válido.
* Sin regresiones TEAMS/DEVOL (REQ-API-009). Listo para el Cierre de Backend (Fase 5).
* Sin regresiones: TEAMS/DEVOL/cancelaciones/e2e verdes tras la migración de aserciones de presentación (REQ-API-009 cumplida en su interpretación vinculante).
* Pendiente para DoD completo: (1) cerrar DEFECT-1 en pase de @coder y re-ejecutar Fase 4; (2) Fases F (frontend) y 5 (integración/archivo) tras la aprobación de las Fases 1–5 del backend.

---

## 8. Archivos modificados / creados

**Modificados (backend/tests/**):** `conftest.py`, `helpers/fabrica.py`, `test_teams.py`, `test_devol.py`, `test_e2e_flujo.py`, `test_cancelaciones.py`, `test_catalogo.py`, `test_auditoria.py`, `test_equipos.py`, `test_seguridad.py`.

**Renombrado:** `test_sparse_inventario.py` → `test_inventario_equipos.py` (`git mv` + reescritura).

**Creados (backend/tests/**):** `test_fibra.py`, `test_busqueda_granel.py`, `test_ajuste_desde_material.py`.

**Creados (entregables del paquete):** `openspec/changes/2026-09-22-frontend-backend-alignment/traceability-matrix.md` (este informe complementa), `qa-report.md`.

**Sin tocar:** `backend/app/**`, `backend/alembic/**`, `backend/db/**`, `frontend/**`, `openspec/specs/**`.
