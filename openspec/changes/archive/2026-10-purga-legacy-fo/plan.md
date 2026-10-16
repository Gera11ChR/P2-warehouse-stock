# Plan Técnico: Purga radical del legado Paquete / En Uso de Fibra Óptica (Backend-First)

**Change ID:** `2026-10-purga-legacy-fo` · **Fase 5 (Planificación)**
**Cubre:** `RF-1`..`RF-8` de `spec.md`. Todo término de este documento es normativo para `tasks.md`.
**Revisores de la fase:** `@arq-reviewer` (coherencia y enmienda E-1), `@dba-guard` (persistencia), `@sec-ops` (seguridad).
**Base:** cabeza Alembic `0027`; este paquete añade **solo `0028`**. `0027` **no se edita** (ya está en commits publicados; regla vigente: todo cambio de esquema va en una revisión nueva).

## 0. Principios de diseño

1. **PostgreSQL decide y ejecuta:** la purga y la verificación viven en la migración; FastAPI/React solo pierden código, no ganan ninguno.
2. **Excepción mínima:** la inmutabilidad del ledger se suspende **únicamente** dentro de la transacción de `0028` y se verifica reactivada (`spec.md` §3.1, E-1).
3. **Criterio por clave, no por texto:** nada de `LIKE '%PAQUETE%'`; la unidad `PAQUETE (100 PZ)` es dominio vivo.
4. **Cero saldo tocado:** los saldos no se derivan de movimientos; la migración verifica `SUM` por material antes = después y aborta si difiere.
5. **Cadena Alembic recorrible en bases sin referencias a `FO`:** las pruebas de migración degradan desde la cabeza (`esquema_en("0024"|"0025"|"0026")`); por eso `downgrade()` revierte el esquema sin abortar y sin restaurar datos. En bases con referencias a `FO`, el `downgrade` de 0027 aborta (paso 1b); aceptado.
6. **Sin deriva de contrato:** OpenAPI idéntico salvo `description`.

---

## 1. Capa de Persistencia (PostgreSQL 18 / PL/pgSQL / Alembic)

### 1.1 Migración `0028_purga_legacy_fo.py` (`down_revision = "0027"`)

Una sola revisión, transaccional (Alembic en PG envuelve en transacción). Pasos en orden:

