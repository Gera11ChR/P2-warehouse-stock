# Refactoring Report — Fase 3.5 (Refactor & Dead Code Audit)
**Change:** `2026-09-22-frontend-backend-alignment`
**Agent:** `@auditor`
**Fecha:** 2026-09-25
**Alcance de escritura:** `backend/app/services/`, `backend/app/api/v1/inventario.py` y este reporte. Nada más fue modificado.

---

## 1. Resumen ejecutivo

La Fase 3.5 cierra el olor legacy del **Modelo Sparse** a nivel de código de aplicación. La vista `vw_inventario_equipo_completo` ya fue eliminada de la BD (migración 0012), el modelo ORM `app/models/vistas.py` fue eliminado por `@coder` y el endpoint de lectura de equipos ya consulta `inventario_equipos` directamente. Quedaba el nombre de módulo `sparse_inventory`, que ya no implementaba el Modelo Sparse.

**Acción principal:** renombrado `app/services/sparse_inventory.py` → `app/services/inventario.py` con `git mv` (historial conservado), actualización de su docstring al modelo actual (lecturas del inventario central / Inventario General) y actualización del único importador (`app/api/v1/inventario.py`).

**Resultado:** cero cambios de comportamiento, cero cambios de contrato HTTP, cero referencias activas a "sparse" en `app/` (solo menciones históricas en docstrings que documentan la deprecación). `import app.main` OK, `mypy` 0 errores.

**Hallazgos de auditoría (sin acción destructiva):** 1 modelo ORM huérfano (`HistorialImportacion`), 2 imports no utilizados (severidad baja) y 4 rutas legacy de código identificadas (parámetros `sku`/`id_lista` del Buscador, búsqueda por `id_lista` cast, tipos de sección FO legacy en el CHECK de `secciones`). Todos quedan documentados como pendientes no bloqueantes para Fase 5.

---

## 2. Cambios realizados

### 2.1. Renombrado de módulo (historial git conservado)

| Antes | Después | Método |
|---|---|---|
| `backend/app/services/sparse_inventory.py` | `backend/app/services/inventario.py` | `git mv` |

Confirmación de git: `RM backend/app/services/sparse_inventory.py -> backend/app/services/inventario.py` (renombrado + modificado).

### 2.2. Docstring del módulo (`services/inventario.py`)

Redacción anterior: describía el módulo como "Lecturas de inventario" con una nota de deprecación del Modelo Sparse como si aún fuera su responsabilidad central.

Redacción nueva: el docstring ahora declara como ámbito **único** del módulo las lecturas del **inventario central (Inventario General)**: maestro de secciones (`secciones`) y stock por sección (`inventario_almacen`, JOIN al catálogo activo con filtro estricto `is_active` — REQ-API-001). La mención del Modelo Sparse se conserva exclusivamente como **nota histórica** (migración 0012, REQ-DOMAIN-001/002) que explica el cambio de nombre del módulo y dónde viven hoy las lecturas de equipos (`api/v1/equipos.py`) y Fibra Óptica (`api/v1/fibra.py`).

### 2.3. Actualización del importador único (`api/v1/inventario.py`)

| Línea | Antes | Después |
|---|---|---|
| 10 | `from app.services import sparse_inventory` | `from app.services import inventario` |
| 22 | `sparse_inventory.listar_secciones(session)` | `inventario.listar_secciones(session)` |
| 29 | `sparse_inventory.obtener_seccion(session, almacen_id)` | `inventario.obtener_seccion(session, almacen_id)` |
| 36 | `sparse_inventory.stock_seccion(session, almacen_id)` | `inventario.stock_seccion(session, almacen_id)` |

Rutas HTTP, prefijos, payloads y lógica: **idénticos**. El renombrado es interno de `app/` y no altera el contrato API.

### 2.4. Revisión de docstrings en modelos/esquemas (sin cambios necesarios)

Se revisaron `models/inventario.py` (`InventarioEquipo`) y `schemas/inventario.py` (`InventarioEquipoOut`, `SeccionStockOut`, `FibraStockOut`):

- `models/inventario.py:70-78` — `InventarioEquipo` ya describe el **modelo autónomo** ("inicializada VACÍA al crear el equipo… poblada EXCLUSIVAMENTE por movimientos TEAMS/DEVOL auditados") y menciona el Sparse únicamente como deprecado. **Conforme, sin cambios.**
- `schemas/inventario.py:27-36` — `InventarioEquipoOut` ya describe el contrato autónomo (filas físicas, cero fantasmas, trazabilidad `ultimo_movimiento_id`) con la vista sparse como "deprecada". **Conforme, sin cambios.**
- `schemas/inventario.py:56-60` — `FibraStockOut` documenta el esquema estándar U.M.-driven y el deprecado `fiber_variants`. **Conforme, sin cambios.**

