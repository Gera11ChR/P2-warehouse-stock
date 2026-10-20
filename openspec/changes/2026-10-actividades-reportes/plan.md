# Plan técnico — ETAPA 2/3: ACTIVIDADES (Reportes y Exportación)

**Paquete:** `2026-10-actividades-reportes` · **Fase SDD:** 5 (Planificación) · **Regla rectora:** Backend-First (consulta → plantilla XLSX → API → congelación de contrato → Frontend).
Separación spec/diseño (Constitución §1.2): este documento define el *cómo*; el *qué* está en `spec.md` (REQ-REP-001..017).

## 1. Decisiones de diseño

| # | Decisión | Justificación |
| --- | --- | --- |
| D-1 | **Un libro, una hoja por folio**, hoja titulada con el folio, orden por folio ascendente, tope de 100 hojas (HTTP 422) | Directriz del humano (RN-3/RN-4); la plantilla es un documento por hoja |
| D-2 | Zona de negocio configurable `P2_REPORTES_TZ` (por defecto `America/Mexico_City`), validada al arrancar con `zoneinfo`; se usa para `desde`/`hasta` y para la FECHA impresa | Decisión del humano (C-1, confirmada en T1: `America/Mexico_City`, UTC-6 constante desde el 30-oct-2022); evita el corrimiento de día de un `timestamptz`. La zona de sesión de la BD es `America/Ojinaga`; la divergencia con Entrega/Consumo se registra como C-8 |
| D-3 | Selectores de operación de Entrega/Consumo solo en frontend, con el `acta_id` ya soportado | Decisión del humano; cero cambios de backend/contrato en esos reportes |
| D-4 | Sin agregados; COLABORADORES en blanco | Decisión del humano; el docx no los define |
| D-5 | **Sin migración** | `actividades_reportes` ya tiene `equipo_id`, `created_at`, índice `ix_actividades_equipo_created (equipo_id, created_at DESC)` y el snapshot. Si el `EXPLAIN` de T4 exigiera un índice por `created_at`, se tramita como RFC |
| D-6 | DTOs de salida reutilizados (`ActividadListOut`/`ActividadOut`/`ActividadMaterialOut`); sin DTOs nuevos | Contrato de Etapa 1 congelado; menor superficie de drift |
| D-7 | JSON: más reciente primero; XLSX: folio ascendente | El listado de UI muestra lo último arriba (igual que Etapa 1); el libro se lee en orden de folio |
| D-8 | FECHA del XLSX como **texto** `20 / OCTUBRE / 2026` (reutiliza `_MESES`) | Determinista e independiente del idioma de Excel; consistente con las actas (C-2). `B8` recibe `f"{dia:02d} / {_MESES[mes-1]} / {año}"` **sin** prefijo `FECHA:` (la etiqueta ya está en `A8`); no se reutiliza `formatear_fecha`, que antepone «FECHA: ». `B8` conserva su formato de número de fecha: solo recibe texto |
| D-9 | Módulos nuevos (`plantilla_reporte_actividades.py`, `reportes_actividades.py`, router propio); **no se modifican** `plantilla_reporte.py`, `reportes.py`, `api/v1/reportes.py` ni `services/actividades.py` (se importan `sanitizar_celda`, `sanitizar_nombre_archivo`, `_desplazar_filas`, `_MESES`, `_construir_out` dentro del mismo paquete) | Aísla Entrega/Consumo (REQ-REP-017); regla de no refactor ajeno |
| D-10 | El listado de Reportes se refresca por invalidación: `invalidarActividadesEquipo` suma la clave `['reportes','actividades']` | Folio nuevo visible sin recarga (REQ-REP-015) |
| D-11 | Límite defensivo adicional: máximo 10 000 filas inyectadas (materiales + actividades) por libro | Cota de memoria/CPU del XLSX (precedente B-1 de `@sec-ops`); a ratificar en T5 |

## 2. Capa 1 — Base de datos (sin DDL)

No hay migración ni función SQL nueva (D-5). El acceso es una consulta SQLAlchemy de **solo lectura** sobre `actividades_reportes JOIN equipos`:

```text
SELECT a.*, e.nombre
  FROM actividades_reportes a JOIN equipos e ON e.equipo_id = a.equipo_id
 WHERE [a.equipo_id = :equipo_id]
   AND [a.equipo_id IN :solo_equipos]                       -- actor no admin (vacío => sin filas)
   AND [a.id = :actividad_id]
   AND [a.created_at >= timezone(:zona, CAST(:desde AS timestamp))]
   AND [a.created_at <  timezone(:zona, CAST(:hasta AS timestamp) + interval '1 day')]
 ORDER BY a.created_at DESC, a.id DESC                      -- json
          | a.folio_num ASC LIMIT 101                       -- xlsx (tope + 1)
```