| Paso | Operación | RF |
| :-- | :-- | :-- |
| 0a | **Guardia E-1:** si `n_dependientes > 0` (movimientos, líneas, scopes, saldos de sección y eventos que cumplan RF-1) y `current_database() NOT IN ('p2','p2_test')` → `RAISE EXCEPTION` (sin efectos). Una base nueva (0010 siembra las secciones legacy) pasa. | RF-6 |
| 0 | **Instantánea previa:** `stock_total_antes` = `SUM(stock_actual)` por `material_id` de `inventario_almacen ∪ inventario_fibra`; `n_secciones_legacy`; `n_eventos_total`. Si no hay secciones legacy, los pasos 3-8 son no-ops (E7). | RF-3 |
| 1 | `ALTER TABLE auditoria_eventos DISABLE TRIGGER tg_ledger_auditoria_inmutable;` y `ALTER TABLE actas_reportes DISABLE TRIGGER tg_ledger_actas_inmutable;` (transaccional: un rollback los restaura). | RF-6 |
| 2 | Tablas temporales `ON COMMIT DROP`: `_purga_secc` (`almacen_id` de `secciones` con `tipo IN ('FO_PAQUETE','FO_EN_USO')`), `_purga_mov` (ver §1.2), `_purga_acta` (`actas_reportes.movimiento_id IN _purga_mov`). | RF-1 |
| 3 | `DELETE FROM auditoria_eventos` con el predicado de §1.3 (usa `_purga_mov` y `_purga_acta`). **Antes** de borrar actas/movimientos para poder resolver `detalles.movimiento_id`/`acta_id`. | RF-1 |
| 4 | `DELETE FROM operaciones_idempotencia WHERE resultado @? '$.modulo ? (@ == "PAQUETE" \|\| @ == "EN_USO")' OR resultado->>'movimiento_id' IN (SELECT id::text FROM _purga_mov)` (columna `jsonb`). Además `UPDATE inventario_equipos SET ultimo_movimiento_id = NULL WHERE ultimo_movimiento_id IN _purga_mov` (puntero sin FK; no es saldo). | RF-1, RF-3 |
| 5 | `DELETE FROM actas_reportes WHERE id IN _purga_acta`. | RF-1 |
| 6 | `DELETE FROM movimientos_detalle WHERE movimiento_id IN _purga_mov`; `DELETE FROM movimientos_cabecera WHERE id IN _purga_mov`. | RF-1 |
| 7 | `DELETE FROM actor_almacen_scopes WHERE almacen_id IN _purga_secc`. | RF-1 |
| 8 | **Guardia de saldos:** si `inventario_almacen` tiene filas con `almacen_id IN _purga_secc` (o quedan referencias en `movimientos_*`, `actor_almacen_scopes`, `inventario_almacen`), `RAISE EXCEPTION` (no se borran saldos; p2 tiene 0). Luego `DELETE FROM secciones WHERE almacen_id IN _purga_secc`. | RF-1, RF-3 |
| 9 | `ALTER TABLE secciones DROP CONSTRAINT ck_secciones_tipo; ADD CONSTRAINT ck_secciones_tipo CHECK (tipo IN ('GENERAL','FO'));`. | RF-2 |
| 10 | `CREATE OR REPLACE FUNCTION fn_procesar_movimiento` y `fn_cancelar_movimiento`: copia **verbatim** de `FN_PROCESAR_NUEVA`/`FN_CANCELAR_NUEVA` de 0027 con `IN ('FO','FO_PAQUETE','FO_EN_USO')` → `= 'FO'` y comentarios legacy retirados. Firmas sin cambio (sin `DROP`). | RF-2 |
| 11 | `ALTER TABLE ... ENABLE TRIGGER` de ambos triggers. Después, `INSERT INTO auditoria_eventos (usuario, tipo_accion, resultado, detalles)` = **un** evento `PURGA_LEGACY_FO` (`usuario='migracion-0028'`) con conteos por tabla y por `tipo_accion`, `E-1`/`0028` y la ruta del dump (sin secretos); un INSERT no dispara los triggers de inmutabilidad. | RF-6 |
| 12 | **Verificaciones (abortan):** (a) 0 filas legacy en `secciones`, `movimientos_*`, `actor_almacen_scopes`, `inventario_almacen`; (b) 0 eventos que cumplan el predicado de §1.3; (c) `stock_total_antes` = después, por material; (d) `n_eventos_despues = n_eventos_total − eliminados + 1` y los eventos conservados conservan su `id` y contenido; (d2) **barrido diagnóstico no circular** de los literales `FO_PAQUETE`/`FO_EN_USO` en `detalles`, `actas_reportes.snapshot` y `operaciones_idempotencia.resultado`, y de claves `almacen_id`/`origen_almacen_id`/`destino_almacen_id` de `detalles` que apunten a ids de secciones purgadas (aborta si hay residuos); (e) `pg_trigger.tgenabled = 'O'` para ambos triggers; (f) ninguna función de `pg_proc` (esquema `public`) contiene `FO_PAQUETE`/`FO_EN_USO`; (g) `ck_secciones_tipo` solo enumera `GENERAL`/`FO`. | RF-2, RF-3, RF-6 |

Sin `DROP`/`TRUNCATE` de tablas, sin tocar permisos ni secuencias.

### 1.2 Definición de «movimiento legacy» (`_purga_mov`)

