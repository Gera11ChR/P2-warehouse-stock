# Plan Técnico: Inventario FO unificado, Valor Unitario y Valor Total (Backend-First)

**Change ID:** `2026-10-fo-unificado-valor-unitario` · **Fase 5 (Planificación)**
**Cubre:** `RF-1`..`RF-10` de `spec.md`. Todo término de este documento es normativo para `tasks.md`.
**Revisores de la fase:** `@arq-reviewer` (coherencia), `@dba-guard` (persistencia), `@sec-ops` (seguridad).

> **Fuente de verdad del esquema:** la cadena Alembic (`backend/alembic/versions/`, cabeza actual `0026`). `backend/db/ddl.sql` está desfasado respecto de las migraciones `0016+` (aún contiene `despliegues`); `@dba-guard` decide en T2 si lo sincroniza solo en las secciones tocadas o lo deja marcado como referencia histórica. Ninguna decisión de este plan depende de `ddl.sql`.

## 0. Principios de diseño

1. PostgreSQL decide y ejecuta: toda aritmética de stock **y de valor** vive en SQL/PL/pgSQL; FastAPI valida y transporta; React renderiza lo que devuelve la API (`.agents.md` §5, `domain_rules.transaction_delegation`).
2. El ledger no se reescribe (§2.4): ni eventos, ni movimientos, ni secciones históricas se modifican en su contenido.
3. Una sola fuente de `valor_unitario`: el catálogo maestro; los tres inventarios lo muestran por JOIN.
4. Contrato sin `modulo`: el concepto desaparece del dominio vivo y solo sobrevive como **valor histórico** en el ledger.

---

## 1. Capa de Persistencia (PostgreSQL 18 / PL/pgSQL / Alembic)

### 1.1 Migración `0027_fo_unificado_valor_unitario.py` (`down_revision = "0026"`)

Una sola revisión, transaccional, en este orden (cada paso asume el anterior):

| Paso | Operación | RF |
| :-- | :-- | :-- |
| 1 | `ALTER TABLE catalogo_materiales ADD COLUMN valor_unitario NUMERIC(12,3) NOT NULL DEFAULT 1.000;` + `CHECK (valor_unitario >= 0)` (`ck_catalogo_valor_unitario_non_negative`). El `DEFAULT` rellena todo el catálogo existente con `1.000`. | RF-2, RF-3 |
| 2 | **Tipos decimales** (ver §1.2): `ALTER COLUMN ... TYPE NUMERIC(12,3)` en existencias, cantidades y ledger. Los `CHECK` (`>= 0`, `> 0`, `consumida <= tomada`) se conservan; `DEFAULT 0` se re-declara como `0`. | RF-6 |
| 3 | **Fusión FO** (§1.3): evento de auditoría por material, reemplazo de PK, eliminación de `modulo`. | RF-1, RF-7 |
| 4 | Sección de ruteo única: `ALTER ... ck_secciones_tipo CHECK (tipo IN ('GENERAL','FO','FO_PAQUETE','FO_EN_USO'))` e `INSERT INTO secciones (nombre, tipo, is_active) VALUES ('Inventario FO','FO', FALSE)` (idempotente por `nombre` único). `FO_PAQUETE`/`FO_EN_USO` **se conservan** (referenciadas por `movimientos_*`). | RF-1, RF-9 |
| 5 | **Stored functions** re-publicadas con tipos decimales y sin `p_modulo` (§1.4); `DROP FUNCTION` de las firmas anteriores para evitar sobrecargas ambiguas. | RF-1, RF-6 |
| 6 | `fn_auditar_modificacion_material` + `tg_auditar_modificacion_material` extendidos con `valor_unitario` (§1.5). | RF-7 |
| 7 | Nueva `fn_valor_total_inventario()` (§1.6). | RF-4 |

### 1.2 Inventario de columnas que pasan a `NUMERIC(12,3)`

`@dba-guard` confirma la lista por introspección del esquema real (`information_schema.columns`) antes de escribir la migración; deben cubrirse como mínimo:

