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

- [x] **T0.1 `@arq-reviewer`.** Validar impacto arquitectónico del cambio:
  > "Revisa el cambio `openspec/changes/2026-10-01-reportes-consumo-management` (proposal.md,
  > EARS.md) contra el contrato maestro `openspec/openspec.yaml`. Evalúa: (1) renombre físico
  > DESPLIEGUE→CONSUMO en funciones SQL, tablas y endpoints; (2) nueva dependencia
  > openpyxl+Pillow y su efecto en el servicio de reportes; (3) nuevos Stored Procedures
  > fn_sumar_cantidad / fn_mover_material / fn_agregar_todo_seguimiento y su encaje en la
  > delegación transaccional; (4) riesgos de romper el contrato existente. Entrega un dictamen
  > APROBADO/CONDICIONADO con lista de ajustes. NO modifiques código."
- [x] **T0.2.** Incorporar a proposal/EARS/tasks el dictamen de `@arq-reviewer` (ajustes
  Críticos 1–3, Altos 4–7, Medios 8–11: trigger del Acta de Entrega en la misma transacción,
  inventario de objetos dependientes del renombre + inmutabilidad del ledger, contrato con
  summaries/eventos/glosario, semántica dispersa de `Mover`, diferenciación `SUMA_CANTIDAD`
  vs `AJUSTE_*`, idempotencia, re-anclado de merges/imagen en desborde, versiones fijadas de
  openpyxl/Pillow, snapshot jsonb del acta, sanitización de descargas). Commit.

## Fase 1 — Base de Datos (`@dba-guard`)

- [x] **T1.1** Inspeccionar el esquema real (solo lectura) para confirmar: nombre del estado
  transaccional TEAMS (`COMPLETED` vs `CONFIRMADO`), estructura de inventarios FO, detalle del
  seguimiento, `auditoria_eventos` (taxonomía de tipos de evento), objetos dependientes de la
  nomenclatura DESPLIEGUE (vistas, triggers, FKs, secuencias, defaults) y **versión real de
  PostgreSQL**. Resolver las preguntas abiertas de EARS.md.
- [x] **T1.2** Migración Alembic **manual** de renombre físico: `fn_crear_despliegue` →
  `fn_crear_seguimiento`; `fn_cerrar_despliegue` → `fn_cerrar_seguimiento`; tablas/columnas,
  vistas, triggers, claves foráneas, secuencias y defaults asociados a la nomenclatura
  CONSUMO/seguimiento. **Prohibido** actualizar filas históricas de `auditoria_eventos`
  (ledger inmutable; mapeo legacy↔nuevo solo en lectura). No confiar en Alembic autogenerate.
- [x] **T1.3** Migración Alembic: `fn_sumar_cantidad(...)` — suma cantidad al stock (General y
  FO), inserta movimiento **inmutable** en `auditoria_eventos` con evento `SUMA_CANTIDAD`
  (diferenciado de `AJUSTE_*`), todo en una transacción. Validaciones: cantidad > 0, material
  activo, registro de inventario existente. **Guarda de idempotencia** (clave de operación)
  contra doble ejecución.
- [x] **T1.4** Migración Alembic: `fn_mover_material(...)` — descuenta origen, acredita destino,
  audita con evento `MOVIMIENTO_INVENTARIO`; rechaza destino = origen, cantidad ≤ 0 o cantidad >
  stock origen. Atomicidad total + guarda de idempotencia. **Documentar la decisión** de
  semántica dispersa: crear fila destino solo con stock > 0; eliminar (o conservar) fila origen
  con stock 0; validación de coherencia U.M./catálogo entre origen y destino.
- [x] **T1.5** Migración Alembic: `fn_agregar_todo_seguimiento(...)` — inserción atómica e
  **idempotente** de todas las líneas con stock del inventario del equipo en el seguimiento
  ABIERTA activo (doble invocación no duplica líneas). Evento de auditoría propio `AGREGAR_TODO`.