```sql
SELECT id FROM movimientos_cabecera
 WHERE origen_almacen_id  IN (SELECT almacen_id FROM _purga_secc)
    OR destino_almacen_id IN (SELECT almacen_id FROM _purga_secc)
UNION
SELECT movimiento_id FROM movimientos_detalle
 WHERE origen_almacen_id IN (SELECT almacen_id FROM _purga_secc)
```
Cualquier estado (BORRADOR, CONFIRMADO, CANCELADO). Medido en `p2`: 31 (29 por cabecera + 2 por línea; 10 mixtos).

### 1.3 Predicado de eventos de auditoría a eliminar

```sql
DELETE FROM auditoria_eventos e
WHERE e.almacen_origen_id  IN (SELECT almacen_id FROM _purga_secc)                 -- (a)
   OR e.almacen_destino_id IN (SELECT almacen_id FROM _purga_secc)
   OR e.detalles::jsonb @? '$.**.modulo        ? (@ == "PAQUETE" || @ == "EN_USO")' -- (b)
   OR e.detalles::jsonb @? '$.**.origen_modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
   OR e.detalles::jsonb @? '$.**.destino_modulo? (@ == "PAQUETE" || @ == "EN_USO")'
   OR e.tipo_accion = 'FO_UNIFICADO'                                                -- (c)
   OR (e.detalles::jsonb ->> 'movimiento_id') IN (SELECT id::text FROM _purga_mov)  -- (d)
   OR (e.detalles::jsonb ->> 'acta_id')       IN (SELECT id::text FROM _purga_acta);
```
- `auditoria_eventos.detalles` es de tipo `json` → cast a `jsonb`; `operaciones_idempotencia.resultado` ya es `jsonb`.
- Quedan fuera por diseño: `MATERIAL_MODIFICADO` (`modulo:"CATALOGO"`, `u_m:"PAQUETE (100 PZ)"`), `UM_*`, `DESPLIEGUE_*`.
- Medido en `p2` (recalcular en T2): 48 por columna + 53 por JSON (`STOCK_INICIAL_FO` 18, `ELIMINACION_FO` 12, `MOVIMIENTO_INVENTARIO` 9, `AJUSTE_INVENTARIO_FO` 7, `SUMA_CANTIDAD` 7) + 16 `FO_UNIFICADO` + 12 por `movimiento_id` (`TEAMS_TRANSFERENCIA` 10, `ACTA_ENTREGA_GENERADA` 2) ≈ 129 (con solapamientos).
- Casos de prueba adicionales (T5): clave `modulo` anidada, caso negativo con `modulo:"CATALOGO"` + `u_m:"PAQUETE (100 PZ)"` anidado y `detalles` NULL (excluido sin error).
- `T2` entrega además un script de **vista previa** de solo lectura (`SELECT` equivalente) para contrastar el conteo antes de aplicar.

### 1.4 `downgrade()` — solo esquema

1. Redefine `ck_secciones_tipo` a `('GENERAL','FO','FO_PAQUETE','FO_EN_USO')`.
2. Republica `fn_procesar_movimiento`/`fn_cancelar_movimiento` con el cuerpo **verbatim** de 0027 (constantes `*_0027` embebidas en `0028`).
3. No recrea secciones, movimientos, actas, scopes ni eventos; no aborta. Documentado en el docstring: «los datos purgados solo se recuperan desde el `pg_dump` previo».
4. No toca los triggers de inmutabilidad (permanecen activos).
5. Emite `RAISE NOTICE` «esquema restaurado; los datos purgados no se restauran (usar pg_dump)».
6. Limitación documentada: tras `0028` el `downgrade` de 0027 aborta si la sección `FO` tiene referencias (su paso 1b); en `p2_test` limpia la cadena es recorrible.

Criterio de prueba (T5): `upgrade 0028` → `downgrade 0027` deja `pg_get_functiondef` de ambas funciones idéntico al de una base recién migrada a 0027.

### 1.5 Procedimiento operativo en `p2`