Ningún docstring presenta el Modelo Sparse como vigente; todos los que lo mencionan lo hacen en contexto histórico de deprecación. No se requirió corrección de redacción adicional.

---

## 3. Código muerto / obsoleto identificado

> Regla de Fase 3.5 respetada: solo se **identifican** hallazgos; no se eliminó código más allá del renombrado aprobado. Las eliminaciones quedan como recomendaciones para Fase 5.

| # | Archivo | Hallazgo | Severidad | Recomendación |
|---|---|---|---|---|
| 1 | `backend/app/models/importacion.py` | Modelo ORM **huérfano** `HistorialImportacion`. Cero referencias en `api/`, `services/`, `schemas/` y `tests/`. La tabla `historial_importaciones` existe en BD (migración 0010) pero **ningún endpoint de ingesta CSV/XLSX/XML la escribe**. No existe schema `importacion` | MEDIA | Evaluar en Fase 5: (a) implementar el endpoint de ingesta masiva que exige el vector de trazabilidad (§6 del flujo, "Bulk Uploads") y conectar el modelo, o (b) deprecar modelo + tabla en una migración nueva. No tocar en Fase 3.5 |
| 2 | `backend/app/models/movimiento.py` | Import no utilizado: `Boolean` (detectado por análisis AST; ruff/pyflakes no disponibles en el venv) | BAJA | Eliminar en Fase 5 |
| 3 | `backend/app/models/scope.py` | Import no utilizado: `Integer` (ídem) | BAJA | Eliminar en Fase 5 |

**Falsos positivos descartados:** los imports "no usados" de `models/__init__.py` y `schemas/__init__.py` son re-exportaciones intencionales (API pública del paquete), no código muerto.

**Evidencia de limpieza ya realizada por @coder (confirmada, sin acción de Fase 3.5):** `backend/app/models/vistas.py` aparece eliminado (`D` en git status) — el modelo de la vista sparse ya no existe en el ORM.

---

## 4. Rutas legacy detectadas

Rutas/código vivo que conserva nomenclatura o semántica de la era pre-alineación (migraciones 0001–0008, `skus/warehouses/fiber_variants/team_inventory`). **No se modifican en Fase 3.5** porque alterarlas cambiaría el contrato API; requieren paquete OpenSpec propio en Fase 5.

| # | Ubicación | Ruta legacy | Contexto / por qué es legacy | Recomendación (Fase 5) |
|---|---|---|---|---|
| L1 | `api/v1/catalog.py:67-68,84-85` + `services/catalogo.py:70-71,104-107` | Parámetros de query `desde_sku` / `hasta_sku` | Nomenclatura `sku` de la era legacy. El contrato ratificado del Buscador a granel es **número de lista + descripción** (REQ-API-006/007); los rangos por SKU no figuran en el contrato actual | Deprecar con cambio de contrato explícito (nuevo OpenSpec): retirar params si el frontend alineado no los consume |
| L2 | `api/v1/catalog.py:65-66,82-83` + `services/catalogo.py:68-69,100-103` | Parámetros `desde_id_lista` / `hasta_id_lista` | Filtrado por `ID Lista` visible, deprecado por REQ-UI-001 (abstracción de identificador: el operador ya no ve ni usa `ID Lista`) | Ídem L1: reemplazo ya existe (`desde_numero_lista`/`hasta_numero_lista`) |
| L3 | `services/catalogo.py:95` | `CatalogoMaterial.id_lista.cast(String).ilike(patron)` en el filtro `buscar` | Búsqueda por ID Lista dentro del buscador libre; legado de identificadores visibles (REQ-UI-001/007 orientan la búsqueda a descripción) | Evaluar remoción de la rama `id_lista` del `buscar` en Fase 5 (cambio de comportamiento de búsqueda → requiere paquete) |
| L4 | `models/inventario.py:9-19` (CHECK `ck_secciones_tipo`) + columna `Seccion.tipo` | Valores legacy `FO_PAQUETE` / `FO_EN_USO` en el maestro de secciones | FO dejó de ser sección del inventario central (REQ-DOMAIN-003): `inventario_fibra` es la raíz física. Ningún código `app/` filtra por esos tipos (verificado por grep) | Tightening DDL en migración futura (dominio `@dba-guard`): restringir CHECK a `GENERAL` y/o deprecar `tipo`. NO interfiere con la migración 0013 en curso |
| L5 | `backend/db/ddl.sql:369-373` | NOTA textual sobre la deprecación de la vista sparse con instrucción `DROP VIEW` | Snapshot DDL conserva solo una nota informativa (no una definición viva de la vista). Fuera del alcance de Fase 3.5 (`backend/db/**` prohibido) | Limpieza cosmética por `@dba-guard` al cerrar el paquete (Fase 5) |