- [x] **T1.6** Migración Alembic: `fn_cerrar_seguimiento` extendido para persistir el registro
  del **Acta de Consumo** (consumo = tomada − sobrante, calculado en SQL, con **snapshot jsonb**)
  y nuevos tipos de evento (`ACTA_ENTREGA_GENERADA`, `ACTA_CONSUMO_GENERADA`). **Trigger/SP**:
  el registro del **Acta de Entrega** ocurre **en la misma transacción SQL** de la confirmación
  TEAMS (transición al estado transaccional real), con snapshot jsonb; nunca como paso HTTP
  posterior.
- [x] **T1.7** Pruebas SQL secuenciales (psql / pytest de migraciones): atomicidad (rollback
  ante fallo inducido), concurrencia con `FOR UPDATE`, inmutabilidad de `auditoria_eventos`,
  idempotencia (doble invocación de los tres SP nuevos), casos borde (cantidad 0/negativa,
  destino=origen, stock insuficiente).
- [x] **T1.8** Commit fase BD. Revisión de `@dba-guard`:
  > "Audita las migraciones y funciones SQL de la Fase 1 del cambio 2026-10-01... Verifica
  > atomicidad, cero aritmética en capa de aplicación, inmutabilidad de auditoria_eventos y
  > conformidad con openspec.yaml. Reporta hallazgos y dictamen."

## Fase 2 — Backend FastAPI (`@coder`)

- [x] **T2.1** Agregar dependencias `openpyxl` y `Pillow` a `backend/pyproject.toml` con
  **versiones fijadas**; documentar que Pillow es requisito para que openpyxl conserve la
  imagen embebida de las plantillas; verificar licencias (MIT/HPND); incluir un test del
  servicio de reportes que **falle si Pillow no está instalado**.
- [x] **T2.2** Servicio de plantillas (`PlantillaReporte`): carga de
  `1 ACTA DE REPORTE NORMAL.xlsx` / `2 ACTA DE REPORTE EXTENSO.xlsx`, inyección de datos con
  OpenPyXL, copia de estilo al insertar filas de desborde (Normal filas 10–25, Extenso 9–28),
  **re-anclado manual de merges y de la imagen** (`drawing1.xml` no se desplaza solo con
  `insert_rows`), desplazamiento de bloques de firma, título "ACTA DE CONSUMO" cuando
  corresponda, preservación del logo embebido, sanitización anti-fórmula de celdas y nombres
  de archivo. Rutas de plantillas como **constantes del servidor** (nunca input de usuario).
- [x] **T2.3** Renombre de capa API: rutas y schemas de `/equipos/{equipo_id}/despliegues*` →
  `/equipos/{equipo_id}/seguimientos*` (crear, listar, obtener, cerrar). Sin alias legacy.
- [x] **T2.4** Endpoint `POST /api/v1/equipos/{equipo_id}/seguimientos/{seguimiento_id}/agregar-todo`
  → llama a `fn_agregar_todo_seguimiento` (sin lógica de negocio en Python). Soporta clave de
  idempotencia en el body/header.
- [x] **T2.5** Endpoints de operadores rápidos (delegación total a SP, namespace unificado
  `/api/v1/inventario/`):
  - `POST /api/v1/inventario/sumar-cantidad` → `fn_sumar_cantidad` (códigos 200/400/404).
  - `POST /api/v1/inventario/mover` → `fn_mover_material` (códigos 200/400/409/422).
  - Ambos con clave de idempotencia (doble submit no duplica efectos).
