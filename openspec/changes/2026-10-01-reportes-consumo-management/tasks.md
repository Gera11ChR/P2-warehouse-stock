# Tasks: Reportes de Consumo & Management

Ejecución del cambio `2026-10-01-reportes-consumo-management` bajo Spec-Driven Development.
Flujo **Backend First** y **estrictamente secuencial**.

## Reglas de ejecución (obligatorias)

1. **Aprobación previa:** no se escribe código de implementación hasta que el administrador
   apruebe `proposal.md`, `EARS.md` y este `tasks.md`.
2. **Secuencialidad total:** los subagentes y las pruebas (pytest / vitest / pruebas SQL) se
   ejecutan **uno a la vez, nunca en paralelo**, para evitar deadlocks en PostgreSQL.
3. **Gate de contrato:** la certificación del contrato Backend (Fase 3) es **bloqueante**:
   no se inicia el Frontend (Fase 4) sin ella.
4. **Commits:** únicamente en `feat/reportes-consumo-management`, al cierre de cada fase con
   pruebas en verde. **Prohibidos** `git merge`, `git checkout main` o push a main.
5. **Regla constitucional:** cero aritmética de stock en Python; toda mutación de stock pasa
   por Stored Procedures en PostgreSQL 18.

> Nota operativa: si la plataforma no permite invocar subagentes automáticamente (algunos
> requieren activación manual), cada tarea incluye el **prompt exacto** para delegar.

---

## Fase 0 — Validación arquitectónica (gate de arranque)

- [ ] **T0.1 `@arq-reviewer`.** Validar impacto arquitectónico del cambio:
  > "Revisa el cambio `openspec/changes/2026-10-01-reportes-consumo-management` (proposal.md,
  > EARS.md) contra el contrato maestro `openspec/openspec.yaml`. Evalúa: (1) renombre físico
  > DESPLIEGUE→CONSUMO en funciones SQL, tablas y endpoints; (2) nueva dependencia
  > openpyxl+Pillow y su efecto en el servicio de reportes; (3) nuevos Stored Procedures
  > fn_sumar_cantidad / fn_mover_material / fn_agregar_todo_seguimiento y su encaje en la
  > delegación transaccional; (4) riesgos de romper el contrato existente. Entrega un dictamen
  > APROBADO/CONDICIONADO con lista de ajustes. NO modifiques código."
- [ ] **T0.2.** Incorporar ajustes del dictamen a proposal/EARS si los hubiera. Commit.

## Fase 1 — Base de Datos (`@dba-guard`)

- [ ] **T1.1** Inspeccionar el esquema real (solo lectura) para confirmar: nombre del estado
  transaccional TEAMS (`COMPLETED` vs `CONFIRMADO`), estructura de inventarios FO, detalle del
  seguimiento y `auditoria_eventos`. Resolver las preguntas abiertas de EARS.md.
- [ ] **T1.2** Migración Alembic de renombre físico: `fn_crear_despliegue` →
  `fn_crear_seguimiento`; `fn_cerrar_despliegue` → `fn_cerrar_seguimiento`; tablas/columnas y
  constraints asociadas a la nomenclatura CONSUMO/seguimiento.
- [ ] **T1.3** Migración Alembic: `fn_sumar_cantidad(...)` — suma cantidad al stock (General y
  FO), inserta movimiento **inmutable** en `auditoria_eventos`, todo en una transacción.
  Validaciones: cantidad > 0, material activo, registro de inventario existente.
- [ ] **T1.4** Migración Alembic: `fn_mover_material(...)` — descuenta origen, acredita destino,
  audita; rechaza destino = origen, cantidad ≤ 0 o cantidad > stock origen. Atomicidad total.
- [ ] **T1.5** Migración Alembic: `fn_agregar_todo_seguimiento(...)` — inserción atómica de
  todas las líneas con stock del inventario del equipo en el seguimiento ABIERTA activo.
- [ ] **T1.6** Migración Alembic: `fn_cerrar_seguimiento` extendido para persistir el registro
  del **Acta de Consumo** (conso consumido = tomada − sobrante, calculado en SQL) y nuevos
  tipos de evento de auditoría (p. ej. `ACTA_ENTREGA_GENERADA`, `ACTA_CONSUMO_GENERADA`,
  `SUMA_CANTIDAD`, `MOVIMIENTO_INVENTARIO`).