1. `pg_dump` de `p2` a `/tmp/opencode/p2_pre_0028.dump` (formato custom) antes de aplicar.
2. Vista previa de conteos (script de solo lectura).
3. `alembic upgrade 0028` sobre `p2_test` (primero) y luego `p2`; comparar contra la vista previa.
4. Verificar de nuevo trigger activo y que `DELETE` sobre ambos ledgers falla.

---

## 2. Capa de Aplicación (FastAPI / SQLAlchemy)

> Alcance: **solo borrar** código/comentarios. Cero lógica nueva; el RBAC, `extra="forbid"`, mensajes y códigos HTTP vivos no cambian.

| Archivo | Cambio | RF |
| :-- | :-- | :-- |
| `backend/app/models/inventario.py` | `CheckConstraint("tipo IN ('GENERAL','FO')", name="ck_secciones_tipo")`; docstrings de `Seccion` e `InventarioFibra` sin «histórico/legacy». | RF-4 |
| `backend/app/services/movimientos.py` | Reescribir el comentario de enrutamiento (líneas ~57-64): las secciones válidas son `GENERAL` activas y `FO`; el bloque ya no habla de BORRADOR legacy/E8. Verificar que `_validar_origen` y la validación de destino DEVOL siguen devolviendo 422 «Sección … inexistente» ante un id purgado (la lógica existente ya lo hace: `session.get` → `None`). | RF-4 |
| `backend/app/services/inventario.py` | Docstring (~l. 40): quitar la mención a valores históricos del ledger. | RF-4 |
| `backend/app/services/transaccional.py` | Docstring (~l. 481) y comentarios de firmas 0027: quitar `FO_PAQUETE`/`FO_EN_USO`. | RF-4 |
| `backend/app/schemas/inventario.py` | Docstrings de `SeccionTransferibleOut`/enumeraciones y comentario `PAQUETE/EN_USO` (~l. 19, 33, 93): quitar lo legacy. Los `Literal` ya son `'GENERAL'`/`'FO'` (verificar). | RF-4 |
| `backend/app/api/v1/fibra.py` (l. 4-5), `backend/app/api/v1/inventario.py` (~l. 124) | Descripciones y docstrings sin la nota sobre tipos legacy. **Única posible variación de OpenAPI:** textos `description`. | RF-4 |
| `backend/app/schemas/operadores.py` (l. 4) | Comentario sobre «módulo»: conservar solo la regla viva (`extra="forbid"` rechaza `modulo`). | RF-4 |
| `backend/app/schemas/material.py` | **Sin cambio:** `PAQUETE (100 PZ)` es una unidad de medida viva. | — |

### 2.1 Congelación contractual (cierre de T5)
- Antes de tocar código: exportar `openapi.json` baseline (`/tmp/opencode/openapi_pre.json`).
- Después de T4/T5: exportar y comparar; el diff **solo** puede contener cambios en `description`/`summary`. Cualquier diferencia de ruta, campo, tipo, enum o código de estado invalida la congelación y detiene T6.
- Regenerar `openspec.yaml › paths` solo si cambian descripciones (ver T7).

---

## 3. Capa de Presentación (React / TypeScript)

> Alcance: **solo podar**. Sin componentes ni flujos nuevos. T6 solo inicia tras la Congelación Contractual de T5.

