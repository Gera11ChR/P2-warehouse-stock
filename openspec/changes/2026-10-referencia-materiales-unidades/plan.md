# Plan técnico — ETAPA 3/3: REFERENCIA DE MATERIALES POR UNIDAD

**Paquete:** `2026-10-referencia-materiales-unidades` · **Fase SDD:** 5 (Planificación) · **Estado:** redactado, pendiente de aprobación del humano y de la clarificación de la Fase 4 (T1).
Separación spec/diseño (Constitución §1.2): este documento define el *cómo*; el *qué* está en `spec.md` (`REQ-REF-001..018`). Contrato de API de referencia (borrador hasta T7): `openapi.snapshot.json`.

## 1. Fases operativas del paquete

| Fase SDD | Contenido en este paquete | Tareas |
| --- | --- | --- |
| 1. Constitución | Sin enmiendas (proposal §10) | — |
| 2. Contexto agente | `.agents.md` vigente; el paquete activo es la única fuente de contexto | — |
| 3. Especificación | `proposal.md`, `spec.md` | (redactados) |
| 4. Clarificación | C-1..C-13 de `spec.md` §8 | T1 |
| 5. Planificación | Este documento | (redactado) |
| 6. Tareas | `tasks.md` | (redactado) |
| 7. Implementación | **Backend-First:** DB (T2-T3) → servicio (T4) → router (T5) → pruebas API (T6) → congelación del contrato (T7) → **Frontend:** estado (T8) → UI y verificación visual (T9) → pruebas de frontend (T10) | T2-T10 |
| 8. Validación y auditoría | Drift Report, trazabilidad, regresión, aprobaciones múltiples | T11 |
| 9. Evolución | Promoción a specs maestras y archivado | T12 |

## 2. Decisiones de diseño

Las decisiones D-1..D-4 (acordadas) y D-5..D-14 (propuestas) están en `proposal.md` §6-§7. Decisiones técnicas adicionales:

| ID | Decisión | Razón |
| --- | --- | --- |
| P-1 | Router nuevo `app/api/v1/referencia.py` (prefijo `/equipos`) y servicio `app/services/referencia.py`; modelo `app/models/referencia.py`; esquemas `app/schemas/referencia.py` | Aísla el paquete; sin tocar `equipos.py` ni sus servicios |
| P-2 | Clave primaria compuesta `(equipo_id, material_id)`; el identificador de una línea en la API es `material_id` | Unicidad estructural; sin id sustituto |
| P-3 | Alta masiva en una sola transacción: validar todo → insertar todo; la carrera se resuelve con la PK y se traduce a 409 | Constitución §4.1, §5.3 y §2.3 |
| P-4 | Auditoría por trigger `AFTER INSERT OR UPDATE OR DELETE` (patrón `fn_auditar_equipo_material_config`) con `app.actor` fijado por el backend | Constitución §6.2; misma transacción |
| P-5 | Sin Stored Function de negocio: la tabla no es de stock ni ledger | D-6 |
| P-6 | Los errores de negocio usan `BusinessRuleError(code, message, coordinates, status_code)`; `coordinates` identifica la línea (`{"linea": i, "material_id": n}`) | Patrón vigente de errores canónicos |
| P-7 | Frontend: selector de material como `<select>` nativo con campo de filtro de texto (no ARIA combobox) | Accesible, robusto en móvil, sin dependencias nuevas |
| P-8 | Datos del selector dependiente desde servicios existentes: «Inventario General» = secciones `GENERAL` activas (`listSecciones` + `stockSeccion`, sin duplicar `material_id`); «Inventario FO» = `listFibraStock` | Sin cambios de contrato en inventarios |

## 3. Datos (Fase 7, T2-T3)

### 3.1 DDL (migración `0030_referencia_materiales_unidad.py`, `down_revision = "0029"`)

```sql
CREATE TABLE referencia_materiales (
    equipo_id        INTEGER NOT NULL REFERENCES equipos(equipo_id) ON DELETE RESTRICT,
    material_id      INTEGER NOT NULL REFERENCES catalogo_materiales(id_lista) ON DELETE RESTRICT,
    cantidad_semanal NUMERIC(12,3) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_referencia_materiales PRIMARY KEY (equipo_id, material_id),
    CONSTRAINT ck_referencia_cantidad_positiva CHECK (cantidad_semanal > 0)
);
```