- `timezone(zona, timestamp)` interpreta el día calendario en la zona de negocio y devuelve `timestamptz`; `:zona`, `:desde` y `:hasta` viajan como **parámetros enlazados**, nunca concatenados. El `+ 1 día` se calcula **en SQL**, nunca en Python (`date + timedelta` desborda con `hasta=9999-12-31` y daría HTTP 500; verificado en T1). Es aritmética de calendario, no de stock/valor.
- La consulta se construye con **SQLAlchemy ORM tipado** (`ActividadReporte.equipo_id == …`, `ActividadReporte.id == …`, `.in_()`), **no** con `text()` sin tipos: solo con comparaciones tipadas PostgreSQL rechaza un identificador fuera de INT4 con SQLSTATE 22003 → 400 `NUMERIC_OUT_OF_RANGE`; con `text()` el mismo valor devolvería 200 vacío (verificado en T1).
- El tope se evalúa con `LIMIT 101` (más de 100 ⇒ 422) sin cargar todas las filas.
- `@dba-guard` (T4) revisa: solo lectura, parámetros enlazados, `EXPLAIN` con y sin `equipo_id`, y confirma que no se requiere índice.

## 3. Capa 2 — Backend FastAPI (`@coder`, revisión `@sec-ops`)

### 3.1 Archivos

- `backend/app/config.py`: `REPORTES_TZ = os.environ.get("P2_REPORTES_TZ") or "America/Mexico_City"` (un valor vacío equivale a no definido; `ZoneInfo("")` lanzaría `ValueError`) y validación al importar (`ZoneInfo(REPORTES_TZ)`; zona inválida ⇒ el servidor no arranca). Documentar la variable en el README (sección de variables opcionales).
- `backend/pyproject.toml`: dependencia `tzdata` con versión fija (política de pines del repo) para que `ZoneInfo` funcione sin tzdata del sistema; `uv.lock` actualizado.
- `backend/app/services/reportes_actividades.py`: `consultar_actividades(...)` (filtros + zona + orden + límite) y constantes `MAX_HOJAS_XLSX = 100`, `MAX_FILAS_XLSX = 10_000`. Reutiliza `_construir_out`.
- `backend/app/services/plantilla_reporte_actividades.py`: `generar_reporte_actividades(actividades, zona) -> bytes`, `nombre_archivo_actividades(...)`.
- `backend/app/api/v1/reportes_actividades.py`: `APIRouter(prefix="/reportes", tags=["reportes"])` con `GET /actividades`; registro en `app/main.py` tras `reportes`.
- No se crean modelos ni schemas (D-6).

### 3.2 Geometría de la plantilla (verificada con openpyxl sobre la hoja `401-450`)

| Zona | Celdas | Contenido a inyectar |
| --- | --- | --- |
| Título | `A3:F3` | Sin cambio («REPORTE DE MATERIALES Y ACTIVIDADES EN F.O») |
| FECHA | `B8:C8` | Texto `DD / MES / AAAA` en la zona de negocio |
| VEHÍCULO | `E8:F8` | `vehiculo` |
| NOMBRE | `B9:F9` | `clientes` |
| FOLIO | `I9:J9` (texto `FOLIO: R0000`) | `FOLIO: {folio}` |
| DIRECCION | `B10:F10` | `direcciones` |
| Encabezado de materiales | fila 12 | Sin cambio (CANTIDAD A, U.M. B, MATERIAL `C:H`, VALOR UNITARIO I) |
| Materiales | filas 13-22 (10), cada fila con `C:H` combinada | A=`cantidad_consumida` (numérico), B=`u_m`, C=`descripcion`, I=`valor_unitario` (numérico, formato `#,##0.00#`) |
| Actividades | encabezado fila 24; filas 25-28 (4), cada una `A:I` combinada | Una actividad por fila, texto envuelto |
| Comentarios | `A32:B34` (etiqueta) y `C32:I34` (valor) | `comentarios` (envuelto) |
| COLABORADORES | fila 36 y firmas 38-48 | **Sin cambio / en blanco** |

La hoja residual `Sheet1` (firmas sueltas en `L18:O28`) no se incluye en el libro (I-3). La plantilla en disco nunca se modifica (se carga en memoria).

