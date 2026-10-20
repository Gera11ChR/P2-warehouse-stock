# Plan técnico — ETAPA 1/3: ACTIVIDADES (Registro)

**Paquete:** `2026-10-actividades-unidad` · **Fase SDD:** 5 (Planificación) · **Regla rectora:** Backend-First (DB → API → congelación de contrato → Frontend).
Separación spec/diseño (Constitución §1.2): este documento define el *cómo*; el *qué* está en `spec.md` (REQ-ACT-001..020).

## 1. Decisiones de diseño

| # | Decisión | Justificación |
| --- | --- | --- |
| D-1 | Tablas propias (`actividades_reportes`); no se agrega tipo a `actas_reportes` | No tocar `ck_actas_reportes_tipo/extremos` ni los tres `ActaTipo` existentes (REQ-ACT-015). La Etapa 2 listará por folio |
| D-2 | 1 actividad = 1 seguimiento CERRADA (`UNIQUE(seguimiento_id)`) | Decisión del humano; RF-3, RF-11 |
| D-3 | Materiales y valor unitario se derivan en PostgreSQL y se congelan como snapshot jsonb | Cálculo/lecturas de negocio fuera de Python/React; RF-10, regla `prohibition` de `openspec.yaml` |
| D-4 | Folio por `pg_advisory_xact_lock` + `COALESCE(MAX(folio_num),0)+1`, con `UNIQUE(folio_num)` como red de seguridad | Sin huecos entre confirmados; la tabla es append-only, sin DELETE. Sin secuencia (las secuencias dejan huecos al rollback) |
| D-5 | El POST lleva `seguimiento_id` explícito | Evita la carrera «GET pendiente → otro cierre → POST» y fija idempotencia (409 en reintento) |
| D-6 | Identificadores técnicos `equipo_id`/`equipos` se conservan | Regla vigente protegida por `backend/tests/test_unidad_nomenclatura.py` (REQ-UNI-005); "Unidad" solo en UI |
| D-7 | Vehículo = texto libre (no usa la tabla legacy `vehicles`) | Decisión del humano |

## 2. Capa 1 — Base de datos (Alembic 0029, `@dba-guard`)

Archivo: `backend/alembic/versions/0029_actividades_unidad.py` (`revision="0029"`, `down_revision="0028"`; estilo de 0025-0028: docstring con Revision/Revises/Create Date y racional, funciones como constantes SQL, `op.execute(sa.text(...))`, verificaciones post-condición con `RuntimeError`).

### 2.1 Tabla `actividades_reportes`

| Columna | Tipo | Restricciones |
| --- | --- | --- |
| `id` | `integer` serial | PK |
| `folio_num` | `integer` | NOT NULL, UNIQUE (`uq_actividades_folio`), CHECK `> 0` |
| `seguimiento_id` | `integer` | NOT NULL, UNIQUE (`uq_actividades_seguimiento`), FK `seguimientos(id)` ON DELETE RESTRICT |
| `equipo_id` | `integer` | NOT NULL, FK `equipos(equipo_id)` ON DELETE RESTRICT; índice `ix_actividades_equipo_created (equipo_id, created_at DESC)` |
| `vehiculo` | `varchar(100)` | NOT NULL, CHECK `btrim(vehiculo) <> ''` |
| `clientes` | `varchar(500)` | NOT NULL, CHECK no vacío tras `btrim` |
| `direcciones` | `varchar(500)` | NOT NULL, CHECK no vacío tras `btrim` |
| `actividades` | `jsonb` | NOT NULL, CHECK `jsonb_typeof = 'array'` y longitud 1..30 |
| `comentarios` | `varchar(2000)` | NULL |
| `materiales` | `jsonb` | NOT NULL (snapshot; array, puede ser `[]`) |
| `usuario` | `varchar(100)` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL DEFAULT `now()` (= fecha de la actividad) |

- Trigger `tg_ledger_actividades_inmutable` BEFORE UPDATE OR DELETE → `fn_bloquear_mutacion_ledger()` (existente; no se modifica).
- **Coherencia seguimiento/equipo:** `fn_crear_actividad` valida `seguimientos.equipo_id = p_equipo_id`.
- No se modifica ninguna tabla existente. `auditoria_eventos.tipo_accion` es `varchar(50)` sin CHECK de enumeración (verificado en T1): el nuevo valor no requiere migración.

### 2.2 Stored Functions