| Tabla | Columna | Nota |
| :-- | :-- | :-- |
| `inventario_almacen` | `stock_actual` | `CHECK >= 0` se conserva |
| `inventario_fibra` | `stock_actual` | idem |
| `inventario_equipos` | `stock_actual` | idem |
| `movimientos_detalle` | `cantidad` | `CHECK cantidad > 0` se conserva |
| `seguimiento_items` | `cantidad_tomada`, `cantidad_consumida` | `CHECK 0 <= consumida <= tomada` se conserva; (tras `0025` ya no existe `cantidad_sobrante` ni columna generada) |
| `auditoria_eventos` | `cantidad` | **Ledger append-only (R2)**: el `ALTER TYPE` **debe** usar cast explícito `USING cantidad::NUMERIC(12,3)`; no dispara triggers de fila (`tg_ledger_auditoria_inmutable` es BEFORE UPDATE/DELETE) ni cambia valores. Visto bueno dual `@arq-reviewer` (T1, APROBADO: aceptable sin enmienda) + `@dba-guard` por escrito; la prueba `test_migracion_0027` asevera identidad **numérica de valores** previos (no solo conteo) y contenido. |

**No cambian:** `stock_minimo`, `stock_minimo_local` (INT, fuera de alcance), todo `id`/`*_id` (INTEGER/BIGINT), `actas_reportes` (snapshot JSONB: sin cambio de esquema).

Dependencias: no hay vistas vivas sobre estas columnas (`vw_inventario_equipo_completo` y `current_stock_view` fueron eliminadas en `0012`/`0004`); `@dba-guard` lo reverifica con `pg_depend` y, si apareciera alguna, la recrea en la misma migración.

### 1.3 Fusión de Inventario FO

```sql
-- (a) trazabilidad: un evento por material fusionado (INSERT permitido; ledger append-only)
INSERT INTO auditoria_eventos (usuario, tipo_accion, material_id, cantidad, resultado, detalles)
SELECT 'migracion-0027', 'FO_UNIFICADO', material_id, SUM(stock_actual), 'OK',
       jsonb_build_object(
         'modulo','Inventario FO',
         'valores_anteriores', jsonb_object_agg(modulo, stock_actual),
         'valores_nuevos', jsonb_build_object('stock_actual', SUM(stock_actual)))
FROM inventario_fibra GROUP BY material_id;

-- (b) agregación y reemplazo de clave
CREATE TEMP TABLE _fo_agg ON COMMIT DROP AS
  SELECT material_id, SUM(stock_actual) AS stock_actual, MAX(updated_at) AS updated_at
  FROM inventario_fibra GROUP BY material_id;
DELETE FROM inventario_fibra;                       -- tabla de saldo mutable, no ledger
ALTER TABLE inventario_fibra DROP CONSTRAINT inventario_fibra_pkey,
                             DROP CONSTRAINT ck_inventario_fibra_modulo,
                             DROP COLUMN modulo;
ALTER TABLE inventario_fibra ADD CONSTRAINT inventario_fibra_pkey PRIMARY KEY (material_id);
INSERT INTO inventario_fibra (material_id, stock_actual, updated_at)
  SELECT material_id, stock_actual, updated_at FROM _fo_agg;
```

Verificación interna de la migración: `SUM(stock_actual)` antes = `SUM(stock_actual)` después; si difiere, `RAISE EXCEPTION` y la transacción completa revierte (§4.3). Los nombres de columnas de `auditoria_eventos` se confirman contra el esquema real (`usuario`, `tipo_accion`, `material_id`, `cantidad`, `resultado`, `detalles`). El índice `ix_inventario_fibra_material` pasa a ser redundante con la PK y se elimina.

### 1.4 Stored functions afectadas

Las firmas conservan nombre y orden de parámetros; solo cambian tipos y se elimina `p_modulo`/`p_origen_modulo`/`p_destino_modulo`. `@dba-guard` toma como base el **cuerpo vigente** (última migración que las definió) y modifica lo mínimo.

