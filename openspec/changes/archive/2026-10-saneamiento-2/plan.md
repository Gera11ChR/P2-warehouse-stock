# Plan Técnico: Saneamiento 2 (Backend-First)

**Change ID:** `2026-10-saneamiento-2` · **Fase 5 (Planificación)**
**Cubre:** `RF-1`..`RF-6` de `spec.md`. Todo término es normativo para `tasks.md`.
**Revisores de la fase:** `@arq-reviewer` (alcance y coherencia), `@sec-ops` (RF-2/RF-3).
**Base:** cabeza Alembic `0028`. **Este paquete no añade ni edita migraciones.**

## 0. Principios

1. Higiene sin cambio de dominio: ninguna stored function, invariante ni regla de negocio cambia.
2. Mínimo contrato: el OpenAPI solo puede variar en (a) los cuatro query params eliminados de `GET /api/v1/catalogo` y (b) las restricciones del header `X-Actor`.
3. Primero la evidencia: RF-2 y RF-3 empiezan con una prueba que **reproduce** el defecto (500 / actor largo) antes de corregirlo.
4. Destrucción irreversible al final, tras las compuertas.

---

## 1. Backend (T3)

### 1.1 RF-2 — Handler global `22003 → 400`
| Archivo | Cambio |
| :-- | :-- |
| `backend/app/main.py` | Registrar `@app.exception_handler(DBAPIError)` (y `DataError` de SQLAlchemy, subclase de `DBAPIError`). Predicado **exclusivo**: `getattr(getattr(exc, "orig", None), "sqlstate", None) == "22003"` (dictamen T2). Si se cumple responde `JSONResponse(status_code=400, content={"error": {"code": "NUMERIC_OUT_OF_RANGE", "message": <mensaje fijo>, "coordinates": []}})` (siempre con argumentos nombrados) con el mismo formato que `BusinessRuleError.to_http_detail()`. Cualquier otro SQLSTATE: **se relanza** el error (se conserva el 500 actual y el comportamiento de los handlers existentes). |
| `backend/app/services/transaccional.py` | **Sin cambio de comportamiento.** Su rama `22003` (mensaje «La cantidad o el stock resultante excede el rango soportado») prevalece porque `BusinessRuleError` se lanza antes; la prueba lo fija. Se reutiliza `_sqlstate` si es importable sin ciclos; si no, se duplica la función mínima en `errors.py`. |
| Desborde | Verificado en T2: PostgreSQL rechaza en el servidor (`22003`) incluso con `10**30`; **sin** fallback por mensaje ni por `psycopg.DataError`. Un entero de miles de dígitos da 422 de Pydantic. |
| Sesión | El handler no emite `commit`. La dependencia de sesión ya hace rollback al salir con excepción; la prueba E3 verifica que la siguiente solicitud funciona. |

Rutas de prueba (reproducir primero; todas dan 500 hoy): `GET /equipos/{id}/inventario`, `/equipos/{id}`, `/equipos/{id}/seguimientos`, `/equipos/{id}/seguimientos/{id}`, `/movimientos/{id}`, `/catalogo/{id}`, `/inventario/secciones/{id}`, `/auditoria?material_id=`; y además POST/PATCH (`POST /movimientos` con `origen_almacen_id=10**12`, `PATCH /fibra/materiales/{id}`), que dependen de `_ejecutar`/pre-chequeos. Verificar que `23505` conserva su 409 vía `_ejecutar`, y que el cuerpo del 400 no contiene «integer», «psycopg» ni SQL.

### 1.2 RF-3 — `X-Actor`
| Archivo | Cambio |
| :-- | :-- |
| `backend/app/security.py` | `ActorHeader = Annotated[str, Header(alias="X-Actor", min_length=1, max_length=100, pattern=…)]` con el patrón `^[^\x00-\x1f\x7f-\x9f]*[^\s\x00-\x1f\x7f-\x9f][^\x00-\x1f\x7f-\x9f]*$` y una `description` («no autenticado»). *Desviación de T3:* el patrón con `\S` prescrito dejaba pasar NUL/DEL/C1 como único carácter «visible»; se usa una clase negada `[^\s<controles>]`. Rechazo → 422 por el handler de validación existente (`RequestValidationError`), antes de abrir sesión. |
| Verificación previa (R2) | Consulta de solo lectura a `p2` y al seed de pruebas: todo `actor_id` de `actor_almacen_scopes`/`administradores` y `usuario` de `equipos_integrantes` cumple la regla; si no, `@sec-ops` decide. |
| `openspec/openspec.yaml › paths` | Reflejar `maxLength: 100`/`pattern` del header en los parámetros `X-Actor` y actualizar su `description` («identificador no autenticado; autenticación real fuera de alcance»). |

