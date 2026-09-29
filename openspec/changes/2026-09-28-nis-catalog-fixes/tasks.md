# Implementation Tasks: 2026-09-28-nis-catalog-fixes

## Fase 1: Gobernanza y Sign-off
- [x] **1.1 Architecture Sign-off (`@arq-reviewer`)**: verificar que proposal/EARS preservan los invariantes del sistema (stock no-negativo, ledger inmutable, autoridad transaccional PostgreSQL). — Governance work.
- [x] **1.2 Specification Audit (`@auditor`)**: confirmar cero drift entre `docs/nis_report.md` y los EARS, y que cada tarea referencia su EARS. — Governance work.

## Fase 2: Backend
- [x] **2.1 U.M. dinámica (`@coder`)** — [REQ-UM-001/002]:
  - `app/schemas/material.py`: eliminar `_validate_um` y los `field_validator("u_m")` de `MaterialCreate`/`MaterialUpdate`; conservar `SUPPORTED_UNITS` solo como referencia/seed.
- [x] **2.2 Carga inicial ruteada (`@coder`)** — [REQ-CARGA-002/003]:
  - `app/services/transaccional.py`: añadir `cargar_stock_inicial_ruteada(session, *, almacen_id, material_id, cantidad, motivo)` que resuelva `seccion.tipo` y despache: GENERAL → `fn_cargar_stock_inicial`; FO_PAQUETE/FO_EN_USO → `fn_cargar_stock_inicial_fibra` con módulo mapeado. NO usar `_prechequear_seccion` sobre las raíces FO (exige `is_active`): validar solo existencia (404); la aritmética y auditoría permanecen 100 % en PostgreSQL.
  - `app/api/v1/catalog.py`: `crear_material` invoca el helper ruteado dentro del mismo `session.begin()` (atomicidad 4.1).

## Fase 3: Frontend
- [x] **3.1 Selector de destino (`@ui-agent`)** — [REQ-CARGA-001]:
  - `components/MaterialForm.tsx`: prop `seccionesDestino?: SeccionTransferible[]`; selector "Sección destino" con etiquetas operativas ("Fibra Óptica - Paquete/En Uso", GENERAL por nombre). SIN filtro `is_active` (las raíces FO son soft-inactivas).
  - `pages/SeccionGeneral.tsx`: `useSeccionesTransferibles()` → `MaterialForm`; `createMut.onSuccess` debe invalidar `['fibra', modulo]` cuando la carga inicial aterriza en una raíz FO (módulo derivado del `tipo` de la sección destino).
- [x] **3.2 Origen FO en Transferencias (`@ui-agent`/`@state-agent`)** — [REQ-TRF-001/002]:
  - `pages/Transferencias.tsx`: cuando la sección origen TEAMS es FO, consultar `listFibraStock(modulo)` (clave `['fibra', modulo]`) en lugar de `stockSeccion`; en DEVOL el origen sigue siendo el inventario del equipo.
  - Invalidaciones: en `procesarMut`/`cancelarMut`, además de `['stock', <id>]`, invalidar `['fibra', modulo]` cuando el extremo de sección corresponde a una raíz FO (origen TEAMS y destino DEVOL).

## Fase 4: Tests (secuencial, sesión principal — sin paralelismo)
- [x] **4.1 (`@tester`)** — [REQ-UM-001/002, REQ-CARGA-002/003]:
  - `tests/test_esquemas.py`: actualizar `TestUnidades` (el schema ya no rechaza nombres estáticos) y el comentario del seed en `conftest.py`.
  - `tests/test_catalogo_admin.py`: U.M. dinámica aceptada (201) + carga inicial con destino FO → stock en `inventario_fibra` + aserción del evento de auditoría `STOCK_INICIAL_FO` en el camino ruteado de `crear_material` (REQ-CARGA-003).
- [x] **4.2 (`@tester`)** — [REQ-TRF-001]:
  - `tests/test_fo_transferencias.py`: regresión — TEAMS desde FO descuenta `inventario_fibra` y preserva auditoría `modulo_fo`; DEVOL hacia FO acredita `inventario_fibra`.
- [x] **4.3 (`@tester`)** — [REQ-CARGA-001]:
  - `frontend/src/components/__tests__/MaterialForm.test.tsx`: etiquetas FO visibles en el selector de sección destino.
- [x] **4.4 (`@tester`)** — [REQ-TRF-002]:
  - Nuevo `frontend/src/components/__tests__/Transferencias.test.tsx`: al procesar/cancelar un movimiento con extremo FO, se invalidan las claves `['fibra', modulo]` y `['stock', <id>]` correspondientes.

## Fase 5: QA y consolidación
- [x] **5.1 Zero-Drift QA (`@qa-agent`)**: verificar consumo frontend contra contrato backend (secuencial, sin subagentes en paralelo). — Governance work.
- [x] **5.2 Final Integration (`@auditor`)**: regresión completa y cierre del paquete. — Governance work.

## Desviaciones y consecuencias documentadas (heredadas / aceptadas)
- Auditoría `STOCK_INICIAL_FO` atribuida a `CURRENT_USER` (preexistente; misma clase que sign-off §4.1 del paquete archivado).
- Renombrar una U.M. no reescribe `catalogo_materiales.u_m` de materiales existentes (dato denormalizado): esos materiales requerirán re-selección de U.M. al editarse. Consecuencia aceptada del modelo; normalización a FK queda fuera de alcance.