### 3.3 Algoritmo de generación

1. `wb = load_workbook(<ruta constante>)`; `base = wb["401-450"]`; se eliminan las hojas que no son `base`.
2. Para `n` folios, se crean `n-1` copias **vacías** con `wb.copy_worksheet(base)` **antes** de inyectar datos (así todas parten de la plantilla limpia) y se **re-incrusta el logo** en cada copia. Antes de copiar y de cualquier `wb.save`, se capturan **una sola vez** los bytes del logo con `base._images[0].ref.getvalue()` (`ref` es un `BytesIO`). **Prohibido** invocar `Image._data()` sobre la imagen de la plantilla: es de un solo uso y cierra el flujo (`ValueError: I/O operation on closed file`, también en `wb.save`; verificado en T1). A cada copia se le añade `Image(BytesIO(bytes_logo))` con un `OneCellAnchor` **propio** (`AnchorMarker` col=6, fila=0, colOff=560070, rowOff=22860; `ext` cx=2266950, cy=876300) y `width`/`height` iguales a los de la imagen base; la hoja base conserva su imagen original. Cada hoja guarda su propio medio (≈24 KB; 100 hojas ≈ 2,6 MB). *Spike de T2:* verificar paridad de ancla/tamaño, merges, alturas, anchos de columna, `fitToPage`, márgenes y que `copy_worksheet` no pierda formatos.
3. Cada hoja se titula con el folio (`R0001`; ≤ 31 caracteres y sin caracteres prohibidos de Excel por construcción; únicos porque el folio es único). Orden por `folio_num` ascendente.
4. Por hoja, **de abajo hacia arriba** (para que las coordenadas de la plantilla sigan siendo válidas): (a) si hay más de 4 actividades, insertar `n_a = len(actividades) - 4` filas en la fila 29; (b) si hay más de 10 materiales, insertar `n_m = len(materiales) - 10` filas en la fila 23. La inserción reutiliza `_desplazar_filas` (mueve celdas, merges, alturas e imágenes) y copia estilo, altura y combinación (`C:H` en materiales, `A:I` en actividades) de la fila de referencia.
5. Inyección de datos (§3.2) con `sanitizar_celda` + eliminación de caracteres ilegales de XLSX (`openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE`). Los números se escriben como números (sin cadenas). La celda MATERIAL (`C:H`) lleva `wrap_text` y altura por la heurística del paso 6 si `len(descripcion)` excede el ancho combinado (≈71 caracteres; la columna admite 255). `A13`/`I13` son `General` en la plantilla: el formato `#,##0.00#` de VALOR UNITARIO se fija explícitamente.
6. **Comentarios y celdas de actividad largas:** `wrap_text=True`, alineación vertical superior; la altura de cada fila de actividad y la suma de las filas del área de comentarios se calculan con una heurística determinista de líneas (`ceil(len(párrafo) / caracteres_por_línea)` por párrafo × 13.2 pt), con `caracteres_por_línea` calibrado en T2 contra el ancho combinado real; el área de comentarios reparte la altura total entre sus filas con tope de 409,5 pt por fila (límite de Excel); si no alcanza, se insertan filas con `_desplazar_filas` y se extienden las combinaciones `A32:B34` y `C32:I34` (REQ-REP-008).
7. `wb.save(BytesIO)`; la generación corre en `run_in_threadpool` (CPU-bound).

### 3.4 Router y reglas transversales

`GET /api/v1/reportes/actividades` — parámetros: `equipo_id: int | None (gt=0)`, `desde: date | None`, `hasta: date | None`, `actividad_id: int | None (gt=0)`, `formato: Literal["json","xlsx"] = "json"`. Los parámetros se declaran como un **modelo de consulta Pydantic** (`filtros: Annotated[FiltrosReporteActividades, Query()]`, `ConfigDict(extra="forbid")`): un parámetro no declarado (p. ej. `acta_id`) responde 422 `extra_forbidden`, y el OpenAPI sigue exponiendo los 5 parámetros (verificado en T1 con FastAPI 0.143; el repo exige ≥0.115). Sin cota superior en los enteros: un valor positivo fuera de INT4 produce el 400 canónico `NUMERIC_OUT_OF_RANGE` del handler global (solo con comparaciones tipadas, §2).

