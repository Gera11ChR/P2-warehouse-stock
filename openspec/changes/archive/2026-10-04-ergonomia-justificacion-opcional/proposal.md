# OpenSpec Change Proposal

## Change ID
`2026-10-04-ergonomia-justificacion-opcional`

## Summary
Convertir en OPCIONAL (no obligatorio) el campo de justificación/motivo en el
flujo de inventario, eliminando la fricción de captura sin romper la
trazabilidad del ledger inmutable (Constitution 2.4: el evento de auditoría
sigue registrándose; solo deja de exigirse texto no vacío):

1. **Modificación de materiales**: eliminar la obligatoriedad del
   motivo/justificación al modificar o ajustar stock/datos de materiales en
   Inventario General (`PATCH /api/v1/catalogo/{id_lista}`) y en Fibra Óptica
   (`PATCH /api/v1/fibra/{modulo}/materiales/{material_id}`).
2. **Transferencias TEAMS y DEVOL**: el campo "Motivo / Observaciones
   (obligatorio)" pasa a opcional en la vista de transferencias; se quita la
   etiqueta "(obligatorio)" de la UI y el payload puede enviar `null`, cadena
   vacía `""` u omitir el campo sin bloqueo en frontend ni backend.
3. **Todo el inventario (decisión de alcance)**: los endpoints de ajuste
   administrativo independientes (`POST /api/v1/ajustes/stock-almacen`,
   `POST /api/v1/fibra/ajuste`) también aceptan motivo opcional.
4. **Cancelación de movimientos**: el motivo del modal de cancelación en
   Transferencias pasa a opcional (el backend ya lo aceptaba como opcional:
   `CancelarMovimientoRequest.motivo: str | None` y default SQL de
   `fn_cancelar_movimiento`).

## Business Problem
- **Fricción operativa**: exigir una justificación textual en cada ajuste,
  transferencia o devolución ralentiza a los operadores de almacén; en flujos
  de alta frecuencia el texto se convierte en relleno sin valor forense.
- **Bloqueo por capas redundantes**: la obligatoriedad vive duplicada en
  validators Pydantic, RAISE de PostgreSQL, asserts en los endpoints y
  validaciones cliente, lo que impide cualquier envío sin texto aunque el
  negocio ya no lo requiera.
- **Contrato inconsistente**: el backend de TEAMS/DEVOL ya acepta
  `observaciones` opcional, pero la UI lo exige; la ergonomía deseada es que
  UI y API converjan en opcional.

## Proposed Changes
1. **Backend schemas**: relajar a `str | None` (o eliminar validators
   `_check_stock_motivo`) en `MaterialUpdate`, `FibraMaterialUpdateRequest`,
   `AjusteStockAlmacenRequest` y `FibraAjusteRequest`.
2. **Backend servicios/API**: firmas `motivo: str | None` en
   `transaccional.ajustar_stock_almacen / ajustar_stock_fibra /
   ajustar_stock_general`; eliminar los `assert payload.motivo is not None`
   de `api/v1/catalog.py` y `api/v1/fibra.py`.
3. **PostgreSQL**: eliminar el RAISE de motivo vacío en
   `fn_ajustar_stock_almacen` y `fn_ajustar_stock_fibra` (nueva migración
   Alembic `0023` + `ddl.sql`). La auditoría conserva el motivo tal como
   llega (`NULL` permitido) — el ledger sigue siendo append-only.
4. **Frontend**: quitar bloqueos, etiquetas "(obligatorio)" y errores de
   motivo en `Transferencias.tsx` (creación TEAMS/DEVOL y modal de
   cancelación), `MaterialForm.tsx` y `FibraMaterialForm.tsx`; enviar
   `motivo/observaciones` como `null` cuando el texto esté vacío.
5. **Contrato OpenSpec**: nueva `domain_rule: justificacion_opcional` y
   ajustes en `openspec/openspec.yaml` (`/ajustes/stock-almacen` y PATCH FO).

## Impact Assessment
- **Backend**: `app/schemas/{material,inventario,ajuste}.py`,
  `app/services/transaccional.py`, `app/api/v1/{catalog,fibra}.py`,
  `db/ddl.sql`, nueva migración `0023`.
- **Frontend**: `pages/Transferencias.tsx`, `components/MaterialForm.tsx`,
  `components/FibraMaterialForm.tsx`, comentarios en
  `services/{catalog,fibra}.ts` y `types.ts`.
- **Tests backend**: `test_ajuste_desde_material.py`, `test_fibra.py`,
  `test_ajustes.py`, `test_esquemas.py`, `test_teams.py`, `test_devol.py`,
  `test_cancelaciones.py`.
- **Tests frontend**: `Transferencias.test.tsx`, `MaterialForm.test.tsx`,
  `FibraOptica.test.tsx`.

## Out of Scope
- `DELETE /fibra/{modulo}/materiales/{id}` con stock > 0 (REQ-DEL-004
  conserva motivo obligatorio: eliminación física con existencias).
- Carga inicial, seguimientos (CONSUMO), operadores rápidos
  (`+Cantidad`/`Mover` — nunca exigieron motivo).
- `fn_cancelar_movimiento` (ya tolera motivo nulo con default en SQL).