- [ ] **T1.7** Pruebas SQL secuenciales (psql / pytest de migraciones): atomicidad (rollback
  ante fallo inducido), concurrencia con `FOR UPDATE`, inmutabilidad de `auditoria_eventos`,
  casos borde (cantidad 0/negativa, destino=origen, stock insuficiente).
- [ ] **T1.8** Commit fase BD. Revisión de `@dba-guard`:
  > "Audita las migraciones y funciones SQL de la Fase 1 del cambio 2026-10-01... Verifica
  > atomicidad, cero aritmética en capa de aplicación, inmutabilidad de auditoria_eventos y
  > conformidad con openspec.yaml. Reporta hallazgos y dictamen."

## Fase 2 — Backend FastAPI (`@coder`)

- [ ] **T2.1** Agregar dependencias `openpyxl` y `Pillow` a `backend/pyproject.toml`
  (requisito funcional: conservar imagen embebida de las plantillas).
- [ ] **T2.2** Servicio de plantillas (`PlantillaReporte`): carga de
  `1 ACTA DE REPORTE NORMAL.xlsx` / `2 ACTA DE REPORTE EXTENSO.xlsx`, inyección de datos con
  OpenPyXL, copia de estilo al insertar filas de desborde (Normal 10–25, Extenso 9–28),
  desplazamiento de bloques de firma, título "ACTA DE CONSUMO" cuando corresponda,
  preservación del logo embebido, sanitización anti-fórmula de celdas y nombres de archivo.
- [ ] **T2.3** Renombre de capa API: rutas y schemas de `/equipos/{equipo_id}/despliegues*` →
  `/equipos/{equipo_id}/seguimientos*` (crear, listar, obtener, cerrar). Sin alias legacy.
- [ ] **T2.4** Endpoint `POST /api/v1/equipos/{equipo_id}/seguimientos/{seguimiento_id}/agregar-todo`
  → llama a `fn_agregar_todo_seguimiento` (sin lógica de negocio en Python).
- [ ] **T2.5** Endpoints de operadores rápidos (delegación total a SP):
  - `POST /api/v1/ajustes/sumar-cantidad` → `fn_sumar_cantidad` (códigos 200/400/404).
  - `POST /api/v1/inventario/mover` → `fn_mover_material` (códigos 200/400/409/422).
- [ ] **T2.6** Reportes XLSX: `GET /api/v1/reportes/entrega` y `GET /api/v1/reportes/consumo`
  con `?formato=normal|extenso` (y filtros equipo/desde/hasta). Respuesta
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Se elimina el enum
  `csv` del reporte legacy `/reportes/despliegues` (ruta reemplazada por `/reportes/consumo`).
- [ ] **T2.7** Disparo del Acta de Entrega: al confirmar TEAMS y transicionar el movimiento al
  estado transaccional real (`COMPLETED`, verificado en T1.1), persistir el registro del acta
  (los datos provienen de la transacción SQL; el XLSX se genera bajo demanda en T2.6).
- [ ] **T2.8** Actualizar `openspec/openspec.yaml` (REQ-P2-CTR-001): mandatory_functions y
  paths del contrato.
- [ ] **T2.9** Commit fase Backend. Prompt `@coder`:
  > "Implementa la Fase 2 del cambio 2026-10-01-reportes-consumo-management conforme a
  > EARS.md y tasks.md. Respeta: cero aritmética de stock en Python, delegación total a SP,
  > inyección sobre plantillas corporativas con openpyxl conservando estilo y logo."

## Fase 3 — Seguridad, pruebas y certificación de contrato (GATE BLOQUEANTE)

- [ ] **T3.1 `@sec-ops`** (secuencial, tras T2):
  > "Audita la seguridad del backend del cambio 2026-10-01...: control de acceso a reportes y
  > operadores (roles), inyección SQL en llamadas a SP, path traversal en plantillas/nombres de
  > archivo, fórmula injection en XLSX, exposición de datos de auditoría. Entrega hallazgos
  > priorizados. NO modifiques código."