- **Autorización (patrón de `/reportes/entrega`):** admin ⇒ sin restricción; no admin con `equipo_id` ⇒ `assert_equipo_access` (403); sin `equipo_id` ⇒ `solo_equipos = equipos_visibles(...)` (conjunto vacío ⇒ resultado vacío sin consultar). Un `actividad_id` ajeno queda fuera por el filtro y se comporta como inexistente (vacío / 404), sin revelar su existencia. No hay prechequeo de «Unidad activa» (C-7).
- **Validación previa a la BD:** `desde > hasta` ⇒ 422 (`BusinessRuleError`, código `RANGO_FECHAS_INVALIDO`); `formato` inválido ⇒ 422 (Pydantic/FastAPI).
- **json:** `ActividadListOut(items, total)` ordenado `created_at DESC, id DESC`.
- **xlsx:** `consultar_actividades(..., limite=MAX_HOJAS_XLSX + 1, orden=folio ASC)`; sin filas ⇒ 404; `> 100` ⇒ 422 (`LIMITE_HOJAS_EXCEDIDO`); total de filas inyectadas `> MAX_FILAS_XLSX` ⇒ 422 (`LIMITE_FILAS_EXCEDIDO`); respuesta `Response(content=bytes, media_type=XLSX, Content-Disposition: attachment; filename="<constante saneada>")`.
- **Nombre del adjunto (C-5):** `reporte-actividades-R0001.xlsx` (una hoja) o `reporte-actividades-AAAA-MM-DD.xlsx` (consolidado; fecha de la actividad más reciente en la zona de negocio), pasado por `sanitizar_nombre_archivo`.
- **Solo lectura:** ninguna escritura ni evento (REQ-REP-016); sin `session.begin()` de escritura.
- **Errores (verificados contra el código en T1):** 403 con el cuerpo de autorización vigente (`AuthorizationError`: `{"error":{"code","message","actor","required_scope"}}`); 422 de validación de FastAPI con `{"detail":[…]}` (parámetros inválidos o no declarados, `X-Actor` ausente/inválido); 400 `NUMERIC_OUT_OF_RANGE` y los errores de regla de negocio (404 sin resultados; 422 `RANGO_FECHAS_INVALIDO`, `LIMITE_HOJAS_EXCEDIDO`, `LIMITE_FILAS_EXCEDIDO`) con `{"error":{"code","message","coordinates"}}`. Precedencia: validación de parámetros (422) → autorización (403) → consulta (200/404). Nunca 500 por reglas de negocio.

### 3.5 Contrato (congelable en T7)

| Método | Ruta | Request | Response | Códigos |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reportes/actividades` | query: `equipo_id`, `desde`, `hasta`, `actividad_id`, `formato` | `ActividadListOut` (json) · `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (xlsx) | 200, 400, 403, 404, 422 |

DTOs: sin nuevos. `ActividadListOut {items: ActividadOut[], total}` y `ActividadOut`/`ActividadMaterialOut` tal como están en `openspec.yaml` (promovidos en la Fase 9 de la Etapa 1). Todos exigen `X-Actor`.

## 4. Congelación contractual (compuerta Backend → Frontend)

1. `@tester` completa las pruebas de plantilla y API (T3, T6).
2. `@qa-agent` (T7) compara `spec.md` ⇄ OpenAPI (`GET /openapi.json`) ⇄ implementación: parámetros, códigos, tipos, DTOs reutilizados **idénticos** (campo a campo, normalizando la notación nullable) a `components.schemas.ActividadMaterialOut/ActividadOut/ActividadListOut` de `openspec/openspec.yaml` y al OpenAPI vivo de `/equipos/{equipo_id}/actividades` (`.agents.md` §2 prohíbe tomar como referencia paquetes archivados), tipo de contenido XLSX y ausencia de campos inventados; ejecuta la suite backend completa.
3. Con **PASS**: se escribe `openapi.snapshot.json` (solo la ruta nueva y los esquemas que referencia) en el paquete, se registra su sha256 y `.openspec.yaml` pasa a `contract.frozen: true`; se autoriza el frontend.
4. Cualquier cambio posterior de contrato exige actualizar primero `spec.md`/`plan.md` (RFC), nunca un parche silencioso (`@state-agent`).

## 5. Capa 3 — Frontend (`@state-agent`, `@form-agent`, `@ui-agent`, `@ux-agent`) — bloqueado hasta T7

### 5.1 Estado (T8)