| Función (última versión) | Cambio |
| :-- | :-- |
| `fn_procesar_movimiento(p_movimiento_id INT)` (0026) | Variables locales `v_stock_*`, `v_nuevo_stock_origen` → `NUMERIC(12,3)`. Las ramas `FO` resuelven `inventario_fibra` por `material_id`. Origen/destino de tipo `FO`, `FO_PAQUETE` o `FO_EN_USO` enrutan al mismo inventario (acepta BORRADOR legacy, caso E8). Orden de bloqueo `FOR UPDATE` determinista (origen, material) intacto. |
| `fn_cancelar_movimiento(...)` (0026) | Idem; reversión exacta con decimales; `FO_PAQUETE`/`FO_EN_USO` históricos → inventario FO unificado (**RF-9**). |
| `fn_cargar_stock_inicial(...)` | `p_cantidad NUMERIC(12,3)`. |
| `fn_cargar_stock_inicial_fibra(p_material_id, p_cantidad, p_motivo)` | Se elimina `p_modulo`; rechaza si ya existe fila del material. |
| `fn_ajustar_stock_almacen(...)` (0023) | `p_nuevo_stock NUMERIC(12,3)`; diferencial decimal; motivo opcional (sin cambio). |
| `fn_ajustar_stock_fibra(p_material_id, p_nuevo_stock, p_motivo)` (0023) | Sin `p_modulo`; decimal. |
| `fn_ajustar_stock_general(...)` | `p_nuevo_stock NUMERIC(12,3)`. |
| `fn_eliminar_inventario_fibra(p_material_id, p_motivo)` (0015) | Sin `p_modulo`; snapshot de auditoría sin `modulo`; reglas de motivo y `FOR UPDATE` intactas. |
| `fn_sumar_cantidad(...)` (0021) | Sin `p_modulo`; `p_cantidad NUMERIC(12,3)`; regla `cantidad > 0` en SQL. |
| `fn_mover_material(...)` (0021) | Sin `p_origen_modulo`/`p_destino_modulo`; `p_cantidad NUMERIC(12,3)`; origen ≠ destino por tipo (`GENERAL`↔`FO`). |
| `fn_crear_seguimiento`, `fn_cerrar_seguimiento` (0025), `fn_agregar_todo_seguimiento` (0021) | Variables y casts JSON: `(elem->>'cantidad_...')::INT` → `::NUMERIC(12,3)`. |
| `fn_generar_acta_entrega()` (0026, trigger) | Casts/serialización de cantidades en el snapshot JSONB sin truncar a entero. |

Reglas transversales: toda función conserva el `FOR UPDATE`, los mensajes de error canónicos y la delegación de auditoría; se añade validación de escala (`p_cantidad <> ROUND(p_cantidad, 3)` → `RAISE EXCEPTION 'La cantidad admite máximo 3 decimales'`) como defensa en profundidad (RF-6).

### 1.5 Auditoría de `valor_unitario` (RF-7)

`fn_auditar_modificacion_material()` añade `OR OLD.valor_unitario IS DISTINCT FROM NEW.valor_unitario` a la condición y `valor_unitario` a los objetos `valores_anteriores`/`valores_nuevos` del evento `MATERIAL_MODIFICADO` (misma estructura `modulo`, `accion`, `valores_anteriores`, `valores_nuevos`). `IS DISTINCT FROM` compara por valor numérico: `1.0` → `1.000` no genera evento.

**Decisión arquitectónica (para `@arq-reviewer`):** `valor_unitario` es un atributo de catálogo, **no un saldo de inventario**; por tanto su edición sigue el patrón vigente de campos de catálogo (`UPDATE` + trigger de auditoría, igual que `stock_minimo`), y no requiere stored function de ajuste/contra-movimiento. La regla §2.4 (contra-ajustes) aplica a saldos y movimientos, que sí se mantienen exclusivamente vía `fn_*`. **RATIFICADA por `@arq-reviewer` (T1).**

**Granularidad del evento (L4):** un `MATERIAL_MODIFICADO` emitido por el cambio de cualquier otro campo incluirá `valor_unitario` en `valores_anteriores`/`valores_nuevos` aunque no haya cambiado (misma granularidad evento-por-edición que el resto de campos de catálogo); no es una violación de RF-7, que solo exige evento cuando el valor **cambia** (comparación `IS DISTINCT FROM`).

### 1.6 `fn_valor_total_inventario()` (RF-4)

```sql
CREATE OR REPLACE FUNCTION fn_valor_total_inventario()
RETURNS NUMERIC AS $$
    SELECT ROUND(
        COALESCE((SELECT SUM(ia.stock_actual * cm.valor_unitario)
                  FROM inventario_almacen ia
                  JOIN secciones s ON s.almacen_id = ia.almacen_id
                                  AND s.tipo = 'GENERAL' AND s.is_active
                  JOIN catalogo_materiales cm ON cm.id_lista = ia.material_id AND cm.is_active), 0)
      + COALESCE((SELECT SUM(f.stock_actual * cm.valor_unitario)
                  FROM inventario_fibra f
                  JOIN catalogo_materiales cm ON cm.id_lista = f.material_id AND cm.is_active), 0)
    , 3);
$$ LANGUAGE sql STABLE;
```