- Sin DDL sobre tablas existentes. `ON DELETE RESTRICT`: ni una Unidad ni un material con Referencia pueden borrarse físicamente (ambos ya son soft-delete).
- Índice adicional innecesario: la PK cubre las consultas por `equipo_id`.
- `downgrade()`: `DROP TRIGGER`, `DROP FUNCTION`, `DROP TABLE` (solo objetos del paquete; los eventos de auditoría ya escritos se conservan).

### 3.2 Trigger de auditoría

`fn_auditar_referencia_materiales()` / `tg_auditar_referencia_materiales` (`AFTER INSERT OR UPDATE OR DELETE ... FOR EACH ROW`), escribe en `auditoria_eventos (usuario, tipo_accion, material_id, resultado, detalles)`:

| Operación | `tipo_accion` | `detalles` |
| --- | --- | --- |
| INSERT | `REFERENCIA_LINEA_CREADA` | `{equipo_id, modulo:'REFERENCIA', accion:'CREAR', valores_anteriores:null, valores_nuevos:{cantidad_semanal}}` |
| UPDATE | `REFERENCIA_LINEA_MODIFICADA` | `{..., accion:'MODIFICAR', valores_anteriores:{cantidad_semanal}, valores_nuevos:{cantidad_semanal}}` |
| DELETE | `REFERENCIA_LINEA_ELIMINADA` | `{..., accion:'ELIMINAR', valores_anteriores:{cantidad_semanal}, valores_nuevos:null}` |

- `usuario = COALESCE(current_setting('app.actor', true), CURRENT_USER)`, `resultado = 'EXITO'`. `tipo_accion` es `varchar(50)` sin CHECK de enumeración: no se amplía el esquema.
- Un `UPDATE` que no cambia la cantidad no emite evento: la función devuelve `NEW` sin insertar cuando `TG_OP = 'UPDATE'` y `OLD.cantidad_semanal IS NOT DISTINCT FROM NEW.cantidad_semanal` (no se usa `WHEN (OLD…)` porque el trigger cubre también INSERT y DELETE). La función retorna `OLD` en DELETE y `NEW` en los demás casos.

### 3.3 Infraestructura de pruebas

- Añadir `referencia_materiales` a las listas `TRUNCATE` de `backend/tests/conftest.py` y `backend/sql_tests/conftest.py` (único cambio permitido a esos archivos; antes de las tablas padre).
- Ajustar solo los asserts de «cabeza de migración» de `test_migracion_0029.py`/`0028` si dependen de `head == "0029"` (cambio mínimo, registrado en `tasks.md`).
- `test_migracion_0030.py` con `tests/helpers/migraciones.py` (`upgrade → downgrade → upgrade`, PK, FK, CHECK, trigger, eventos preservados, ninguna tabla preexistente modificada).
- `sql_tests/test_fase_referencia.py`: PK/FK/CHECK, trigger de auditoría (3 operaciones, `app.actor`, sin evento si no cambia la cantidad), `ON DELETE RESTRICT`, que no se altere ninguna tabla de negocio.

## 4. Backend (Fase 7, T4-T5)

### 4.1 Contrato (resumen; detalle en `openapi.snapshot.json`)

| Método y ruta | Cuerpo | Éxito | Errores |
| --- | --- | --- | --- |
| `GET /api/v1/equipos/{equipo_id}/referencia` | — | 200 `ReferenciaListOut {items, total}` | 400, 403, 404, 422 |
| `POST /api/v1/equipos/{equipo_id}/referencia` | `ReferenciaCreate {lineas:[{material_id, cantidad_semanal}]}` (1..50) | 201 `ReferenciaListOut` (líneas creadas) | 400, 403, 404, 409, 422 |
| `PATCH /api/v1/equipos/{equipo_id}/referencia/{material_id}` | `ReferenciaUpdate {cantidad_semanal}` | 200 `ReferenciaLineaOut` | 400, 403, 404, 422 |
| `DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id}` | — | 204 | 400, 403, 404, 422 |

- `ReferenciaLineaOut`: `material_id`, `codigo` (nullable), `descripcion`, `u_m` (nullable), `cantidad_semanal` (number). Todos los modelos de entrada con `extra="forbid"`; `cantidad_semanal` reutiliza `CantidadMovimiento` (`gt=0`, 12 dígitos, 3 decimales).
- Códigos de error de negocio: `MATERIAL_NO_ENCONTRADO` (404), `REFERENCIA_NO_ENCONTRADA` (404), `REFERENCIA_DUPLICADA` (409), `REFERENCIA_LINEA_DUPLICADA` (422).