**`fn_crear_actividad(p_equipo_id int, p_seguimiento_id int, p_vehiculo text, p_clientes text, p_direcciones text, p_actividades jsonb, p_comentarios text, p_usuario text) RETURNS int`** (devuelve `actividades_reportes.id`):
1. `SELECT … FROM seguimientos WHERE id = p_seguimiento_id FOR UPDATE`. Inexistente o de otra Unidad → `RAISE EXCEPTION 'Seguimiento inexistente para la Unidad.' USING ERRCODE='P0001'`.
2. `estado <> 'CERRADA'` → «El seguimiento debe estar cerrado para registrar la actividad.» (no se exige que sea el más reciente; C-1)
3. Existe actividad para el seguimiento → «El seguimiento ya tiene una actividad confirmada.»
4. Valida que `p_actividades` sea array de 1..30 textos no vacíos (≤500) tras recortar espacios (defensa en profundidad de RF-6/RF-13).
5. `pg_advisory_xact_lock(<constante de dominio>)`; `folio_num = COALESCE(MAX(folio_num),0)+1`.
6. Construye `materiales` desde `seguimiento_items JOIN catalogo_materiales` con `cantidad_consumida > 0`, ordenados por `material_id`: `{material_id, codigo, descripcion, u_m, cantidad_consumida, valor_unitario}` (NUMERIC exacto, sin aritmética en Python).
7. `INSERT INTO actividades_reportes … RETURNING id`.
8. `INSERT INTO auditoria_eventos(usuario, tipo_accion, equipo_origen_id, resultado, detalles)` con `usuario = p_usuario`, `tipo_accion = 'ACTIVIDAD_CONFIRMADA'`, `equipo_origen_id = p_equipo_id`, `resultado = 'EXITO'` y `detalles = jsonb_build_object('actividad_id', …, 'folio', 'R'||lpad(folio_num::text, GREATEST(4, length(folio_num::text)), '0'), 'seguimiento_id', …, 'equipo_id', …)` (convención de `ACTA_CONSUMO_GENERADA`).
9. No toca `inventario_equipos`, `seguimientos` ni `actas_reportes` (REQ-ACT-015).

Mensajes `RAISE` deterministas, mapeados por `_mapear_raise_exception` (ver §3.3). **Nombres de mensaje son contrato**: no se cambian sin RFC.

**`fn_actividad_pendiente(p_equipo_id int) RETURNS TABLE(...)`** (solo lectura, STABLE): último seguimiento `CERRADA` (por `closed_at DESC, id DESC`) de la Unidad sin fila en `actividades_reportes`, con sus materiales consumidos y `valor_unitario` vigente. Una consulta SQL equivalente en `services/actividades.py` es aceptable si `@dba-guard` la prefiere (decisión de T2); en ambos casos el cálculo vive en PostgreSQL.

**`downgrade()`:** `DROP FUNCTION` ×2, `DROP TRIGGER`, `DROP TABLE actividades_reportes`. Los eventos `ACTIVIDAD_CONFIRMADA` ya escritos en el ledger NO se eliminan (append-only); `downgrade` sin datos de usuario se prueba en `test_migracion_0029`.

### 2.3 Archivos de soporte
- `backend/db/ddl.sql` regenerado con `backend/scripts/generar_ddl.py` y verificado con `--verificar` (el encabezado nombra el head 0029).
- `backend/tests/conftest.py`: añadir `actividades_reportes` a `TABLAS_DOMINIO` (el TRUNCATE usa `CASCADE`, el orden no es crítico; se coloca antes de `seguimientos` por legibilidad).

## 3. Capa 2 — API FastAPI (`@coder`, revisión `@sec-ops`)

### 3.1 Archivos
- `backend/app/models/actividad.py` (`ActividadReporte`, alineado con el DDL) y registro en `models/__init__.py`.
- `backend/app/schemas/actividad.py` (Pydantic v2, `model_config = ConfigDict(extra="forbid")` en todo DTO de entrada).
- `backend/app/services/actividades.py` (lecturas) y wrappers en `services/transaccional.py` (`crear_actividad`, con `_SQL_CREAR_ACTIVIDAD`, `_set_actor`, `_ejecutar`).
- `backend/app/api/v1/actividades.py` (`APIRouter(prefix="/equipos", tags=["actividades"])`) e inclusión en `app/main.py`.

### 3.2 Contrato (congelable en T7)

Base: `/api/v1/equipos/{equipo_id}/actividades`. Todos exigen `X-Actor` (validado antes de la BD, 422 si inválido).

