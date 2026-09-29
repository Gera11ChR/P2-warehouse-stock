# OpenSpec Change Proposal

## Change ID
`2026-09-28-nis-catalog-fixes`

## Summary
Corregir dos hallazgos operativos del catálogo en la Sección General
(según `docs/nis_report.md`) y preservar/corregir el invariante de ruteo de
inventario de Fibra Óptica en Transferencias:

1. La "SECCIÓN DESTINO" de la Carga Inicial (alta de material) debe incluir
   "Fibra Óptica - Paquete" y "Fibra Óptica - En Uso", y rutear el stock
   inicial a `inventario_fibra` (no a `inventario_almacen`).
2. La validación de U.M. debe ser dinámica contra la tabla `ums`, aceptando
   U.M. creadas o renombradas por el administrador (sin Enum estático).
3. INVARIANTE: al seleccionar una raíz FO en Transferencias (TEAMS/DEVOL),
   la consulta de inventario de origen debe direccionarse a
   `inventario_fibra` sin romper el flujo transaccional.

## Business Problem
- **Carga Inicial limitada:** el selector de sección destino solo muestra
  "Inventario General"; el operador no puede asignar stock inicial a las
  raíces de Fibra Óptica durante el alta de material.
- **U.M. inflexibles:** una U.M. creada o renombrada por el administrador
  provoca error 422/400 al guardar el material, porque el backend valida
  contra el Enum estático `SUPPORTED_UNITS`.
- **Origen FO sin inventario:** la consulta de inventario de origen en
  Transferencias lee `inventario_almacen`; para las secciones FO devuelve
  vacío (su stock vive en `inventario_fibra`), impidiendo armar el carrito
  desde esas secciones.

> Nota de trazabilidad: `nis_report.md` §3 declara Transferencias operativa
> (los selectores FO aparecen). REQ-TRF-001 corrige una brecha latente no
> reportada explícitamente: el listado de inventario de origen quedaba
> vacío al elegir una raíz FO, por lo que el carrito no se podía construir
> desde esas secciones.

## Proposed Changes
1. **Frontend MaterialForm/SeccionGeneral:** el selector "Sección destino"
   de Carga Inicial consume `GET /api/v1/inventario/secciones/transferibles`
   (GENERAL activas + raíces FO con etiquetas operativas).
2. **Backend:** nuevo `cargar_stock_inicial_ruteada` en
   `services/transaccional.py` que resuelve `seccion.tipo` y despacha a
   `fn_cargar_stock_inicial` (GENERAL) o `fn_cargar_stock_inicial_fibra`
   (FO_PAQUETE/FO_EN_USO → `inventario_fibra`). `crear_material` usa el
   helper ruteado.
3. **Backend:** eliminar el validator estático `_validate_um` de
   `MaterialCreate`/`MaterialUpdate`; la validación autoritativa permanece
   dinámica en `services/catalogo._validar_um` contra la tabla `ums`.
4. **Frontend Transferencias:** cuando el origen TEAMS (o destino DEVOL) es
   una raíz FO, la consulta de inventario correspondiente usa
   `GET /fibra/{modulo}` en lugar de `stockSeccion`, con invalidaciones de
   caché alineadas al módulo FO.

## Impact Assessment
- **Backend:** `app/schemas/material.py`, `app/services/transaccional.py`,
  `app/api/v1/catalog.py`.
- **Frontend:** `components/MaterialForm.tsx`, `pages/SeccionGeneral.tsx`,
  `pages/Transferencias.tsx`.
- **Tests:** `tests/test_esquemas.py`, `tests/test_catalogo_admin.py`,
  `tests/test_fo_transferencias.py`, `frontend/.../MaterialForm.test.tsx`.

## Out of Scope
- Cambios en la lógica transaccional TEAMS/DEVOL del backend (ya correcta
  desde el paquete archivado 2026-09-28-equipos-despliegue-management).
- Nuevo modelo de autenticación o MFA.
- Migraciones de esquema (no se requiere DDL nuevo).