### 4.2 Flujo del router (orden de precedencia, REQ-REF-010)

1. Validación Pydantic (cuerpo, tipos, `X-Actor`, `equipo_id` > 0) → 422; identificadores fuera de INT4 → 400 `NUMERIC_OUT_OF_RANGE`.
2. La Unidad existe → si no, 404 (antes que 403); en escrituras debe estar activa → si no, 404.
3. `assert_equipo_access` → 403.
4. Lectura: consulta tipada con JOIN al catálogo (`is_active`) y orden `descripcion ASC, material_id ASC`; `total` = número de ítems listados.
5. Alta: `session.begin()`; fijar `app.actor`; verificar que los `material_id` existan y estén activos (404 con `coordinates` de la línea) → rechazar repetidos del payload (422) y los ya presentes (409) → insertar todas las líneas; un `IntegrityError` por carrera se traduce a 409 con rollback completo. El trigger audita en la misma transacción.
6. Modificación/eliminación: `SELECT ... FOR UPDATE` de la línea (serializa con una modificación concurrente); 404 `REFERENCIA_NO_ENCONTRADA` si no existe; `UPDATE` con `updated_at = CURRENT_TIMESTAMP` o `DELETE`.

### 4.3 Seguridad (`@sec-ops`, T5)

Default-deny con `assert_authenticated` más `assert_equipo_access`; `extra="forbid"`; parámetros enlazados (sin SQL concatenado); sin eco de detalles SQL; una Unidad ajena no revela la existencia de líneas (403 uniforme tras confirmar que la Unidad existe, como los demás endpoints por Unidad).

### 4.4 Aislamiento

No se modifican `app/api/v1/equipos.py`, `catalog.py`, `inventario.py`, `fibra.py`, `actividades.py`, `reportes*.py` ni sus servicios y modelos. Cambios permitidos fuera de los archivos nuevos: registrar el router en `app/main.py` y las listas `TRUNCATE` de las dos `conftest.py`.

## 5. Congelación del contrato (T7)

`@qa-agent` valida de forma independiente el backend contra `spec.md`, regenera `openapi.snapshot.json` desde `app.openapi()` restringido a las cuatro operaciones y sus esquemas, calcula su sha256, marca `frozen: true` en `.openspec.yaml` y registra el hash. Desde entonces, cualquier cambio de contrato requiere un RFC aprobado.

## 6. Frontend (Fase 7, T8-T10) — solo tras T7

### 6.1 Estado (T8, `@state-agent`)

- Tipos en `types.ts`: `ReferenciaLinea`, `ReferenciaList`, `ReferenciaCreatePayload`, `ReferenciaUpdatePayload` (espejo del contrato congelado).
- Servicio `services/referencia.ts`: `listarReferencia`, `crearReferencia`, `modificarReferencia`, `eliminarReferencia`.
- Claves: `queryKeys.referencia(equipoId)` en `hooks/queryKeys.ts` y su invalidación acotada (REQ-REF-017: solo esa clave).
- Hooks `hooks/useReferencia.ts`: `useReferencia(equipoId, enabled)`, `useCrearReferencia`, `useModificarReferencia`, `useEliminarReferencia` (mutaciones con `pushToast`/`pushError`, sin recalcular nada en el cliente).
- Origen del selector: hooks de solo lectura que reutilizan `listSecciones`/`stockSeccion` y `listFibraStock` (P-8).

### 6.2 Interfaz (T9, `@ui-agent`, `@ux-agent`, `@form-agent`)

| Componente | Responsabilidad |
| --- | --- |
| `InventarioPorEquipos.tsx` (cambio mínimo) | Estado `referenciaAbierta`; botón «Referencia» en el extremo derecho de la barra de subsecciones (solo Consulta y Configuración); cierra el panel al cambiar de Unidad o de subsección sin botón; monta `ReferenciaPanel` |
| `ReferenciaPanel.tsx` (nuevo) | Título «Materiales Referencia», tabla (Descripción, U.M., Cantidad Semanal), estados de carga/error/vacío, modo lectura (Consulta) o con acciones (Configuración) |
| `ReferenciaAgregarForm.tsx` (nuevo) | Origen («Inventario General», «Inventario FO») → `MaterialSelect` dependiente, «Cantidad», papelera por línea, «+ Agregar línea», confirmar; zod con mínimo 1 línea, positivos y sin duplicados; conserva los datos ante rechazo |
| `MaterialSelect.tsx` (nuevo) | Filtro de texto + `<select>` con «Descripción (stock)» en solo lectura; excluye los materiales ya presentes |
| Modificar / Eliminar | Diálogo de edición de la cantidad (mismas reglas que el backend) y `ConfirmDialog` para eliminar |