| Método | Ruta | Request | Response | Códigos |
| --- | --- | --- | --- | --- |
| GET | `/pendiente` | — | `ActividadPendienteOut` | 200, 400, 403, 404, 422 |
| POST | `` | `ActividadCreate` | `ActividadOut` | 201, 400, 403, 404, 409, 422 |
| GET | `` | — | `ActividadListOut` | 200, 400, 403, 404, 422 |

**DTOs**

```text
ActividadMaterialOut {
  material_id: int, codigo: str | null, descripcion: str, u_m: str | null,   // el catálogo admite codigo/u_m NULL (verificado en T7)
  cantidad_consumida: CantidadDecimal (NUMERIC(12,3) -> number),
  valor_unitario: number (NUMERIC(12,3))
}

ActividadPendienteOut {
  seguimiento: null | {
    seguimiento_id: int, fecha_cierre: datetime (ISO 8601 con zona),
    materiales: ActividadMaterialOut[]            // puede ser []
  }
}

ActividadCreate  (extra="forbid") {
  seguimiento_id: int (1..2147483647),
  vehiculo: str (1..100, strip),
  clientes: str (1..500, strip),
  direcciones: str (1..500, strip),
  actividades: str[] (1..30 items, cada item 1..500 tras strip; vacías ya descartadas por el cliente),
  comentarios: str | null (<=2000)
}
// Ausentes del contrato de entrada por diseño: folio, fecha, materiales, valor_unitario, usuario.

ActividadOut {
  actividad_id: int, folio: str ("R0001"), folio_num: int,
  seguimiento_id: int, equipo_id: int, equipo_nombre: str,
  fecha: datetime (created_at, ISO 8601 con zona), usuario: str,
  vehiculo: str, clientes: str, direcciones: str,
  actividades: str[], comentarios: str | null,
  materiales: ActividadMaterialOut[]
}

ActividadListOut { items: ActividadOut[], total: int }
```

- El formateo `folio = f"R{folio_num:04d}"` es **presentación pura** en el DTO (sin lógica de negocio/aritmética de stock).
- IDs fuera de INT4 → 400 canónico (`NUMERIC_OUT_OF_RANGE`) por el handler global vigente.
- Valores numéricos como números JSON (convención de `decimal_quantities`).

### 3.3 Reglas transversales
- **Autorización:** POST → `assert_authenticated` + `async with session.begin()` + `prechequear_equipo` (404 antes de 403) + `assert_equipo_access`. GET → `prechequear_equipo` + `assert_equipo_access` (patrón de `seguimientos.py`).
- **Entrada (`@sec-ops`):** `extra="forbid"`, `strip`, límites, rechazo de caracteres de control (C0 salvo `\n` en `comentarios`, DEL, C1) con validadores Pydantic; sanitización de celda para XLSX NO aplica aquí (es de la Etapa 2).
- **Errores:** nuevas entradas en `_mapear_raise_exception` (`services/transaccional.py`):

| Mensaje de la función | HTTP | code |
| --- | --- | --- |
| «Seguimiento inexistente para la Unidad.» | 404 | `SEGUIMIENTO_NO_ENCONTRADO` |
| «El seguimiento debe estar cerrado…» | 409 | `SEGUIMIENTO_NO_CERRADO` |
| «El seguimiento ya tiene una actividad confirmada.» | 409 | `ACTIVIDAD_DUPLICADA` |
| validación de actividades/campos | 422 | `ACTIVIDAD_INVALIDA` |

  `23505` sobre `uq_actividades_seguimiento`/`uq_actividades_folio` (carrera residual) → 409 `ACTIVIDAD_DUPLICADA`; nunca 500.
- **Sin cálculo en Python:** el servicio solo transporta parámetros y mapea filas.
- **Auditoría:** `app.actor` fijado antes de mutar (patrón vigente); la función escribe el evento con `p_usuario`.

## 4. Congelación contractual (compuerta Backend → Frontend)

1. `@tester` completa pruebas de API (T6).
2. `@qa-agent` (T7) compara `spec.md` ⇄ OpenAPI (`GET /openapi.json`) ⇄ DTOs Pydantic, detecta campos faltantes/inventados/nomenclatura/tipos/métodos, y ejecuta la suite backend completa.
3. Con **PASS**: se escribe `openapi.snapshot.json` (solo rutas/esquemas de actividades) en el paquete, `.openspec.yaml` pasa a `contract.frozen: true`, y se autoriza la Fase 7 de frontend.
4. Cualquier cambio posterior de contrato exige actualizar primero `spec.md`/`plan.md` (RFC), nunca un parche silencioso (`@state-agent`).