- [x] **T2.6** Reportes XLSX: `GET /api/v1/reportes/entrega` y `GET /api/v1/reportes/consumo`
  con `?formato=normal|extenso` (y filtros equipo/desde/hasta). Respuesta
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` con `Content-Disposition`
  seguro. Se elimina el enum `csv` del reporte legacy `/reportes/despliegues` (ruta reemplazada
  por `/reportes/consumo`).
- [x] **T2.7** Acta de Entrega: el registro se persiste **dentro de la transacción SQL** de la
  confirmación TEAMS (trigger/SP de T1.6), con snapshot jsonb. FastAPI solo expone la
  exportación bajo demanda del XLSX desde ese snapshot (sin recalcular desde stock actual).
- [x] **T2.8** Actualizar `openspec/openspec.yaml` (REQ-P2-CTR-001): mandatory_functions, paths
  renombrados **con summaries/descripciones y eventos de auditoría**, eliminación del enum
  `csv`, endpoints de operadores rápidos bajo `/api/v1/inventario/` y **glosario de
  nomenclatura** (CONSUMO / seguimiento / entrega).
- [x] **T2.9** Commit fase Backend. Prompt `@coder`:
  > "Implementa la Fase 2 del cambio 2026-10-01-reportes-consumo-management conforme a
  > EARS.md y tasks.md. Respeta: cero aritmética de stock en Python, delegación total a SP,
  > inyección sobre plantillas corporativas con openpyxl conservando estilo y logo."

### Notas de implementación de la Fase 2 (decisiones tomadas y desviaciones menores)

- **Estado transaccional TEAMS:** el real es `CONFIRMADO` (verificado en T1.1); `COMPLETED`
  del documento de contexto es su equivalente conceptual. El Acta de Entrega la registra el
  trigger `tg_acta_entrega` en la misma transacción SQL (T2.7: FastAPI solo la exporta).
- **Reportes:** `formato` admite `json` (por defecto, listado para la tabla de la UI),
  `normal` y `extenso`; el CSV legacy responde 422 y `/reportes/despliegues` ya no existe.
  Se añadió el filtro opcional `acta_id` (exportar un acta individual). Con varias actas el
  XLSX concatena las líneas **sin agregarlas ni recalcularlas**. En el Acta de Consumo se
  omiten las líneas con consumo 0. Sin actas, el XLSX responde 404.
- **Operadores rápidos:** `cantidad` no se valida con `gt=0` en Pydantic para que la regla
  (cantidad > 0) la aplique el SP y responda **400** como indica el contrato; el reenvío con
  la misma `clave_idempotencia` responde 200 con el resultado original
  (`reenvio_idempotente=true`).
- **Acta de Consumo y cierres previos a la migración 0020:** los seguimientos ya cerrados
  antes de 0020 no tienen acta (no hubo backfill) y por tanto no aparecen en
  `/reportes/consumo`. Pendiente de decisión del administrador.

## Fase 3 — Seguridad, pruebas y certificación de contrato (GATE BLOQUEANTE)

- [x] **T3.1 `@sec-ops`** (secuencial, tras T2):
  > "Audita la seguridad del backend del cambio 2026-10-01...: control de acceso a reportes y
  > operadores (roles), inyección SQL en llamadas a SP, **path traversal en plantillas
  > (prioridad Alta)**, fórmula injection en XLSX, `Content-Disposition`/content-type en
  > descargas, exposición de datos de auditoría. Entrega hallazgos priorizados. NO modifiques
  > código."
- [ ] **T3.2** Aplicar correcciones de seguridad y re-ejecutar pruebas.
- [ ] **T3.3 `@tester`** — pytest secuencial: migraciones, SP (atomicidad/rollback),
  endpoints de operadores **con idempotencia**, generación de actas Normal/Extenso, desborde de
  filas **verificando que merges + imagen + estilo permanecen intactos tras `insert_rows` en
  ambas plantillas**, errores 400/404/409/422, sin regresiones del resto de la suite.
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

- [ ] Renombre físico CONSUMO/seguimiento completo en BD, API y UI, con objetos dependientes
  cubiertos e `auditoria_eventos` histórico intacto (ledger inmutable).
- [ ] Reportes XLSX sobre plantillas corporativas (Normal y Extenso) con estilo, merges y logo
  intactos, incluido el desborde de filas.
- [ ] Acta de Entrega automática (misma transacción SQL de la confirmación TEAMS, snapshot
  jsonb) y Acta de Consumo al cierre del seguimiento.
- [ ] `+Cantidad` y `Mover` operativos vía SP atómicos e idempotentes, con eventos de
  auditoría diferenciados y namespace unificado `/api/v1/inventario/`.
- [ ] Contrato `openspec/openspec.yaml` actualizado (summaries, eventos, glosario) y
  certificado sin drift.
- [ ] Cero aritmética de stock en Python. Pruebas secuenciales en verde.
- [ ] Commits solo en `feat/reportes-consumo-management`; ningún merge ejecutado.
