# OpenSpec Change Proposal

## Change ID
`2026-10-04-saneamiento-deuda-tecnica`

## Summary
Mantenimiento puro del proyecto: saneamiento de deuda técnica y recogida de
basura ("garbage collection") sin alterar ningún comportamiento en tiempo de
ejecución. El paquete abarca exclusivamente:

1. **Mantenimiento OpenSpec**: archivar los 6 paquetes implementados
   pendientes (`2026-09-28-nis-catalog-fixes`, `2026-09-29-fo-delete-fix`,
   `2026-10-01-reportes-consumo-management`,
   `2026-10-04-ergonomia-justificacion-opcional`,
   `2026-10-04-eliminar-buscador-a-granel`,
   `2026-10-04-eliminar-breadcrumb-dashboard`) y sincronizar los master
   specs en `openspec/specs/` desde los deltas de los paquetes archivados
   que los poseen.
2. **Saneamiento Mypy**: resolver los 56 errores de tipado estático con
   impacto runtime CERO (stubs de `openpyxl` y anotaciones en los servicios
   de reportes XLSX y sus tests).
3. **Limpieza de assets huérfanos del frontend**: eliminar la dependencia
   `recharts` (declarada pero sin imports) y borrar el residuo `src/App.css`
   (no importado por ningún módulo).
4. **Cobertura de semilla**: pruebas automatizadas para
   `backend/scripts/seed_catalogo_oficial.py` (idempotencia y aserción
   `== 53`) sin modificar la lógica interna del script.

## Business Problem
- **Gobernanza especulativa pendiente**: 6 paquetes completos siguen activos
  en `openspec/changes/` sin Fase 13 (archivado); `openspec/specs/` está
  vacío porque los deltas históricos nunca se sincronizaron; y
  `openspec validate --all --strict` reporta una falla preexistente en el
  paquete `2026-10-01-reportes-consumo-management` (falta `.openspec.yaml`).
- **Deuda de tipado**: `mypy app/ tests/` reporta 56 errores concentrados en
  5 de 73 archivos (openpyxl sin stubs + indexación/atributos de `object` +
  Literals) que no reflejan defectos de runtime, pero impiden usar el tipado
  como red de seguridad.
- **Basura de dependencias**: `recharts` y `src/App.css` son residuos del
  template/iteraciones previas: no aportan nada al bundle ni al runtime.
- **Sin red de seguridad del seed**: la idempotencia y la integridad final
  del catálogo oficial (53 materiales) dependen hoy de corridas manuales.

## Proposed Changes
1. **OpenSpec**: crear `.openspec.yaml` (`skip_specs: true`) en el paquete
   de reportes (único sin él) → `validate --all --strict` en verde → mover
   los 6 paquetes a `openspec/changes/archive/`. Luego, merge inteligente de
   los deltas `specs/*/spec.md` de los 4 paquetes archivados que los poseen
   (`001_core_logistics`, `002_stock_transfer`, `003_inventory_dashboard`)
   hacia `openspec/specs/` → `validate --specs --strict` en verde.
2. **Mypy**: pin `types-openpyxl==3.1.5.20260827` en dev-deps (stubs
   oficiales typeshed alineados a openpyxl 3.1.5) y corregir anotaciones en
   `app/services/plantilla_reporte.py`, `app/services/reportes.py`,
   `app/api/v1/auditoria.py`, `tests/test_plantilla_reporte.py` y
   `tests/test_reportes.py`. Meta: 0 errores. Cero cambios de semántica.
3. **Frontend**: eliminar `recharts` de `package.json` (+ lock) y borrar
   `src/App.css`. Gates: `npm test`, `npm run lint`, `npm run build`.
4. **Seed**: nuevo `tests/test_seed_catalogo.py` que ejecuta `main()` dos
   veces (idempotencia: 53 stocks intactos, 53 eventos `STOCK_INICIAL`,
   segunda corrida sin cargas nuevas) y verifica la aserción `== 53`
   (RuntimeError con catálogo alterado vía monkeypatch). El script no se
   modifica.

## Impact Assessment
- **Backend runtime**: CERO. Solo anotaciones de tipos, dev-deps y tests.
  Las funciones PL/pgSQL, routers, servicios y modelos quedan intactos.
- **Fibra Óptica**: INTANGIBLE. No se toca `db/ddl.sql`, ninguna migración,
  `fibra.py`, `transaccional.py` ni `security.py`.
- **Frontend runtime**: CERO. La eliminación de `recharts` y `App.css` no
  altera el bundle funcional (verificado: sin imports en `src/`).
- **Contrato OpenSpec**: `openspec/openspec.yaml` no cambia. El paquete es
  refactor/gobernanza puro → `skip_specs: true` (precedente: los 5 paquetes
  hermanos de 2026-09-28 a 2026-10-04).

## Out of Scope
- Correcciones de auditoría FO (`fn_*_fibra`), migraciones nuevas, cambios
  de `ddl.sql` y cualquier ajuste de seguridad/alcances (`SEC-002`).
- Corrección del PATCH con `descripcion: null` (comportamiento de negocio).
- OAuth2/JWT, esquema `X-Actor`, tabla `administradores`.
- Enrutador del lado del cliente (se mantiene `useState`).
- Cambios en `openspec/openspec.yaml` o `docs/constitution.md`.