- [ ] **T3.2** Aplicar correcciones de seguridad y re-ejecutar pruebas.
- [ ] **T3.3 `@tester`** — pytest secuencial: migraciones, SP (atomicidad/rollback),
  endpoints de operadores, generación de actas Normal/Extenso, desborde de filas, errores
  400/404/409/422, sin regresiones del resto de la suite.
- [ ] **T3.4 `@qa-agent`** — auditoría de contrato (Zero-Drift): implementación vs
  `openspec/openspec.yaml` y EARS.md. Lista de drift (si existiera) y dictamen.
- [ ] **T3.5** **CERTIFICACIÓN DEL CONTRATO BACKEND:** pytest 100% verde + dictamen QA sin
  drift crítico + aprobación del administrador. **No se procede a Fase 4 sin esto.**
- [ ] **T3.6** Commit.

## Fase 4 — Frontend React 19 (secuencial: `@ui-agent` → `@ux-agent` → `@form-agent` → `@state-agent`)

- [ ] **T4.1 `@ui-agent`** — renombres visibles: DESPLIEGUE→CONSUMO, "Crear Despliegue"→
  "Crear Seguimiento"; sección REPORTES con subsecciones Entrega y Consumo (botones
  "Exportar XLSX (Normal)" / "Exportar XLSX (Extenso)"); logo corporativo esquina superior
  izquierda. Prompt:
  > "Implementa los cambios de UI de la Fase 4 del cambio 2026-10-01... según EARS.md.
  > No modifiques lógica de estado ni endpoints."
- [ ] **T4.2 `@ux-agent`** — revisar flujos: botón "Agregar todo" en Inventario por Equipos
  (ubicación demarcada en `docs/reportes-implementacion/consume_functionalities.png`),
  opciones `+Cantidad` y `Mover` junto a Modificar/Eliminar en el panel Detalle del Material,
  y confirmación de exportación (ver `confirmation_report_generation.png`).
- [ ] **T4.3 `@form-agent`** — formularios: `+Cantidad` (input numérico > 0), `Mover`
  (select box de inventarios destino válidos + cantidad, por defecto stock completo),
  validaciones client-side coherentes con 400/409/422 del backend.
- [ ] **T4.4 `@state-agent`** — estado/data fetching: integración con endpoints de seguimientos,
  `agregar-todo`, operadores rápidos y reportes XLSX (descarga de blob); manejo de errores y
  recarga de stock tras operaciones; sincronización de la tabla transaccional TEAMS para el
  disparo del Acta de Entrega.
- [ ] **T4.5** vitest secuencial: componentes renombrados, "Agregar todo", `+Cantidad`, `Mover`,
  subsecciones de Reportes, logo. Commit.

## Fase 5 — Cierre y QA final

- [ ] **T5.1 `@qa-agent`** — auditoría final Zero-Drift end-to-end (contrato ↔ backend ↔
  frontend) y verificación de los dos hitos: Acta de Entrega al confirmar TEAMS y Acta de
  Consumo al cerrar el seguimiento.
- [ ] **T5.2** pytest + vitest completos, secuenciales, en verde.
- [ ] **T5.3** Commit final en `feat/reportes-consumo-management`. **Sin merge**: el
  administrador revisará y fusionará manualmente.

## Definición de Terminado (DoD)

- [ ] Renombre físico CONSUMO/seguimiento completo en BD, API y UI.
- [ ] Reportes XLSX sobre plantillas corporativas (Normal y Extenso) con estilo y logo intactos.
- [ ] Acta de Entrega automática al estado transaccional de entrega TEAMS y Acta de Consumo
  al cierre del seguimiento.
- [ ] `+Cantidad` y `Mover` operativos vía SP atómicos con auditoría inmutable.
- [ ] Contrato `openspec/openspec.yaml` actualizado y certificado sin drift.
- [ ] Cero aritmética de stock en Python. Pruebas secuenciales en verde.
- [ ] Commits solo en `feat/reportes-consumo-management`; ningún merge ejecutado.