- `frontend/src/types.ts`: `ReporteActividadesParams {equipo_id?, desde?, hasta?, actividad_id?}`; `NavigationTarget.actividadId?: number` (opcional, sin romper rutas existentes). Se reutilizan `Actividad`/`ActividadList`.
- `frontend/src/services/reportes.ts` (funciones nuevas; las existentes no cambian de firma ni de comportamiento): `listarReporteActividades(params) → Actividad[]` (`GET /reportes/actividades?formato=json`, devuelve `items`) y `descargarReporteActividadesXlsx(params) → ArchivoDescargado` (`formato=xlsx`, `responseType: 'blob'`, mismo manejo de errores `ErrorDescargaReporte`, nombre desde `Content-Disposition` saneado con fallback determinista).
- `frontend/src/hooks/useReportes.ts`: `useReporteActividades(params)` y `useExportarReporteActividades()` con estado `idle | loading | success | error` (alcance consolidado/individual, `nombreArchivo`, `httpStatus`, `detalle`) y `reiniciar()` que no actúa durante una descarga en curso.
- `frontend/src/hooks/queryKeys.ts`: `reporteActividades(params?)` con el patrón de `actas` (`params === undefined ? ['reportes','actividades'] : ['reportes','actividades', params]`; no colisiona con `['reportes','actas',…]` ni con `['actividades', equipoId]`) e invalidación adicional en `invalidarActividadesEquipo` (D-10). Documentar en el comentario de claves que `usePatchConfigLocal` invalida el prefijo literal `['reportes']` y marca también este listado como obsoleto (inocuo: lectura idempotente).
- **Prohibido** agregar, ordenar o recalcular datos del reporte en cliente: se renderiza lo que entrega el backend.

### 5.2 Interfaz (T9)

- `frontend/src/pages/Reportes.tsx`: añade `'actividades'` a `SUBSECCIONES` (tras `consumo`), `subseccionInicial` la acepta y los props `initialActividadId`; los selectores de operación de Entrega y Consumo. `layouts/MainLayout.tsx` pasa `initialActividadId={route.actividadId}`, lo incluye en la `key` y define `SUB_LABELS.actividades = 'Actividades'` (el breadcrumb mostraría `Reportes / actividades` sin él).
  - **Desacople de tipos:** `Subseccion` deja de ser `ReporteTipo`. `useReporteActas`/`useExportarReporte` se ejecutan solo para `'entrega'|'consumo'` (subcomponente por tipo o `enabled`); la subsección `'actividades'` renderiza `ReporteActividadesSeccion` con sus propios hooks y **nunca** llama a `listarActas('actividades')` (devolvería `data.actas === undefined`).
- `frontend/src/components/ReporteSubseccion.tsx`: **props opcionales retrocompatibles** (`tipo` pasa a opcional: sin `tipo` o con `acciones` no se renderiza `ReporteExportFeedback`): `selectorOperacion?: {etiqueta, valor, opciones, onChange}` (renderizado tras «Hasta») y `acciones?: ReactNode` (sustituye los botones Normal/Extenso, que Actividades no usa porque solo hay un formato). Sin ellos el componente se comporta exactamente igual.
- **Selector de operación:** etiqueta «Acta» (Entrega), «Seguimiento» (Consumo), «Actividad» (Actividades). Las opciones salen del listado **sin** el filtro de operación (clave idéntica ⇒ una sola petición si no hay selección; con selección se hace una segunda petición con `acta_id`/`actividad_id`, filtrada por el servidor). Etiquetas: `Acta #12 · 2026-10-20 · Unidad`, `Seguimiento #7 · Acta #12 · …`, `R0001 · 20/10/2026 · Unidad`. Cambiar Unidad o fechas reinicia la selección y el resultado de descarga. El selector de Unidad lista solo Unidades activas (igual que Entrega y Consumo; C-9).
- `frontend/src/components/ReporteActividadesSeccion.tsx` (contenedor: filtros, queries, exportación) + `ReporteActividadesTable.tsx` (una fila por folio con botón «Ver detalle» `aria-expanded` y «Descargar XLSX» individual) + `ReporteActividadDetalle.tsx` (materiales con CANTIDAD/MATERIAL/U.M./VALOR UNITARIO congelado en `MonedaMxn`, actividades y comentarios) + `ReporteActividadesExportFeedback.tsx` (estado accesible `role="status"`/`alert`).
- Descarga consolidada: botón «Descargar libro (XLSX)» con los filtros vigentes (y `actividad_id` si hay operación elegida); deshabilitada con motivo visible mientras carga, con error o sin resultados; el 422 por tope de 100 muestra el mensaje del backend.
- `frontend/src/components/ActividadesPanel.tsx`: el aviso de éxito añade el botón «Ir a Reportes › Actividades» solo si `useAppNavigation()` existe, con `navigate({page:'reportes', sub:'actividades', equipoId, actividadId: actividad.actividad_id})`.
- Nomenclatura «Unidad» en toda la UI (REQ-UNI-005); fechas del listado en hora local del navegador (C-3).