### 1.3 RF-4 backend — Filtros eliminados
| Archivo | Cambio |
| :-- | :-- |
| `backend/app/api/v1/catalog.py` (l. 74-77, 91-94) | Quitar `desde_id_lista`, `hasta_id_lista`, `desde_sku`, `hasta_sku` de la firma y de la llamada a `catalogo_svc.listar`. |
| `backend/app/services/catalogo.py` (l. 100-103, 132-137) | Quitar los parámetros y sus cuatro `where`; ajustar el docstring («rangos id_lista/SKU»). |
| `backend/tests/test_catalogo.py` (l. ~54) | Reemplazar la prueba de `desde_sku`/`hasta_sku` por una que verifique que son **ignorados** (E6). |
| Otros consumidores | `grep` de `desde_sku|hasta_sku|desde_id_lista|hasta_id_lista` en `backend/`, `frontend/`, `openspec/specs` = 0 (el grep previo no encontró usos en specs). |

### 1.4 RF-5 — Test guardián `EXITO`
Nuevo `backend/tests/test_convencion_resultado.py`:
1. Recorre `pg_get_functiondef` de las funciones de `public` y falla si hay literal de `resultado` ≠ `'EXITO'` (análisis del `INSERT INTO auditoria_eventos`); también comprueba que el `DEFAULT` de la columna sea `'EXITO'` o nulo según el esquema real.
2. Barre `backend/app/**/*.py` (comprobación defensiva; hoy sin literales) buscando `resultado=`/`resultado =` con valor ≠ `EXITO`.
3. Tras un flujo representativo vía API (carga, ajuste, TRANSF, DEVOL, seguimiento), verifica `SELECT DISTINCT resultado FROM auditoria_eventos` = `{'EXITO'}`.
`0027` queda excluido por diseño (histórico).

### 1.5 Congelación Contractual (T4)
- Baseline previa a T3: exportar `openapi.json` a `/tmp/opencode/openapi_s2_pre.json`.
- Tras T3: el diff **solo** puede contener los cuatro params de `/api/v1/catalogo` y las restricciones/`description` del header `X-Actor`. Cualquier otra diferencia detiene T5.
- Regenerar `openspec.yaml › paths` desde el OpenAPI (el repositorio ya lo hizo así en T7 del paquete `fo-unificado`).

---

## 2. Frontend (T5) — solo podar (Backend-First: tras la congelación)

| Archivo | Cambio |
| :-- | :-- |
| `frontend/src/components/Sidebar.tsx` | Quitar `children?: NavItem[]` (l. 17) y el bloque `item.children && (...)` (l. ~73-95) más los imports/variables que queden sin uso (`ChildIcon`, `isActive(child)` si solo lo usa esa rama). |
| `frontend/src/utils/formatMxn.ts` | Quitar `formatMxnConMoneda` (l. 21). |
| `frontend/src/utils/cantidad.ts` | Quitar `parseCantidadDecimal` (l. 148-155). |
| `frontend/src/utils/__tests__/valorUnitario.test.ts`, `cantidad.test.ts` | Quitar sus importaciones y los casos correspondientes (l. 7, 76-77; l. 7, 131-139). |
| `frontend/src/services/catalog.ts` | Quitar `desde_id_lista`, `hasta_id_lista`, `desde_sku`, `hasta_sku` de `CatalogFilters` y cualquier uso en la construcción de params. |
| `frontend/src/types.ts` (`ActaItem`, l. 260) | Añadir `origen_almacen_id?: number \| null` y `origen_nombre?: string \| null`. Sin cambios de UI. |

Verificaciones: `tsc -b`, `eslint`, `vitest run`, `vite build` sin advertencias y `grep` de las cadenas eliminadas = 0.

---

## 3. Gobernanza y documentación (T6)

| Elemento | Acción |
| :-- | :-- |
| `.agents.md` | Retirar `FO_PAQUETE`/`FO_EN_USO` de §3 (l. 33 → «tales como `Equipo`, `TEAMS`, `DEVOL`») y de la l. 670 («TEAMS/DEVOL or `id_lista`»); **conservar** la fila de la tabla de §3 «FO Paquete / FO En Uso → Inventario FO». El mensaje del commit cita la autorización. Nivel L2: la edición queda autorizada por la instrucción explícita del solicitante de este paquete (registrada en `tasks.md`). Verificar que el commit de §5 (`69bca35`) ya está en la rama. |
| `docs/1 Changes.docx` | `git rm`; `grep` de referencias en el repo = 0 (el paquete `fo-unificado` verificó que no hay en `.agents.md`). |
| `README.md` | Ver §3.1. |
| `backend/db/ddl.sql` | Ver §3.2. |
| `trazabilidad.md` | Ver §3.3. |

