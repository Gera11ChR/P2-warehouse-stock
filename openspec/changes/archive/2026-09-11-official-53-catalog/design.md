# Design: Catálogo Oficial de 53 SKUs (soft-delete + seed idempotente)

## Context

- Postgres (`p2`), SQLAlchemy async + Alembic head `0008`. `skus` es PK `sku` referenciada con `ondelete=RESTRICT` desde `warehouse_inventory`, `stock_movements`, `transfer_line_items`, `fiber_variants`, `team_inventory`, `fleet_allocations` y `legacy_stock_quarantine` — por eso los 58 SKUs demo con historial no pueden borrarse físicamente (Constitution 2.4, ledger append-only).
- El catálogo demo actual (58 SKUs: `CBL-*`, `FO-*`, etc.) tiene 58 `warehouse_inventory` (CENTRAL 20 / NORTE 19 / SUR 19), 58 `stock_movements` RECEIPT y 2 transferencias (`CBL-FO-001`, `CBL-CORD-001`) que deben permanecer.
- `Sku` no tiene columna de inactividad; `Warehouse` sí (`is_active`).
- La plantilla oficial DMS registra los 53 ítems con STOCK ACTUAL=0, STOCK MÍNIMO=0, "SIN STOCK".
- Spec 003 `REQ-MAT-003` exigía 58 materiales; el delta de esta change lo corrige a 53.

## Goals / Non-Goals

**Goals:**
- Catálogo activo = exactamente los 53 SKUs oficiales, sin duplicados ni faltantes.
- Seed estrictamente idempotente y no destructivo (nunca TRUNCATE/DELETE sobre filas con FK).
- Historiales (transfers, movements, audit) con conteos no decrecientes y FKs válidas.

**Non-Goals:**
- No tocar RBAC/`user_warehouse_scopes`, auth/MFA, lógica o endpoints de `stock-transfers`, ni tablas contables.
- No crear variantes de fibra (`fiber_variants`) en el seed — el catálogo CF-* se registra; los rollos "En Uso" los registra el operador.
- No rediseñar el vocabulario de unidades (los 53 ítems ya caben en `SUPPORTED_UNITS`).

## Decisions

1. **Soft-delete vía columna nueva `skus.is_active` (migración `0009`, expand-only)** — alternativa descartada: reutilizar `tipo` o `categoria` para marcar inactividad (rompe semántica y filtros existentes); alternativa descartada: borrado físico con historial (viola FK RESTRICT y Constitution 2.4).
2. **Seed = upsert de los 53 + barrido de desactivación**: para cada SKU oficial, `INSERT ... ON CONFLICT (sku) DO UPDATE` (o get+update) fijando `is_active=True` y campos del catálogo; luego `UPDATE skus SET is_active=False WHERE sku NOT IN (lista oficial)`. Así el seed **repara** catálogos divergentes (reactiva oficiales, depura demo) y es idempotente por construcción.
3. **Stock inicial 0 en CENTRAL sin movimientos**: `warehouse_inventory` con `on_hand_quantity=0` (cumple CHECK `>=0`); no se insertan `stock_movements` porque `quantity_change <> 0` los prohibiría y un RECEIPT de 0 sería una falsedad contable (ledger append-only). El stock real entra por ingesta masiva.
4. **Filtro `is_active` en el backend, no en el frontend**: `GET /materials`, `GET /inventory`, `GET /kpis` (total_materiales, stock_total vía join a skus activos, alertas_stock), `GET /fiber-optics` (join con sku activo). El frontend queda intacto y la tabla principal muestra 53 filas (53 SKUs × CENTRAL).
5. **`DELETE /materials` → soft-delete**: marca `is_active=False` con evento de auditoría `MATERIAL_DELETE`; se elimina la dependencia de `_assert_deletable` en ese camino (ya no hay riesgo de FK). Materiales inactivos responden 422 "Material no encontrado" en GET/PATCH (semántica de catálogo cerrado).
6. **Almacenes CENTRAL/NORTE/SUR intactos**: la consolidación es de custodia (todo stock oficial en CENTRAL), no de esquema; NORTE/SUR y sus transferencias siguen operando (spec 002 intacta).

## Risks / Trade-offs

- [Los KPI `stock_total` y `alertas_stock` podrían incluir stock demo inactivo] → Mitigación: ambos joins filtran `Sku.is_active = true`.
- [Alguien con acceso SQL podría reactivar un SKU demo por error] → Mitigación: el seed es re-ejecutable y siempre re-aplica el estado canónico (53 activos).
- [La búsqueda de SKUs demo históricos deja de resolverlos en el frontend] → Aceptado: el catálogo oficial es la única superficie; la historia permanece en transferencias/auditoría.
- [Revert de la migración] → `downgrade` elimina la columna; el seed anterior quedaría restaurado sin pérdida de datos (la columna es aditiva).

## Migration Plan

1. `alembic upgrade head` (0009) en dev y en `p2_test` (los fixtures de pytest ya lo hacen).
2. `python -m app.seed` dos veces consecutivas en dev.
3. Verificar: 53 activos exactos, 58 demo inactivos, conteos de historial idénticos, `pytest` 100 %, build frontend limpio, `openspec validate --specs --strict`.
4. Rollback: `alembic downgrade -1` + re-seed del catálogo anterior (solo si el cambio no se aprueba).