- Aritmética `NUMERIC` exacta sin tope intermedio; redondeo (mitad alejada de cero) solo al final.
- Solo lectura: bloqueo `FOR UPDATE` no aplica; la consistencia es la del snapshot de la sentencia.
- Excluye Unidades y materiales inactivos (spec C-6, E-material inactivo).
- Se añadirá a `openspec.yaml › domain_rules.transaction_delegation.mandatory_functions` en la Fase 9.

### 1.7 `downgrade()` (reverso a `0026`)

**Secuencia (L5):** restaurar primero las columnas/PK de `inventario_fibra` (paso 3) y **después** las funciones verbatim de `0026` (paso 2 ejecutado al final), de modo que ninguna función re-publicada quede referenciando momentáneamente la columna `modulo` inexistente (plpgsql resuelve de forma diferida, pero la secuencia inversa es frágil).

1. **ABORTA** (`RAISE EXCEPTION`) si existe cualquier `stock_actual`/`cantidad`/`cantidad_tomada`/`cantidad_consumida`/`auditoria_eventos.cantidad` con fracción (`<> TRUNC(...)`) — evita pérdida silenciosa (E14).
2. Restaura funciones **verbatim de 0026/0025/0023/0021/0015** (copias literales en constantes `FN_*_ANTERIOR`).
3. Devuelve columnas a `INTEGER`, restaura `modulo` y la PK `(modulo, material_id)`; coloca la existencia total en `modulo='PAQUETE'` (la partición original **no** se reconstruye: reversión con pérdida de la partición, no de cantidad; se declara en el docstring de la migración).
4. Restaura `ck_secciones_tipo` sin `'FO'` (aborta si hay referencias a la sección `FO` en movimientos) y elimina `valor_unitario`, su `CHECK` y `fn_valor_total_inventario`.
5. Restaura trigger y función de auditoría anteriores. Los eventos `FO_UNIFICADO` ya emitidos permanecen (ledger inmutable).

### 1.8 Modelos SQLAlchemy (`@coder`, alineados al esquema aprobado)

- `CatalogoMaterial.valor_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default=text("1.000"))` + `CheckConstraint`.
- `InventarioFibra`: PK `material_id`; se elimina `modulo` y el `CheckConstraint` correspondiente.
- `stock_actual`/`cantidad*`: `Mapped[Decimal] = mapped_column(Numeric(12, 3), ...)`.
- `Seccion.tipo` `CheckConstraint` ampliado (`'FO'`).
- `AuditoriaEvento.cantidad`: `Numeric(12, 3)`.
- Los modelos de saldo siguen siendo de **lectura estricta** (prohibido `session.add/delete` o `UPDATE` directo).

---

## 2. Capa de Contrato API (FastAPI + Pydantic v2)

### 2.1 Tipos Decimal comunes (`app/schemas/_tipos.py`)

```python
from decimal import Decimal
from typing import Annotated
from pydantic import Field, PlainSerializer

CantidadDecimal = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=3, allow_inf_nan=False),
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
CantidadMovimiento = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False),
                               PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
```

- **Entrada:** `Field(max_digits=12, decimal_places=3)` rechaza sobre-precisión y desbordamiento con 422 (nunca redondea).
- **Salida:** número JSON (TypeScript `number`). `float()` es exacto para ≤15 dígitos significativos, suficiente para valores de columna (12 dígitos). `valor_total` puede superar ese rango solo por encima de ≈9×10¹² MXN: pérdida de precisión de sub-unidad inherente a `number` de TypeScript (mandato del solicitante), aceptada y documentada (R6).
- `@tester` prueba entradas JSON con binarios problemáticos (`0.1`, `2.675`, `1e-4`) para confirmar que Pydantic parsea el literal JSON sin artefactos de coma flotante.
- Los DTOs de movimiento que hoy usan `Field(le=2_147_483_647)` (`operadores.py`) sustituyen la cota INT4 por los límites decimales.

### 2.2 DTOs (todos `model_config = ConfigDict(extra="forbid")` en entradas)

