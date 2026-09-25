# Domain Validation Report — Phase 0
**Change:** `2026-09-22-frontend-backend-alignment`
**Agents:** @arq-reviewer, @auditor
**Status:** APPROVED — Architectural direction ratified with binding governance conditions
**Date:** 2026-09-24

## 1. Pre-Phase Traceability Gate (Udoc2) — PASS

| Issue (#) | Proposal Item | EARS Requirement(s) |
|---|---|---|
| 1. ID LISTA innecesario | 3.1 | REQ-UI-001, REQ-UI-002 |
| 2. Ghost records | 3.2 | REQ-API-001, REQ-UI-003 |
| 3. Campos bloqueados | 3.3 | REQ-UI-004, REQ-API-002, REQ-API-003 |
| 4. Numeración comienza en 10 | 3.1 | REQ-UI-002 |
| 5. Modelo sparse de Equipos | 3.4 | REQ-DOMAIN-001, REQ-DOMAIN-002 |
| 6. FO inventarios independientes | 3.4 | REQ-DOMAIN-003, REQ-DOMAIN-004, REQ-DOMAIN-005, REQ-DOMAIN-006 |
| 7. Equipos nacen con inventario | 3.4 | REQ-DOMAIN-001, REQ-DOMAIN-002 |
| 8. Descripción en Auditoría | 3.5 | REQ-UI-006, REQ-API-008 |
| 9. Buscador masivo incompleto | 3.5 | REQ-UI-007, REQ-API-006, REQ-API-007 |
| 10. Categorías no persisten | 3.6 | REQ-API-004, REQ-API-005, REQ-UI-005 |

Cadena `Issue → Proposal Item → EARS Requirement → Task → Implementation → Test` íntegra.
Sin enlaces faltantes.

## 2. Issue Classification

| Issue | Classification | Backend Evidence | Domain Verdict |
|---|---|---|---|
| #1 ID LISTA | Functional Enhancement | `models/material.py:37` PK inmutable, FKs `ondelete=RESTRICT` | Sin cambio de dominio (abstracción DTO/UI) |
| #2 Ghost records | Bug Fix (brecha de contrato) | `services/catalogo.py:73,100`, `services/movimientos.py:37,170`, vista `0010:574` ya filtran; **gap real: `services/sparse_inventory.py:54` (`stock_seccion` sin filtro `is_active`)** | Sin cambio de dominio |
| #3a SKU bloqueado | Functional Enhancement | `schemas/material.py:80` `codigo` ya editable; bloqueo solo frontend | Sin cambio de dominio |
| #3b Stock bloqueado | Domain Change (ruta de mutación) | Stock vive en `inventario_almacen`; `fn_ajustar_stock_almacen` ya existe (`api/v1/ajustes.py`, migración `0011`) | Nuevo camino auditado en PUT material |
| #4 Numeración en 10 | Functional Enhancement | Consecuencia de PK SERIAL; UI genera índice 1-indexed | Sin cambio de dominio |
| #5 Modelo sparse Equipos | Domain Change (mayor) | `vw_inventario_equipo_completo` (`0010:557-574`) CROSS JOIN catálogo global | Depreca vista sparse |
| #6 FO independiente | Domain Change (mayor) | `secciones.tipo IN ('FO_PAQUETE','FO_EN_USO')` + legacy `fiber_variants.metros_restantes` (`0008`) | Nuevo modelo UM-driven |
| #7 Equipo nace con inventario | Domain Change (parte de #5) | `api/v1/equipos.py:52` crea equipo sin inventario; `inventario.py:48` 404 si vacío | Nueva relación equipo→inventario autónomo |
| #8 Descripción en Auditoría | Functional Enhancement | `api/v1/auditoria.py` filtra por `material_id`; requiere JOIN catálogo | Sin cambio de dominio |
| #9 Buscador masivo | Functional Enhancement | `services/catalogo.py:66-92` soporta sku/id_lista/ILIKE; falta rango descripción y contrato ordinal | Sin cambio de dominio |
| #10 Categoría no persiste | Bug Fix (alineación contrato) | `services/catalogo.py:20-35,111-126,143-157` ya persiste `categoria_id`; `MaterialOut.categoria` incluida | Backend mayormente conforme; desajuste frontend probable (`categoria` vs `categoria_id`/`nueva_categoria`, `extra="forbid"` → 422) |

## 3. Domain Impact Analysis

### New Entities / Relationships
- Inventario propio autónomo por `Equipo` (canonicalizado en `inventario_equipos`, sin vista derivada del catálogo global).
- Inventarios independientes `FO Paquete` y `FO En Uso` con esquema estándar (`CÓDIGO`, `DESCRIPCIÓN`, `U.M.`, `STOCK ACTUAL`, `STOCK MÍNIMO`, `ALERTA STOCK`), gobernados por `U.M.`.
- Campo `stock_actual` en el payload de edición de material (solo Inventario General), enrutado vía `fn_ajustar_stock_almacen`.
- Contrato ordinal del `Buscador a granel` (`start_index`, OFFSET/LIMIT deterministas).

### Deprecated Assumptions
- "ID LISTA = identificador permanente visible al operador" → deprecado en presentación (la PK de BD permanece inmutable).
- Modelo Sparse (herencia del catálogo global por todos los equipos) → deprecado.
- FO como secciones del inventario central + modelo `fiber_variants` (carretes/metros) → deprecado.
- Stock inmodificable desde el formulario de material → reemplazado por ajuste auditado con delta (jamás UPDATE directo).
- Legado `skus/warehouses/fiber_variants/team_inventory` (migraciones 0001–0008) → candidatos de limpieza en Phase 3.5.

### Inventory / Catalog Ownership Impacts
- Ownership pasa de "catálogo maestro + vistas derivadas" a "inventarios por alcance": `Inventario General` (secciones), por `Equipo`, `FO Paquete`, `FO En Uso`.
- `catalogo_materiales` permanece como identidad maestra de materiales (FK `material_id`), preservando movimientos y auditoría.

### Constitutional Check Summary
| Invariante | Riesgo | Mitigación ratificada |
|---|---|---|
| 2.4 Immutable Ledger | CRÍTICO | Delta vía `fn_ajustar_stock_almacen` con `motivo` obligatorio |
| 2.1 Non-Negative Balance | ALTO | CHECK constraints DB + validación en funciones |
| 4.1 Transactional Atomicity | ALTO | `FOR UPDATE` sobre tablas aisladas (Phase 2, @dba-guard) |
| 2.3 State Serialization | MEDIO | Stored functions serializan transiciones |
| 6.2 Audit Events | MEDIO | LEFT JOIN legible; historial íntegro, sin filtros de actividad |
| 3.1/3.2 Authorization | MEDIO | Ajustes restringidos a administradores (RBAC + MFA 3.3) |

Sin violación constitucional. Sin necesidad de enmienda a `constitution.md`.

## 4. Approved Architectural Direction (ratified)

1. **Equipos:** inventario autónomo = filas físicas de `inventario_equipos`; se elimina la vista sparse. Creación de equipo inicializa inventario vacío (cero herencia). TEAMS/DEVOL siguen siendo el único mecanismo de entrada/salida de stock.
2. **Fibra Óptica:** `FO Paquete` y `FO En Uso` pasan a inventarios independientes con esquema estándar gobernado por `U.M.`; deprecar `fiber_variants` y los tipos de sección FO.
3. **Stock editable:** solo en Inventario General vía delta → `fn_ajustar_stock_almacen` con `motivo` obligatorio; jamás UPDATE directo.
4. **Gap de ghost records:** incluir filtro `is_active=True` en `stock_seccion()` dentro del alcance de Task 3.1.

### Binding Governance Conditions (innegociables)
1. **Preservación operativa:** TEAMS/DEVOL mantienen su contrato 100% funcional sin alteraciones (REQ-API-009).
2. **Blindaje constitucional:** `motivo` obligatorio en `fn_ajustar_stock_almacen`; validación no-negativa a nivel DB.
3. **Cero registros fantasma:** `is_active=True` estricto en `stock_seccion` y todas las vistas operativas de inventario.
4. **Backend-First (SDD v7.1):** prohibido modificar `frontend/` hasta que Fases 1–5 del backend estén completadas y aprobadas.

### Binding Domain Clarifications
1. **Equipos:** inventario propio autónomo (no "catálogo de equipo"): vacío al nacer, poblado SOLO por movimientos auditados, cero filas fantasma (stock 0 no se muestra), trazabilidad al movimiento de origen.
2. **Buscador a granel:** el rango por número de lista se resuelve 100% en backend con posicionamiento ordinal determinista (`ORDER BY descripcion ASC, id_lista ASC`; `OFFSET = X-1`, `LIMIT = Y-X+1`; respuesta incluye `start_index`). Prohibido descargar datasets completos al cliente.
3. **Auditoría:** historial íntegro e inmutable; `LEFT JOIN` a materiales SIN filtro `is_active` (descripción/SKU legibles); etiqueta opcional `[Inactivo]`; la desactivación solo afecta selectores operativos de nuevos movimientos.

## 5. Exit Criteria — Fase 0

- [x] Every issue classified (10/10).
- [x] Architectural direction approved with binding conditions.
- [x] Domain impact identified (entities, relationships, deprecations, ownership).