| Archivo | Cambio | RF |
| :-- | :-- | :-- |
| `frontend/src/types.ts` | `Seccion.tipo: 'GENERAL' \| 'FO'`; borrar comentarios «HISTÓRICOS» (l. 48, 64) y el de `modulo` (l. 328) que describe el rechazo del contrato heredado si ya no aporta. **No tocar** `DESPLIEGUE_*` ni `PAQUETE (100 PZ)`. | RF-5 |
| `frontend/src/utils/seccionLabel.ts` | `etiquetaSeccion`: `FO` → `ETIQUETA_INVENTARIO_FO`, otro → `nombre`. `etiquetaSeccionPorId`: búsqueda por id; id desconocido → `Sección #<id>` (nunca «Inventario FO»); sin comentarios legacy. | RF-5 |
| `frontend/src/utils/auditoriaPresentacion.ts` | **Eliminar** el archivo. | RF-5 |
| `frontend/src/pages/Auditoria.tsx` | Quitar `import presentarDetallesAuditoria` (l. 9) y usar `JSON.stringify(e.detalles, null, 2)` (l. ~249); reescribir el comentario de `nombreSeccion` (l. 53-54). | RF-5 |
| `frontend/src/pages/Transferencias.tsx` | Comentarios de l. ~185, ~453 y ~510: retirar «orígenes FO históricos». Sin cambio de lógica. | RF-5 |
| `frontend/src/utils/operadorPayload.ts` (l. 60-62) | Comentario de `resolverInventario` sin «orígenes FO históricos». Firma y lógica iguales. | RF-5 |
| `frontend/src/services/fibra.ts`, `frontend/src/components/*` | Revisar comentarios con `modulo` heredado; conservar la advertencia viva «enviar `modulo` es 422» solo si sigue siendo contrato. | RF-5 |

### 3.1 Tests de frontend
- `NomenclaturaFo.test.tsx`: retirar los casos de secciones legacy y de `etiquetaSeccionPorId` → «Inventario FO»; añadir el caso «id desconocido → `Sección #id`».
- `Transferencias.test.tsx`, `OperadoresRapidosDialogs.test.tsx`, `operadorPayload.test.ts`: quitar fixtures con `tipo: 'FO_PAQUETE'|'FO_EN_USO'` y las aserciones que dependían de ellos.
- Borrar el test de `auditoriaPresentacion` si existe.
- Puerta: `tsc -b`, `eslint`, `vitest run`, `vite build` en verde; `grep` de residuos vacío (salvo `PAQUETE (100 PZ)`).

---

## 4. Pruebas Backend

| Archivo | Cambio |
| :-- | :-- |
| `tests/test_migracion_0028.py` (**nuevo**, usa `esquema_en("0027")`) | `test_RF_001_purga_elimina_dependientes_legacy` (siembra en 0027: movimiento con líneas y acta, mixto, borrador, scopes, idempotencia, eventos por columna/JSON/`FO_UNIFICADO`/`movimiento_id`); `test_RF_001_conserva_unidad_paquete_y_material_modificado`; `test_RF_003_stock_intacto`; `test_RF_003_eventos_no_legacy_intactos` (conteo y contenido por `id`); `test_RF_002_check_y_funciones_sin_legacy`; `test_RF_006_triggers_activos_tras_purga` (DELETE en ambos ledgers falla); `test_RF_006_aborto_con_saldo_legacy` (siembra `inventario_almacen` legacy → rollback y trigger sigue activo); `test_RF_006_downgrade_solo_esquema` (idéntico `pg_get_functiondef` a 0027, sin filas); `test_E7_sin_datos_legacy_noop`. |
| `tests/test_migracion_0027.py` | Cambiar los `alembic("upgrade", "head")` (l. 254, 310) a `"0027"`, para que sigan verificando el comportamiento de 0027 sin ejecutar 0028; las pruebas RF-9/D-2 de 0027 se conservan (verifican la migración publicada). Ajustar la aserción de l. 140 si depende de la cabeza. |
| `tests/test_fo_unificado.py` | Eliminar `ALMACEN_PAQUETE/EN_USO` y los tests `test_RF_009_cancelar_transf_confirmado_origen_legacy_en_uso_restaura`, `test_RF_009_borrador_legacy_origen_paquete_procesable` y `test_RF_009_secciones_legacy_no_seleccionables`; añadir `test_RF_4_origen_id_purgado_responde_422` (ids 2 y 3 ya no existen). |
| `tests/test_fo_transferencias.py` | Eliminar `test_RF_9_teams_desde_origen_legacy_en_uso_enruta_fo_unificado`, `test_RF_9_cancelar_teams_legacy_restituye_fo_unificado` y el aserto de exclusión de legacy en `test_RF_9_secciones_transferibles_incluyen_fo_excluyen_legacy` (renombrar a `..._solo_general_y_fo`). |
| `tests/test_fo_valor_casos_limite.py`, `tests/test_catalogo_admin.py`, `tests/helpers/fabrica.py` | Quitar constantes y comentarios legacy; sustituir cualquier uso de `ALMACEN_EN_USO` por la sección `FO` (`seccion_fo`). |
| `sql_tests/conftest.py` y `sql_tests/*` | Quitar la siembra legacy (si existe); verificar que las pruebas SQL no usan ids 2/3. |