| DTO | Cambio |
| :-- | :-- |
| `MaterialUpdate` | `+ valor_unitario: CantidadDecimal \| None = None`; `stock_actual: CantidadDecimal \| None`. |
| `MaterialCreate` | `stock_inicial: CantidadDecimal \| None`. **Sin** `valor_unitario` (spec C-3). |
| `MaterialOut` | `+ valor_unitario: CantidadDecimal`. |
| `FibraMaterialUpdateRequest` | `+ valor_unitario`, `stock_actual: CantidadDecimal \| None`; sin `modulo`. |
| `FibraCargaInicialRequest`, `FibraAjusteRequest` | Sin `modulo`; `cantidad`/`nuevo_stock` decimales. |
| `FibraStockOut`, `FibraMaterialOut`, `FibraOperacionOut` | Sin `modulo` (incluido `FibraOperacionOut`, que hoy lo expone); `stock_*` decimal; `+ valor_unitario`. |
| `FibraModulo`, `ModuloFo`, `ModuloFoOut` | **Eliminados**. |
| `SeccionStockOut`, `InventarioEquipoOut` | `stock_actual` decimal; `+ valor_unitario`. |
| `SeccionTransferibleOut.tipo` | `Literal["GENERAL","FO"]` (los legacy no se emiten). |
| `SumarCantidadRequest/Out` | Sin `modulo`; `cantidad`, `stock_nuevo` decimales. |
| `MoverMaterialRequest/Out` | Sin `origen_modulo`/`destino_modulo`; `cantidad`, `stock_origen`, `stock_destino` decimales. |
| `CargaInicialRequest`, `AjusteStockAlmacenRequest`, `AjusteOut` (`ajuste.py`) | `cantidad`, `nuevo_stock` y resultados decimales. |
| `DetalleLine`, `DetalleOut` (`movimiento.py`) | `cantidad: CantidadMovimiento`. |
| `SeguimientoItemIn/Out`, `ConsumoLine` (`seguimiento.py`) | `cantidad_tomada: CantidadMovimiento`, `cantidad_consumida: CantidadDecimal`. |
| `AuditoriaOut`, `Reporte*` | `cantidad`, `cantidad_tomada`, `cantidad_consumida` decimales (sólo lectura). |
| **Nuevo** `ResumenGeneralOut` | `valor_total: Decimal` (serializado como número), `moneda: Literal["MXN"]`. |

### 2.3 Endpoints (prefijo `/api/v1`)

| Método y ruta | Cambio | RF |
| :-- | :-- | :-- |
| `GET /fibra` | Reemplaza `GET /fibra/{modulo}`; lista el Inventario FO con `valor_unitario`. | RF-1 |
| `POST /fibra/carga-inicial` · `POST /fibra/ajuste` | Sin `modulo`; delegan a `fn_cargar_stock_inicial_fibra`/`fn_ajustar_stock_fibra`. | RF-1, RF-6 |
| `PATCH /fibra/materiales/{material_id}` · `DELETE /fibra/materiales/{material_id}` | Reemplazan las rutas con `{modulo}`. `valor_unitario` solo admin. | RF-1, RF-3, RF-8 |
| `PATCH /catalogo/{id_lista}` | Acepta `valor_unitario` (admin). Persistencia vía `catalogo_svc.actualizar`; la auditoría la emite el trigger. | RF-3, RF-7, RF-8 |
| `GET /inventario/secciones/transferibles` | Incluye la sección `FO`; excluye `FO_PAQUETE`/`FO_EN_USO`. | RF-9 |
| `POST /inventario/sumar-cantidad` · `POST /inventario/mover` | Sin campos de módulo. | RF-1 |
| **`GET /inventario/resumen-general`** | **Nuevo.** `SELECT fn_valor_total_inventario()` → `ResumenGeneralOut`. `assert_authenticated`. Sin escritura. | RF-4, RF-8 |
| Resto de rutas con cantidades (`/movimientos`, `/ajustes/*`, `/equipos/*`, `/seguimientos/*`) | Solo cambio de tipo en DTO. | RF-6 |

Prefijo del catálogo y rutas existentes se respetan tal como están registradas en `app/main.py`.

### 2.4 Seguridad (`@sec-ops`)