## 6. Estrategia de pruebas

| Capa | Pruebas | REQ cubiertos |
| --- | --- | --- |
| Plantilla | `tests/test_plantilla_reporte_actividades.py`: celdas de §3.2, formato numérico, plantilla en disco intacta (hash), logo en **todas** las hojas, merges y alturas, desborde (11, 40 materiales; 5, 30 actividades de 500 caracteres; comentarios de 2000), cero materiales, sin `Sheet1`, hojas ordenadas, 100 hojas, neutralización de fórmulas, caracteres ilegales | 006, 007, 008, 009, 010 |
| API | `tests/test_reportes_actividades.py` (`test_req_rep_NNN_*`): cada prueba aserta HTTP **y** estado de BD con SQL directo (aprendizaje de T11 de la Etapa 1): json/orden, filtros y AND, día inclusivo en zona de negocio (actividad a las 23:30 locales), `desde > hasta`, 403/404/vacío por aislamiento, admin transversal, Unidad inactiva incluida, 404 sin resultados, 422 por 101 folios, `formato` inválido, 400 INT4, XLSX descargable y leído con openpyxl, tablas sin cambios y cero eventos nuevos | 002, 003, 004, 005, 009, 010, 011, 016 |
| Seguridad | `@sec-ops`: default-deny, no divulgación por `actividad_id`, fórmulas, nombre de archivo, límites | 003, 010 |
| Contrato | `@qa-agent` compuerta T7 (OpenAPI vs spec, DTOs idénticos a Etapa 1) | 011 |
| Frontend | `components/__tests__/ReporteActividades*.test.tsx`, `ReportesSelectoresOperacion.test.tsx`, `ActividadesPanel` (enlace), hooks y servicio (vitest) | 001, 012, 013, 014, 015 |
| Regresión | pytest completo (incluido Entrega/Consumo y Etapa 1), vitest completo, `tsc -b`/build/lint, `mypy`, `openspec validate --specs --strict`, contratos de `/equipos/{equipo_id}/actividades*` de `openspec/openspec.yaml` sin drift | 016, 017 |

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Logo perdido en las hojas copiadas (I-1) | Re-incrustación por hoja + prueba de imagen en cada hoja (T2/T3) |
| Desborde de actividades/materiales/comentarios deforma el formato (I-2) | Reutilizar `_desplazar_filas`; pruebas de merges/alturas/estilos con 11/40 materiales y 30 actividades |
| Zona horaria: día equivocado en la FECHA y en los filtros (I-4, C-1) | Zona de negocio configurable y validada; pruebas de borde a las 23:30 y 00:30 locales; decisión humana en T1 |
| XLSX gigante o lento (100 hojas × catálogo) | Tope de 100 hojas + 10 000 filas, `LIMIT 101`, `run_in_threadpool`; medición en T6 |
| Inyección de fórmulas / caracteres ilegales desde texto de usuario | `sanitizar_celda` + `ILLEGAL_CHARACTERS_RE`; pruebas y revisión `@sec-ops` |
| Filtro de fechas sin `equipo_id` hace barrido de tabla | Volumen acotado (un documento por seguimiento); `EXPLAIN` en T4; RFC si se requiere índice |
| Fuga entre Unidades por `actividad_id` ajeno | Filtro `solo_equipos` + igual respuesta que inexistente; prueba negativa |
| Cambios en `ReporteSubseccion`/`Reportes.tsx` rompen Entrega/Consumo | Props opcionales retrocompatibles; suite previa de Reportes intacta (T10/T11) |
| Listado JSON sin tope (I-5) | Filtros por uso; paginación registrada como deuda |

## 8. Trazabilidad plan ⇄ spec

REQ-REP-001→§5.2 · 002/005→§2, §3.4 · 003→§3.4 · 004→§2, §3.4, D-2 · 006→§3.3 · 007→§3.2, D-8 · 008→§3.3 (4)(6) · 009→D-1, §3.3 (2)(3), §3.4 · 010→§3.3 (5), §3.4, D-11 · 011→§3.5, §4 · 012→§5.2 · 013→§5.1, §5.2 · 014→§5.2, D-3 · 015→§5.1 (D-10), §5.2 · 016→§2, §3.4 · 017→§6, D-9.