### 3.1 README (cifras medidas, no estimadas)
Se fijan tras la corrida final de compuertas (T7) y se verifican contra `ls backend/alembic/versions` y los resúmenes de pytest/vitest. Puntos a corregir: l. 101 (revisiones), l. 102 y 259 (pytest), l. 122, 260 y 446 (vitest), l. 108 y 310 (cabeza `0027` → `0028`), l. 302 (`23 migrations` → `28`), l. 312 (`tests/`), l. 398 y 438 (cadena `0001 → 0023`), l. 440; prosa de FO desfasada (l. 36, 82, 272-274); (la l. 242 describe el resultado del script de seed —8 U.M.— y es correcta; la «corrección a 10» del plan inicial era errónea); y una entrada en el historial de cambios por cada paquete cerrado de esta sesión.

### 3.2 `ddl.sql`
1. Crear una base vacía temporal (si el rol QA carece de `CREATEDB`, usar `p2_test` llevándola a `head` como hace `esquema_en`).
2. `pg_dump --schema-only --no-owner --no-privileges` de la base en `0028`.
3. Normalizar (quitar `SET`/`SELECT pg_catalog.set_config`, comentarios de versión) y anteponer la cabecera: fecha, comando, versión de `pg_dump`, «cabeza `0028`», «referencia no ejecutable sobre bases reales».
4. Script de verificación `backend/scripts/verificar_ddl.py` (o prueba): vuelve a volcar y compara el volcado normalizado con `ddl.sql`.
5. Si PostgreSQL no está disponible, aborta (E7).

### 3.3 `trazabilidad.md` (en el paquete, al archivar)
Matriz RF → implementación → prueba; sección **Dispensas formales**:
| Dispensa | Justificación | Evidencia alternativa |
| :-- | :-- | :-- |
| 12(c) stock | Aserción de defensa en profundidad; no se puede disparar desde fuera sin corromper el estado | `test_RF_001_003_purga_conserva_dominio_vivo…` compara stock fila a fila |
| 12(d) md5 de eventos | Ídem | La misma prueba compara `id` y md5 de los eventos conservados |
| E12 guardia en otra base | El rol QA no posee `CREATEDB` | `test_RF_006_guardia_e1_aborta_fuera_de_p2_y_p2_test` (unidad) |
| E9 reintento tras fallo | La infraestructura de pruebas restaura la cabeza con `upgrade head` tras cada aborto, lo que re-ejecuta `0028` con éxito | `test_RF_006_abortos_con_rollback_total` |

### 3.4 Destrucción segura (último paso de T7)
Tras la última compuerta verde: `find /tmp/opencode -type f -exec shred -u {} +` (cubre el `pg_dump`, scripts, volcados y los archivos dentro de `__pycache__/`, `dist/` y `probe/`) y luego `find /tmp/opencode -mindepth 1 -type d -empty -delete`. `shred` es de mejor esfuerzo en sistemas de archivos con journaling/CoW (se documenta). El directorio `/tmp/opencode` se conserva. Se deja constancia en `tasks.md` (qué se destruyó, no su contenido). Es irreversible: antes se pide confirmación al solicitante.

---

## 4. Estrategia de pruebas

| RF | Archivo | Pruebas |
| :-- | :-- | :-- |
| RF-2 | `backend/tests/test_robustez_ids.py` (nuevo) | 6 rutas con `10**12` → 400; `10**30` → 400 (E1); la siguiente solicitud funciona (E3); `23505` conserva 409 (R3) |
| RF-3 | `backend/tests/test_actor_header.py` (nuevo) | 101 chars → 422; vacío → 422; solo espacios → 422; `\t` por HTTP → 422; `\n`/NUL por ASGITransport o dependencia directa → 422; 100 chars válido (E4); `Juan Perez` válido (E5); sin consulta de scopes ante rechazo |
| RF-4 | `test_catalogo.py` (ajuste); vitest | Filtros eliminados ignorados (E6); Sidebar sin `children`; utilidades eliminadas |
| RF-5 | `test_convencion_resultado.py` (nuevo) | Guardián (3 comprobaciones) |
| RF-6 | todas | pytest (serie), `sql_tests`, `mypy`, `tsc -b`, `eslint`, `vitest`, `vite build` |

Reglas de ejecución: serializar (`p2_test` compartida); credenciales desde `backend/.env` sin imprimirlas.

## 5. Orden de ejecución

`T1 → T2 → T3 → T4 [Congelación] → T5 → T6 → T7`. T6 (documentación) puede preparar `.agents.md`, `docs/` y `ddl.sql` en paralelo a T5 al no tocar contrato, pero el README y `ddl.sql` se **cierran** con cifras finales después de T5.