- **RBAC (RF-8):** en `actualizar_material` (catálogo) y en `PATCH /fibra/materiales/{id}`, la condición es **por presencia del campo** (dictamen `@sec-ops`, hallazgo 1): `if "valor_unitario" in payload.model_fields_set: require_admin(actor_ctx)` → 403 `AUTHORIZATION_FAILED` con mensaje canónico. En la ruta de fibra el gate se evalúa **antes** de construir el `payload_catalogo` passthrough. Los demás campos conservan `assert_authenticated`.
- **`valor_unitario: null` explícito = no-op:** la capa de servicio excluye `valor_unitario` del `setattr` cuando es `None` (no-op explícito en `catalogo_svc.actualizar`), de modo que `{"valor_unitario": null}` con actor autorizado responda sin escribir, sin evento de auditoría y **nunca** con 500 (columna `NOT NULL`).
- **Default-deny:** `GET /inventario/resumen-general` con `assert_authenticated`.
- **Mass-assignment:** `extra="forbid"` en todo DTO de entrada; `modulo` enviado → 422 (RF-1).
- **Sin secretos** nuevos; sin dependencias nuevas.

### 2.5 Errores

`transaccional.py` mapea los `RAISE EXCEPTION` de las funciones a `BusinessRuleError` 400/422 (incluidos los nuevos de escala, que caen en el fallback P0001 → **422**). **`numeric field overflow` (SQLSTATE 22003) → 400 con mensaje canónico** (precedente vigente de `_ejecutar`/`_mapear_raise_exception`; RF-8 admite 400/422 y plan/código/tests deben coincidir — Zero-Drift; dictamen `@sec-ops`, hallazgo 2). Ninguna `DBAPIError` escapa como 500 (precedente `FO_DELETE_*`). El Valor Total nunca devuelve 500 por inventario vacío (`COALESCE`).

### 2.6 Servicios

`services/transaccional.py` (`SQL` constantes de llamadas a `fn_*`), `services/inventario.py` (secciones transferibles) y `services/catalogo.py` se ajustan a las nuevas firmas; **cero aritmética** de stock o de valor en Python. `alerta_stock` conserva su comparación existente (presentacional, `Decimal` vs `int`).

---

## 3. Punto de Control de Congelación Contractual (Backend-First)

El frontend (React/TypeScript) **no se modifica** hasta que se cumplan todas:

1. **Documentado:** contratos de §2 reflejados en el OpenAPI generado (`/openapi.json`) y registrados por `@qa-agent` (evidencia: diff de OpenAPI contra el contrato de este plan).
2. **Pruebas obligatorias del backend en verde al 100 %:** `pytest` completo (incluye migración, decimales, RBAC, concurrencia y cancelación legacy), `mypy app/ tests/` sin errores.
3. **Sin desviaciones contractuales bloqueantes:** campos faltantes, inventados, tipos incompatibles o rutas/métodos incorrectos (informe `@qa-agent`).
4. **Aprobaciones:** `@qa-agent` registra la congelación; `@arq-reviewer` (arquitectura) y `@sec-ops` (RBAC, `extra="forbid"`) dan visto bueno por ser aplicables al alcance.

Cualquier cambio posterior de contrato invalida la congelación y exige nueva verificación (RFC OpenSpec; nunca parches silenciosos).

---

## 4. Capa Frontend (React 19 / TypeScript / TanStack Query) — bloqueada hasta §3

Agentes: `@state-agent` (contratos/queries), `@form-agent` (formularios), `@ui-agent` (componentes), `@ux-agent` (estados y confirmaciones).

### 4.1 Tipos y servicios (`@state-agent`)

- `types.ts`: se eliminan `FibraModulo`, `ModuloFoOut` y los campos `modulo`/`origen_modulo`/`destino_modulo`; `valor_unitario: number` en las filas de material/stock; `stock_actual`/`cantidad*: number`; `SeccionTransferibleOut.tipo: 'GENERAL' | 'FO'` (el tipo `Seccion` conserva `'FO_PAQUETE' | 'FO_EN_USO'` solo para datos históricos); `interface ResumenGeneral { valor_total: number; moneda: 'MXN' }`.
- `services/fibra.ts`: rutas `/fibra` y `/fibra/materiales/{id}`; `services/inventory.ts`: `getResumenGeneral()`.
- Hook `useResumenGeneral` (`hooks/`, clave `['inventario','resumen-general']` en `hooks/queryKeys.ts`).
- **Invalidación:** toda mutación que cambie existencias o valor (ajustes, +Cantidad, Mover, TRANSF/Devolución/cancelación, carga inicial, FO PATCH/DELETE, catálogo PATCH, seguimientos) invalida además `resumen-general`. React nunca calcula el total.

### 4.2 Componentes

