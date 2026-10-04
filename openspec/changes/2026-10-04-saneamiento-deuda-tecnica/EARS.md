# EARS: Saneamiento de deuda técnica y limpieza de código

Requisitos del cambio `2026-10-04-saneamiento-deuda-tecnica` en notación
EARS (Ubiquitous / Event-driven / State-driven / Option-driven / Unwanted).
Clasificación de severidad: **CRÍTICO** (constitucional) · **ALTO** · **MEDIO**.

> Convenciones: "Paquetes pendientes" = los 6 cambios implementados sin
> archivar (Fase 13). "Master specs" = `openspec/specs/`. "Deltas
> históricos" = los archivos `specs/*/spec.md` de los paquetes ya
> archivados que declaran cambios de especificación.
> "Intangibilidad runtime" = cero modificación de comportamiento ejecutable,
> esquemas, stored functions, respuestas exitosas de la API y UX actual.

## 1. Mantenimiento OpenSpec

- **REQ-SANE-001 (Ubiquitous / ALTO).** Los 6 paquetes implementados
  pendientes **deberán** quedar archivados bajo
  `openspec/changes/archive/`, incluida la corrección del manifiesto
  `.openspec.yaml` (`skip_specs: true`) faltante en
  `2026-10-01-reportes-consumo-management`; al finalizar,
  `openspec validate --all --strict` **deberá** reportar 0 fallos.
- **REQ-SANE-002 (Ubiquitous / ALTO).** Los master specs **deberán**
  sincronizarse en `openspec/specs/` a partir de los deltas históricos
  (`001_core_logistics`, `002_stock_transfer`, `003_inventory_dashboard`)
  respetando el formato de spec principal (sin cabeceras de operación de
  delta), y `openspec validate --specs --strict` **deberá** pasar.

## 2. Tipado estático

- **REQ-SANE-003 (Ubiquitous / ALTO).** `mypy app/ tests/` **deberá**
  reportar 0 errores sobre los 73 archivos chequeados, usando los stubs
  oficiales `types-openpyxl==3.1.5.20260827` (dev-dependency pinneada) y
  anotaciones correctas de indexación/atributos en
  `app/services/plantilla_reporte.py`, `app/services/reportes.py`,
  `app/api/v1/auditoria.py` y sus tests.
- **REQ-SANE-004 (Unwanted / CRÍTICO).** Las correcciones de tipado
  **no deberán** alterar el comportamiento en tiempo de ejecución: las
  suites backend (pytest) **deberán** permanecer al 100 % y los archivos
  XLSX generados **deberán** ser byte-a-byte equivalentes a los actuales.

## 3. Assets huérfanos del frontend

- **REQ-SANE-005 (Option-driven / MEDIO).** **Si** una dependencia de
  `package.json` no posee ningún import en `frontend/src/`,
  **el sistema deberá** eliminarla junto con su entrada en el lockfile.
  Aplica a `recharts`; la ausencia de imports se verifica con búsqueda
  exhaustiva previa a la remoción.
- **REQ-SANE-006 (Ubiquitous / MEDIO).** El archivo residual
  `frontend/src/App.css` (no importado por ningún módulo) **deberá**
  borrarse; las suites vitest, lint y `tsc -b && vite build` **deberán**
  permanecer en verde sin cambios en páginas ni componentes.

## 4. Cobertura del script de semilla

- **REQ-SANE-007 (Event-driven / ALTO).** **Cuando** el script
  `seed_catalogo_oficial.py` se ejecute dos veces sobre la misma base,
  **el sistema deberá** probar automáticamente que la segunda corrida no
  duplica cargas: 53 filas de inventario intactas, exactamente 53 eventos
  `STOCK_INICIAL` y cero cargas nuevas.
- **REQ-SANE-008 (Unwanted / ALTO).** **Cuando** el conteo final de
  materiales activos difiera de 53, **el sistema deberá** probar que el
  script levanta `RuntimeError`; la cobertura se logra sin modificar la
  lógica interna del script (monkeypatch del listado en el test).

## 5. Gobernanza y trazabilidad

- **REQ-SANE-009 (Ubiquitous / MEDIO).** Cada requisito **deberá** mapear
  al menos a una prueba automatizada o verificación determinista
  (Constitution 7.1) y cada tarea de `tasks.md` **deberá** referenciar su
  identificador EARS.
- **REQ-SANE-010 (Unwanted / CRÍTICO).** El saneamiento **no deberá**
  introducir OAuth2/JWT, modificar el esquema `X-Actor` ni la tabla
  `administradores`, ni agregar enrutamiento por URL en el frontend, ni
  alterar la lógica de Fibra Óptica, `db/ddl.sql` o las migraciones
  existentes (intangibilidad runtime absoluta).
