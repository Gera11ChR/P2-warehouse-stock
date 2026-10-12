# Plan técnico (Backend-First): Inversión de consumo

**Change ID:** `2026-10-12-inversion-consumo` · **Spec:** `spec.md` (RF-1..RF-14)

## 1. Impacto constitucional

§2.1/§2.3 se conservan (validación de stock y `FOR UPDATE` dentro de la función). §2.4: no se modifican `auditoria_eventos` ni `actas_reportes`; el backfill solo recalcula columnas de `seguimiento_items`. §4.1: la atomicidad sigue en PL/pgSQL. Sin enmienda constitucional. Verificado: no hay triggers ni vistas sobre `seguimiento_items` (los triggers de `0022` cubren solo `auditoria_eventos` y `actas_reportes`).

## 2. Alembic `0025_consumo_directo` (`down_revision = "0024"`, solo `backend/alembic/versions/`)

`upgrade()`:
1. `ADD COLUMN cantidad_consumida_n INT`.
2. `UPDATE seguimiento_items SET cantidad_consumida_n = cantidad_tomada - cantidad_sobrante WHERE cantidad_sobrante IS NOT NULL`.
3. `DROP CONSTRAINT ck_seguimiento_items_sobrante`; `DROP COLUMN cantidad_consumida` (generada); `DROP COLUMN cantidad_sobrante`.
4. `RENAME cantidad_consumida_n → cantidad_consumida`; `ADD CONSTRAINT ck_seguimiento_items_consumida CHECK (cantidad_consumida IS NULL OR (cantidad_consumida >= 0 AND cantidad_consumida <= cantidad_tomada))`.
5. `DROP FUNCTION fn_cerrar_seguimiento(INT, JSONB, TEXT, TEXT)`; `CREATE FUNCTION fn_cerrar_seguimiento(p_seguimiento_id INT, p_consumidos JSONB, p_usuario TEXT, p_observaciones_cierre TEXT DEFAULT NULL) RETURNS VOID`.

`downgrade()`: inverso exacto (restaura `cantidad_sobrante = tomada − consumida`, la columna generada, el check y la función de `0024` embebida verbatim). Verificación upgrade → downgrade → upgrade con md5 de `pg_get_functiondef` y checksum de `seguimiento_items`.

## 3. PL/pgSQL `fn_cerrar_seguimiento`

- Bloquea el seguimiento ABIERTA (`FOR UPDATE`); mensajes "no se encuentra en estado ABIERTA" / "no encontrado" sin cambio.
- `p_consumidos` NULL o no arreglo → `El payload de consumidos debe ser un arreglo JSON.`
- Por línea: duplicado, material ajeno (`no pertenece a este seguimiento`) y `Consumo inválido para el material ID LISTA % (máximo %).` si < 0 o > tomada.
- Completitud: todo material del seguimiento debe aparecer, si no `Falta la cantidad consumida del material ID LISTA %.` (se valida ANTES de bloquear o descontar inventario).
- Bloquea `inventario_equipos` `FOR UPDATE` ordenado; exige stock ≥ consumida o `Stock insuficiente en la Unidad ID % …` (texto vigente desde 0024).
- `UPDATE seguimiento_items SET cantidad_consumida`; `UPDATE inventario_equipos SET stock_actual = stock_actual − consumida`; evento `SEGUIMIENTO_CERRADO {cantidad_tomada, cantidad_consumida, stock_remanente_equipo, observaciones_cierre}`; snapshot del acta con `cantidad_tomada`/`cantidad_consumida`; seguimiento CERRADA. Misma transacción.

## 4. FastAPI / Pydantic v2 (solo `backend/app`)

- `schemas/seguimiento.py`: `SobranteLine → ConsumoLine {material_id: int>0, cantidad_consumida: int>=0}`; `CerrarSeguimientoRequest {consumidos: list[ConsumoLine] (obligatorio, min_length=1), observaciones_cierre}`; validador de duplicados; `extra="forbid"`; `SeguimientoItemOut` sin `cantidad_sobrante`.
- `api/v1/seguimientos.py`: `payload.consumidos`; docstring actualizado.
- `services/transaccional.py`: `cerrar_seguimiento(consumidos=…)`, SQL `:consumidos`; mapeo `Consumo inválido → 400`, `Falta la cantidad consumida → 422`, se retira `Sobrante inválido`.
- `models/seguimiento.py`: `cantidad_consumida` columna real y nuevo `CheckConstraint`; se elimina sobrante/`Computed`.
- `schemas/reporte.py`, `services/reportes.py`: sin `cantidad_sobrante`; las actas antiguas se leen por `cantidad_consumida` (presente en ambos formatos de snapshot).
- `openspec/openspec.yaml` (cerrar seguimiento): `requestBody` `consumidos` y respuestas 400/422.

## 5. React / TypeScript (solo `frontend/src`; bloqueado hasta T10)

- `types.ts`, `schemas/seguimiento.ts` (`consumoItemSchema`, `cerrarSeguimientoSchema {consumidos}`), `services/seguimientos.ts`, `hooks/useCerrarSeguimiento.ts`.
- `components/SeguimientoCierreForm.tsx`: etiqueta "Consumido", campo vacío con captura obligatoria, rango 0..tomada, ayuda y placeholder sin "sobrante".
- `components/ReporteConsumoTable.tsx`: retira columna Sobrante. `components/SeguimientoPanel.tsx`: confirmación sin "sobrantes".
- Tests afectados + barrido de "sobrante".

## 6. Tests backend (REQ-CONSUMO-NNN)

Nuevo `tests/test_inversion_consumo.py` (RF-3..RF-13, incl. migración con backfill y OpenAPI). Reescribir referencias a sobrante en `test_seguimientos`, `test_reportes`, `test_operadores_rapidos` y `sql_tests/test_fase1_consumo`.

## 7. Decisiones y riesgos

D1 Columna real en vez de generada. D2 Líneas obligatorias. D3 Ruptura de contrato deliberada (sin alias `sobrantes`); migración y API se despliegan juntas.
Riesgos: backfill (checksum antes/después) · cierre en vuelo durante el despliegue · actas antiguas (test con snapshot con y sin sobrante).