| Componente | Cambio | RF |
| :-- | :-- | :-- |
| `KpiCards.tsx` | Nueva tarjeta `Valor Total` (icono `Coins`, color teal) como **segunda**: `Total Materiales`, `Valor Total`, `Stock Total`, `Alertas Stock`, `Transferencias Hoy`; rejilla `lg:grid-cols-5`; valor desde `useResumenGeneral` con estados de carga/error; formato `utils/formatMxn.ts` (`es-MX`, 2–3 decimales) + etiqueta `MXN` a la derecha. Las otras 4 tarjetas no cambian. | RF-5 |
| `InventoryTable.tsx`, `EquipoInventoryTable.tsx`, tabla de `FibraOptica.tsx` | Columna **VALOR UNITARIO** (`1.00 MXN`); solo lectura en Unidades. | RF-3 |
| `MaterialForm.tsx`, `FibraMaterialForm.tsx` | Campo `Valor Unitario` (admin), validación Zod preliminar (`^\d{1,9}(\.\d{1,3})?$`), envía `number`; oculto/deshabilitado para no administradores (RBAC visual, no seguridad). | RF-3, RF-8 |
| `CampoCantidad.tsx` y formularios de cantidades (+Cantidad, Mover, carrito TRANSF/Devolución, ajuste, seguimiento) | Aceptan hasta 3 decimales (`inputMode="decimal"`, `step=0.001`); validación preliminar; el backend decide. | RF-6 |
| `pages/FibraOptica.tsx` | Elimina `MODULO_POR_SUB`, sub-rutas y sub-pestañas; una sola tabla **Inventario FO** con `useQuery(['fibra'])`. | RF-1, RF-10 |
| `Sidebar.tsx` | Una entrada "Inventario FO" sin hijos (la ruta interna `fibra-optica` se conserva). | RF-1, RF-10 |
| `Transferencias.tsx`, `MoverMaterialDialog.tsx`, `SumarCantidadDialog.tsx`, `utils/seccionLabel.ts`, `utils/operadorPayload.ts` | Una sola opción "Inventario FO"; sin selección de módulo; secciones legacy se etiquetan "Inventario FO" al mostrar historial. | RF-9, RF-10 |
| `Auditoria.tsx` / etiquetas de acción | Etiqueta para `FO_UNIFICADO`; textos de eventos históricos con `modulo` se presentan como "Inventario FO" sin mutar el dato. | RF-7, RF-10 |

`@ux-agent`: confirmaciones con contexto (material, cantidad decimal, origen/destino "Inventario FO"), mensajes de error operativos para 400/422 de escala y desbordamiento. Sin `fetch`/`axios`/`invalidateQueries` en componentes presentacionales.

---

## 5. Estrategia de Pruebas y Matriz RF → Prueba

Backend en `backend/tests/` (estructura real del repositorio; PostgreSQL real, fixtures asíncronos, aislamiento por limpieza de `TABLAS_DOMINIO`). Nomenclatura `test_RF_<n>_<escenario>`; cada test asevera **HTTP y estado de BD**.

| RF | Archivo | Pruebas clave |
| :-- | :-- | :-- |
| RF-1 | `test_fo_unificado.py`, `test_migracion_0027.py` | Fusión PAQUETE+EN_USO = suma; evento `FO_UNIFICADO`; `modulo` → 422; una fila por material. La migración se prueba sobre una BD temporal llevada a `0026`, sembrada y subida a `0027`. |
| RF-2 | `test_valor_unitario.py` | Persistencia `12.345`; rechazo `-1`, `1.2345`, `1e9`; CHECK en BD. |
| RF-3 | `test_valor_unitario.py` (API) + vitest | Default `1.000` en todo el catálogo; PATCH con decimales; columnas y formulario (frontend). |
| RF-4 | `test_valor_unitario.py` | General+FO = 22.500 (caso de spec); vacío = 0; inactivo excluido; refleja cambios de stock y valor; 3 dp; sin 500; **E9**: suma de productos que excede 12 dígitos no se trunca ni falla (columna grande × valor grande). |
| RF-5 | vitest `KpiCards.test.tsx` | Orden de tarjetas; sufijo `MXN`; carga/error; refresco tras mutación. |
| RF-6 | `test_stock_decimal.py` + actualización de suites existentes | Ajuste `7.250`; TRANSF 2.5 + cancelación exacta; `1.0005` → 422; saldo no negativo; concurrencia `asyncio.gather` (8 vs 7 sobre 10). |
| RF-7 | `test_valor_unitario.py`, `test_migracion_0027.py` | Evento `MATERIAL_MODIFICADO` con anterior/nuevo; sin evento si no cambia; ledger previo intacto (conteo y contenido). |
| RF-8 | `test_valor_unitario.py`, `test_seguridad.py` | `extra` → 422 (incl. `{"modulo": "PAQUETE"}` en cualquier operación FO); no admin → 403 y valor sin cambios (con `2.5` **y** con `null` explícito); `valor_unitario: null` admin → no-op sin evento ni 500; `resumen-general` sin header actor → 422 y actor sin scope → 403; número JSON (no string); `NaN`/`Infinity`/`1e-4`/`1.0005` → 422; desbordamiento API → 422 y SQLSTATE 22003 → 400; nunca 500. |
| RF-9 | `test_fo_unificado.py` | Cancelar un TRANSF confirmado con origen legacy `FO_EN_USO` restaura exactamente; BORRADOR legacy confirmable; transferibles excluye legacy. |
| RF-10 | vitest `NomenclaturaFo.test.tsx` | Barrido de textos visibles ("Paquete"/"En Uso"/"FO Paquete"/"FO En Uso") con caso positivo del detector; Sidebar sin subentradas. |