## 5. Capa 3 — Frontend (`@state-agent`, `@form-agent`, `@ui-agent`, `@ux-agent`) — bloqueado hasta T7

Archivos nuevos (nombres de campos = contrato exacto):
- `frontend/src/types.ts`: `ActividadMaterial`, `ActividadPendiente`, `ActividadCreatePayload`, `Actividad`, `ActividadList`; entrada `ACTIVIDAD_CONFIRMADA` en `TIPOS_ACCION_AUDITORIA`.
- `frontend/src/services/actividades.ts` (`obtenerActividadPendiente`, `crearActividad`, `listarActividades` sobre `/equipos/{id}/actividades`).
- `frontend/src/hooks/useActividades.ts` + claves en `queryKeys.ts` (`actividadPendiente(equipoId)`, `actividades(equipoId)`; invalidador `invalidarActividadesEquipo` que refresca ambas y la auditoría). **Prohibido** calcular stock/valores en cliente.
- `frontend/src/schemas/actividad.ts` (zod 4: límites de RF-5/6/7, preliminar; PostgreSQL decide).
- `frontend/src/components/ActividadesPanel.tsx` y subcomponentes (`ActividadesMaterialesConsumidos`, `ActividadesFormulario`).
- `frontend/src/pages/InventarioPorEquipos.tsx`: agregar `'actividades'` a `TABS` (después de `consumo`), tipo `TabValue` y rama de panel `tab==='actividades'` que renderiza `<ActividadesPanel equipoId equipoNombre/>`.

UX (según imagen del docx): columna izquierda con «Materiales Consumidos · CANTIDAD | MATERIAL | U.M.» (+ VALOR UNITARIO); cabecera con Fecha («Automatizado»), Vehículo, Nombre Cliente(s), Dirección(es), «Actividades Realizadas» con celdas y botón verde «+ Agregar», Comentarios, y botón azul «Confirmar» (con diálogo `ConfirmDialog`). Estados: cargando / sin seguimiento pendiente (aviso + «Confirmar» deshabilitado) / listo / enviando (pendiente) / éxito (aviso con folio y fecha local) / error (mensaje del backend, datos conservados para reintentar). Tras éxito → `invalidateQueries` y re-lectura del backend.

## 6. Estrategia de pruebas

| Capa | Pruebas | REQ cubiertos |
| --- | --- | --- |
| BD | `tests/test_migracion_0029.py` (upgrade/downgrade, objetos, CHECKs, trigger); `sql_tests/` para folio, concurrencia (2 sesiones), inmutabilidad, snapshot | 008-012, 015, 020 |
| API | `tests/test_actividades.py` con nombres `test_req_act_NNN_*`: aserta HTTP **y** estado de BD | 001-017, 019 |
| Seguridad | `client_sin_scope`, `client_admin`, integrante; extras 422; X-Actor | 013, 014 |
| Frontend | `components/__tests__/ActividadesPanel*.test.tsx`, hooks, servicio, schema (vitest) | 001, 005-007, 017 |
| Regresión | pytest completo, vitest completo, `tsc`/build sin warnings, `openspec validate --specs --strict` | 020 |

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Folio duplicado/huecos por concurrencia | advisory lock + UNIQUE; prueba de 2 sesiones simultáneas |
| `seguimiento_id` cruzado entre Unidades | validación en la función + prueba negativa |
| Seguimientos cerrados anteriores sin actividad (C-1) | resuelto: la UI ofrece solo el más reciente, el backend acepta cualquiera |
| Sin vía de corrección tras confirmar | decisión de inmutabilidad; documentado |
| Cambio de `valor_unitario` entre vista previa y confirmación (C-3) | el snapshot de BD manda; la UI indica que el valor final lo fija el backend |
| `ddl.sql` desactualizado | `generar_ddl.py --verificar` en el criterio de T2 |

## 8. Trazabilidad plan ⇄ spec

REQ-ACT-001→§5 · 002/003/004→§2.2, §3.2 · 005/006/007→§3.2, §5 · 008→D-4, §2.2 · 009→§2.1 (`created_at`) · 010→§2.2 paso 6 · 011→D-2, D-5, §2.2 · 012→§2.1 trigger, §2.2 paso 8 · 013→§3.3 · 014→§3.3 · 015→§2.2 paso 9 · 016→§3.2 · 017→§5 · 018→§3.2 · 019→§3.3 · 020→§2, §6.