Reglas de UI: texto «Unidad» e «Inventario FO»; aviso permanente «La cantidad no afecta el inventario»; foco gestionado al abrir/cerrar formulario y diálogos; `aria-expanded` en el botón; tabla con `caption`; contenedor `overflow-x-auto` solo en la tabla (sin desbordar la página).

### 6.3 Verificación visual con Playwright Chromium (Definición de Done de T9)

Script headless ad hoc (no se confirma al repositorio) en `/tmp/opencode/visual-referencia.mjs`, resolviendo `playwright` desde `frontend/` con `createRequire('/home/gerar/P2/frontend/package.json')` y Chromium de `~/.cache/ms-playwright`. Precondiciones: backend en `127.0.0.1:8000` contra la BD de desarrollo (entorno de `backend/.env`) y `npm run dev` en `frontend/` (`http://localhost:5173`, proxy `/api` a `:8000`); el actor y los datos de la Unidad de prueba se crean por API y se eliminan al terminar.

Para cada viewport (**390×844** y **1280×800**) el script debe:

1. Navegar a `http://localhost:5173`, abrir «Inventario por Unidad», seleccionar la Unidad de prueba.
2. **Consulta:** pulsar «Referencia»; verificar `aria-expanded="true"`, tabla con las tres columnas y ausencia de «+ Agregar»/«Modificar»/«Eliminar».
3. **Configuración:** pulsar «Referencia»; ejecutar el flujo Agregar (origen → material → cantidad → confirmar), Modificar y Eliminar con confirmación.
4. Extraer el **snapshot del árbol semántico** (`page.accessibility`/`ariaSnapshot`) de cada estado y comprobar nombres, roles y etiquetas.
5. Medir **overflow**: `document.documentElement.scrollWidth <= window.innerWidth` en cada estado; sin desborde horizontal de la página.
6. Capturar la **consola** del navegador (`console`, `pageerror`, respuestas ≥ 400 inesperadas): cero errores y cero warnings.
7. Guardar capturas y el informe en `/tmp/opencode/visual/` (evidencia citada en la PARADA de T9; un fallo detiene la tarea).

## 7. Estrategia de pruebas y trazabilidad (Constitución §7.1)

| REQ | Verificación | Tarea |
| --- | --- | --- |
| 005, 006, 007, 008, 009, 010, 011 | pytest API + BD (`backend/tests/test_referencia.py`, aserta HTTP y SQL directo, snapshot de tablas de negocio) | T6 |
| 012 | `sql_tests/test_fase_referencia.py` y pytest (trigger, rollback) | T3, T6 |
| 015 | Contrato congelado vs OpenAPI vivo | T7 |
| 018 | `test_migracion_0030.py`, regresión completa | T3, T11 |
| 001-004, 013, 014, 016, 017 | vitest (componentes, hooks, servicio) | T10 |
| 001-004, 013, 014, 016 | Verificación visual Playwright (390/1280 px, árbol semántico, consola) | T9, T10 |

Regresión final (T11): `pytest` completo, `sql_tests`, `mypy`, vitest completo, `tsc -b`, `npm run build` sin warnings, `npm run lint`, `openspec validate --specs --strict`, contratos de Etapas 1 y 2 sin drift.

## 8. Riesgos y mitigación

| Riesgo | Mitigación |
| --- | --- |
| Carrera de altas del mismo material | PK compuesta + traducción de `IntegrityError` a 409 con rollback |
| Selector de cientos de materiales en móvil | Filtro de texto y verificación a 390 px (T9) |
| Duplicados entre secciones GENERAL en el origen «Inventario General» | Deduplicación por `material_id` en el cliente (P-8) |
| Pruebas que enumeran rutas o cabeza de migración | T3/T6 ajustan solo lo mínimo y lo registran |
| Cambio de `InventarioPorEquipos.tsx` (474 líneas) | Cambio mínimo y localizado; el resto de la página queda intacto |
| Navegadores Playwright sin instalar | Verificado previamente (`chromium` en `~/.cache/ms-playwright`); si faltara, instalar con `npx playwright install chromium` previa autorización |