Suites existentes que **deben actualizarse** (retirar `modulo`, tipos decimales): `test_fibra.py`, `test_fo_transferencias.py`, `test_operadores_rapidos.py`, `test_catalogo_admin.py`, `test_ajuste_desde_material.py`, `test_transferencias_multi_origen.py`, `test_e2e_flujo.py` y los vitest de `FibraOptica`, `MaterialForm`, `Transferencias*`, `Operadores*`. Se actualizan **junto con** el código que cubren en la fase correspondiente (backend en T4/T5, frontend en T6), no antes.

Compuertas finales (Constitución §7.2): `pytest` 100 %; `mypy`; `tsc -b`, eslint y `vite build` sin errores ni advertencias; `openspec validate --specs --strict` con 0 violaciones.

---

## 6. Orden de ejecución y dependencias

```text
P0 archivar paquete previo
   ↓
T1 spec aprobada (@arq-reviewer)
   ↓
T2 migración 0027 + funciones (@dba-guard)  ──┐
T3 revisión seguridad plan/DTO (@sec-ops)  ───┤  (T3 puede solaparse con T2)
   ↓                                          │
T4 modelos/DTOs/endpoints (@coder)  ←─────────┘
   ↓
T5 pruebas backend + CONGELACIÓN CONTRACTUAL (@tester / @qa-agent)
   ↓
T6 frontend (@state-agent → @form-agent → @ui-agent → @ux-agent)
   ↓
T7 trazabilidad, Drift Report, archivado (@auditor / @qa-agent)
```

## 7. Impacto en gobernanza (Fase 9, no ahora)

- `openspec/openspec.yaml › domain_rules`: añadir `fn_valor_total_inventario` a `mandatory_functions`; declarar que `FO_PAQUETE`/`FO_EN_USO` son valores **históricos** del ledger (precedente `DESPLIEGUE_*`) y que `valor_unitario` es atributo auditado de catálogo. Además, `openspec.yaml › paths` queda obsoleto en T5 (rutas con `{modulo}` y tipos `integer`): la Congelación Contractual valida contra `plan.md` §2 y el OpenAPI generado; **actualizar `paths` es condición de cierre de T7/antes del archivado** (L7).
- Promover `RF-1`..`RF-10` a las specs maestras `001_core_logistics` / `003_inventory_dashboard`, actualizando `REQ-DASH-003/004` (navegación y tarjetas KPI) y **retirando o reescribiendo explícitamente `REQ-FIBER-001`, `REQ-FIBER-002` y `REQ-FIBER-003`** de `003_inventory_dashboard` (describen vistas "Paquete"/"En Uso", en contradicción directa con RF-1/RF-10; si no se enmiendan al promover queda un conflicto L3 permanente) (M2). Los encabezados `### Requirement:` de `spec.md` ya tienen el formato de promoción (requiere traducir el verbo EARS "deberá" a "SHALL" al promover; al hacerlo, retirar el prefijo `RF-n` del encabezado o mantener el formato dual de forma consistente en toda la spec maestra, sin mezclar estilos — L6).
- `.agents.md` no registra enlaces a este paquete ni a `docs/1 Changes.docx` tras el archivado.