**Menciones legacy en tests (fuera de alcance, dominio Fase 4):** `backend/tests/test_e2e_flujo.py:5,74`, `helpers/fabrica.py:189`, `conftest.py:121` referencian el contrato de presentación sparse en docstrings/helpers. `tasks.md` ya documenta la migración de esas aserciones a Fase 4; no se tocan en Fase 3.5.

---

## 5. Verificación ejecutada

| # | Comando | Resultado |
|---|---|---|
| V1 | `cd /home/gerar/P2/backend && .venv/bin/python -c "import app.main"` | ✅ **OK** — `IMPORT OK — routes: 12` (sin errores de importación) |
| V2 | `.venv/bin/python -m mypy app` | ✅ **0 errores** — `Success: no issues found in 38 source files` (exit 0) |
| V3 | `grep -rin "sparse" backend/app/ --include="*.py"` | ✅ Solo 4 menciones históricas en docstrings (ver justificación abajo) |
| V4 | `grep -rn "sparse_inventory" backend/ --include="*.py"` | ✅ Única coincidencia: la nota histórica del docstring de `services/inventario.py:9`. Ningún import activo |
| V5 | Detector AST de imports no utilizados (stdlib, sin instalar nada) | ✅ Hallazgos 2-3 de la tabla §3; re-exportaciones de `__init__.py` descartadas como falsos positivos |
| V6 | Suite completa (pytest) | ⏭️ **No ejecutada** — los tests están en migración por Fase 4 (instrucción explícita). El cambio es interno de `app/` (sin alterar rutas HTTP) y `import app.main` + `mypy` cubren el riesgo de integración |

**Justificación de cada mención "sparse" restante en `app/` (todas históricas, ninguna activa):**

1. `api/v1/equipos.py:100` — docstring: *"Query directa a `inventario_equipos` (la vista sparse ya no existe)"* → contexto histórico del cambio de modelo. ✅
2. `services/inventario.py:9-10` — nota histórica del renombrado: *"este módulo se llamaba `sparse_inventory`… El Modelo Sparse… quedaron deprecados con la migración 0012"*. ✅
3. `schemas/inventario.py:30` — *"Reemplaza a `CatalogoEquipoOut` y a la vista sparse deprecada"* → histórico. ✅
4. `models/inventario.py:73` — *"El Modelo Sparse y la vista `vw_inventario_equipo_completo` quedaron deprecados"* → histórico. ✅

No existen referencias funcionales (imports, llamadas, atributos) a `sparse_inventory` ni a la vista sparse en `backend/app/`.

---

## 6. Pendientes recomendados para Fase 5 (nada bloqueante)

1. **Decisión sobre `HistorialImportacion`** (hallazgo §3.1): implementar ingesta masiva con trazabilidad en `historial_importaciones` o deprecar modelo+tabla. Requiere paquete OpenSpec nuevo si se implementa funcionalidad.
2. **Limpieza de imports no utilizados** (`models/movimiento.py: Boolean`, `models/scope.py: Integer`).
3. **Deprecación de params legacy del Buscador** (`desde_sku/hasta_sku`, `desde_id_lista/hasta_id_lista`, rama `id_lista` en `buscar`) — solo tras confirmar que el frontend alineado (Fase F) no los consume; cambio de contrato → paquete OpenSpec propio.
4. **Tightening DDL de `secciones.tipo`** (retirar `FO_PAQUETE`/`FO_EN_USO` del CHECK) — dominio `@dba-guard`, posterior a la migración 0013 en curso.
5. **Limpieza cosmética del snapshot `backend/db/ddl.sql`** (nota de deprecación de la vista sparse) al archivar el paquete.
6. **Migración de aserciones de presentación sparse en tests** — ya planificada para Fase 4 en `tasks.md` (nota de ejecución de Task 3.10); fuera del alcance de Fase 3.5.

---

## 7. Archivos modificados / renombrados

| Archivo | Operación |
|---|---|
| `backend/app/services/sparse_inventory.py` → `backend/app/services/inventario.py` | Renombrado (`git mv`) + docstring actualizado |
| `backend/app/api/v1/inventario.py` | Import y 3 usos actualizados (`sparse_inventory` → `inventario`) |
| `openspec/changes/2026-09-22-frontend-backend-alignment/refactoring-report.md` | **NUEVO** — entregable oficial de Fase 3.5 |

**Sin cambios** en: `backend/tests/**`, `backend/alembic/**`, `backend/db/**`, `frontend/**`, `openspec/specs/**` (no leído ni tocado).

**Exit criteria Fase 3.5:** ✅ No queda implementación obsoleta relacionada con el comportamiento reemplazado en `backend/app/` — el nombre `sparse` solo sobrevive como documentación histórica de la transición de modelo.
