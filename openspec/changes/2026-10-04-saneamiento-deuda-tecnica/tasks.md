# Implementation Tasks: 2026-10-04-saneamiento-deuda-tecnica

> RESTRICCIÓN DE EJECUCIÓN: cero subagentes en paralelo sobre el mismo
> archivo. Las fases se ejecutan de forma estrictamente secuencial:
> artefactos → OpenSpec → tipado → frontend → seed → verificación.

## Fase 0: Artefactos OpenSpec
- [x] **0.1** `proposal.md` + `EARS.md` + `.openspec.yaml` + `tasks.md`
  creados — [REQ-SANE-001..010]
- [x] **0.2** Verificación de intangibilidad: `db/ddl.sql`, migraciones,
  `fibra.py`, `transaccional.py`, `security.py` y `openspec/openspec.yaml`
  intactos (git diff confirma cero cambios sobre ellos).

## Fase 1: Mantenimiento OpenSpec — reparar y archivar
- [x] **1.1** `.openspec.yaml` (`skip_specs: true`) creado en
  `2026-10-01-reportes-consumo-management` — [REQ-SANE-001]
- [x] **1.2** `openspec validate --all --strict` → 7/7 en verde (6 paquetes
  pendientes + el nuevo) — [REQ-SANE-001]
- [x] **1.3** Los 6 paquetes movidos a `openspec/changes/archive/` vía
  `git mv` (13 archivados en total; aviso: el paquete de reportes tenía
  tasks 32/40 marcados, implementación completa verificada) —
  [REQ-SANE-001]

## Fase 2: Mantenimiento OpenSpec — sincronizar master specs
- [x] **2.1** Leídos SOLO los deltas `specs/*/spec.md` de los 4 paquetes
  archivados con deltas (2026-09-02, 2026-09-04, 2026-09-11 ×2); jamás
  proposals/EARS — [REQ-SANE-002]
- [x] **2.2** Merge inteligente hacia `openspec/specs/`:
  `001_core_logistics` (RF-3, RF-5, REQ-STOCK-001..004),
  `002_stock_transfer` (REQ-STOCK-006..019) e `003_inventory_dashboard`
  (REQ-DASH-001..014, REQ-FIBER-001..003, REQ-TEAM-001..003,
  REQ-MAT-001..006, REQ-CAT-001..003; MODIFIED aplicados
  cronológicamente) — [REQ-SANE-002]
- [x] **2.3** `openspec validate --specs --strict` → 3/3, 0 violaciones —
  [REQ-SANE-002]

## Fase 3: Saneamiento Mypy (impacto runtime CERO)
- [x] **3.1** `types-openpyxl==3.1.5.20260827` pinneado en dev-deps de
  `backend/pyproject.toml` e instalado en `.venv` — [REQ-SANE-003]
- [x] **3.2** Anotaciones: `plantilla_reporte.py` (cast de `wb.active` a
  `Worksheet`; `_images`/`_style` vía `cast(Any, …)`), `reportes.py`
  (`cast(TipoActa, acta.tipo)`; alias `sa_cast` para el cast de SQLAlchemy),
  `auditoria.py` (`condiciones: list[ColumnElement[bool]]`) —
  [REQ-SANE-003]
- [x] **3.3** Anotaciones en `test_plantilla_reporte.py` (helpers tipados
  a `Worksheet`, casts de `_images`/Literals) y `test_reportes.py`
  (`_xlsx` tipado a `Worksheet`, narrowing `detalles = evento.detalles or
  {}`) — [REQ-SANE-003]
- [x] **3.4** `mypy app/ tests/` → **0 errores en 74 archivos**;
  tests/test_plantilla_reporte.py + tests/test_reportes.py → 50 passed
  (runtime byte-equivalente) — [REQ-SANE-003/004]

## Fase 4: Assets huérfanos del frontend
- [x] **4.1** Grep exhaustivo: `recharts` sin imports en `frontend/src/`
  (solo package.json/lock); `App.css` sin referencias — [REQ-SANE-005]
- [x] **4.2** `recharts` eliminado de `package.json`; lockfile regenerado
  con `npm install` (0 coincidencias de recharts) — [REQ-SANE-005]
- [x] **4.3** `frontend/src/App.css` borrado (`git rm`) — [REQ-SANE-006]
- [x] **4.4** Gates frontend: vitest **341/341 passed**, `eslint .`
  limpio, `tsc -b && vite build` ✓ (chunk-size advisory preexistente) —
  [REQ-SANE-005/006]

## Fase 5: Cobertura del script de semilla
- [x] **5.1** Nuevo `tests/test_seed_catalogo.py` (import lazy del script
  vía `sys.path`; `P2_DATABASE_URL` apuntado a `p2_test` por conftest) —
  [REQ-SANE-007/008]
- [x] **5.2** Caso idempotencia: dos corridas de `main()` → 53 filas de
  inventario con stock 5 intactas, exactamente 53 eventos `STOCK_INICIAL`,
  cero cargas nuevas — [REQ-SANE-007]
- [x] **5.3** Caso aserción `== 53`: `RuntimeError` (`"!= 53"`) con listado
  alterado vía monkeypatch; el script permanece intacto — [REQ-SANE-008]

## Fase 6: Documentación sincronizada
- [x] **6.1** README: badge Mypy → `0_Errors_73_files`; tabla §4.3
  actualizada; §5 (estructura: 1 activo + 13 archivados, specs
  sincronizados); §9 (conteos); §10 ítems 2-6 marcados RESUELTO
  (2026-10-04) con evidencia — [REQ-SANE-009]

## Fase 7: Verificación Zero-Drift (QA)
- [x] **7.1** Backend: `pytest tests/ -q` → **305 passed** (303 baseline +
  2 de seed) — [REQ-SANE-004/007/008]
- [x] **7.2** `mypy app/ tests/` → 0 errores — [REQ-SANE-003]
- [x] **7.3** Frontend: vitest 341/341, lint limpio, build ✓ —
  [REQ-SANE-005/006]
- [x] **7.4** `openspec validate --all --strict` → 4/4 y
  `openspec validate --specs --strict` → 3/3, 0 fallos —
  [REQ-SANE-001/002]

## Fase 8: Registro y Commit
- [x] **8.1** `tasks.md` completo con resultados.
- [x] **8.2** Revisión de solo-archivos-autorizados (Fase 13, `@auditor`)
  y commit en `refactor/saneamiento-deuda-tecnica`.