Reglas de ejecución: pytest y `sql_tests` **en serie** (comparten `p2_test`); credenciales desde `backend/.env` sin imprimirlas (`P2_ADMIN_DATABASE_URL`, `P2_TEST_DATABASE_URL`; `sql_tests` usa la URL sin `+psycopg`).

---

## 5. Gobernanza al archivar (T7)

- `openspec/specs/001_core_logistics/spec.md`: reescribir **REQ-FO-002** como «no existen secciones legacy (solo `GENERAL` y `FO`)»; retirar la cláusula de compatibilidad y el escenario «Legacy draft still processable». Añadir los requisitos `REQ-PURGA-*` aplicables (RF-1..RF-4) con identificadores `REQ-…`.
- `openspec/openspec.yaml › domain_rules`: retirar `FO_PAQUETE`/`FO_EN_USO` de los valores técnicos históricos (mantener `TEAMS`, `DEVOL`); actualizar `audit_ledger_immutability` con la nota «única excepción registrada: 0028, E-1»; regenerar `paths` si cambian descripciones.
- `tasks.md` final: registro de dictámenes y aprobación humana pendiente sobre `.agents.md` §3 (si procede) y `docs/1 Changes.docx`.
- `git mv` del paquete a `openspec/changes/archive/` y `openspec validate --specs --strict` 3/3.

---

## 6. Riesgos y mitigaciones

| # | Riesgo | Mitigación |
| :-- | :-- | :-- |
| R1 | Pérdida irreversible de datos | `pg_dump` previo (§1.5); vista previa de conteos; alcance limitado por E-1 a bases de prueba. |
| R2 | Borrar eventos que no son legacy | Criterio por clave JSON (no `LIKE`); prueba que fija `MATERIAL_MODIFICADO`/`UM_*` intactos; verificación 12(d). |
| R3 | Triggers de inmutabilidad quedan desactivados | `DISABLE`/`ENABLE` en la misma transacción + verificación 12(e); prueba de DELETE posterior. |
| R4 | Eventos o actas con referencias colgantes | Borrado por `movimiento_id`/`acta_id` (§1.3 d) ANTES de borrar los padres. |
| R5 | La cabeza 0028 rompe las pruebas que degradan desde head | `downgrade()` no aborta (§1.4); T5 verifica el ciclo completo `head → 0026 → head` en `p2_test` limpia y documenta el aborto de 0027 con scope FO sembrado. |
| R6 | Tests API que usaban ids 2/3 | Retirarlos/reemplazarlos (§4); `grep` de residuos como puerta. |
| R7 | Otra base ya en 0027 con datos | Guardia técnica de §1.1 paso 0a: aborta si `current_database()` no es `p2`/`p2_test` y hay dependientes legacy. |
| R8 | Función republicada difiere de 0027 más de lo previsto | T2 verifica por diff textual contra `FN_PROCESAR_NUEVA`/`FN_CANCELAR_NUEVA`: solo cambian `IN ('FO','FO_PAQUETE','FO_EN_USO')` → `= 'FO'` y comentarios. |
