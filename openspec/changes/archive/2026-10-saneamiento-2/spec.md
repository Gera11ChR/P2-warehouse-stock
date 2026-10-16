# Spec: Saneamiento 2 — deuda técnica residual (gobernanza, robustez y código muerto)

**Change ID:** `2026-10-saneamiento-2`
**Naturaleza:** higiene técnica. **No introduce reglas de dominio nuevas** (`.openspec.yaml › skip_specs: true`): no se promueven requisitos a `openspec/specs/`; solo se ajustan descripciones de `openspec.yaml › paths` si cambia el OpenAPI.
**Identificadores:** `RF-1`..`RF-6` (usados en `tasks.md` y en `test_RF_<n>_...`). Son requisitos de higiene técnica: **no se promueven a `openspec/specs/`** (no hay reglas de dominio nuevas; RF-5 formaliza una convención ya vigente) y, por ello, no se les asigna alias `[REQ-…]` (Constitución §1.5 queda cubierta por la matriz RF → prueba de `trazabilidad.md`, §7.1).
**Antecedentes (nota histórica):** los dos paquetes previos (unificación FO y purga del legado FO) dejaron fuera de alcance, deliberadamente, la deuda aquí tratada.

---

## 1. Decisiones de diseño (aprobadas 2026-10-16)

| ID | Decisión |
| :-- | :-- |
| **D-1** | `'EXITO'` es la convención canónica de `auditoria_eventos.resultado`; se formaliza con un **test guardián**, **sin migración** ni CHECK. |
| **D-2** | IDs fuera de INT4: **handler global** de `DBAPIError`/`DataError` con SQLSTATE `22003` → HTTP 400 canónico. No añade cotas `le=` a los esquemas. |
| **D-3** | `X-Actor`: **validación mínima** (longitud 1..100, sin caracteres de control → 422). La autenticación real queda **fuera de alcance**, documentada. |
| **D-4** | Filtros `desde_id_lista`/`hasta_id_lista`/`desde_sku`/`hasta_sku`: se eliminan en **frontend y backend** (incluido `test_catalogo.py`). |
| **D-5** | `ActaItem` (TS): se **añaden** `origen_almacen_id` y `origen_nombre` como opcionales (alinear con el backend; no se quitan, no existen). |
| **D-6** | `backend/db/ddl.sql`: se **regenera** con `pg_dump --schema-only --no-owner --no-privileges` desde una base recién migrada a `0028`. |
| **D-7** | Dispensas de prueba (12(c), 12(d), E12, E9) consolidadas en `trazabilidad.md`; el `pg_dump` y los scripts de `/tmp/opencode` se **destruyen al final** (`shred`), conservando el directorio. |

### 1.1 Correcciones factuales al briefing (verificadas en el repositorio)

- El commit de `.agents.md` §5 **ya existe** (`69bca35`) y el árbol estaba limpio: el RF solo lo verifica.
- La «nota de §3 sobre valores históricos» **nunca se añadió**. Existen menciones deprecadas de `FO_PAQUETE`/`FO_EN_USO` en `.agents.md` línea 33 (§3) y línea 670 (ejemplo ilustrativo); se retiran de ambas.
- Hay **28** migraciones (`0001`..`0028`), no 29 (el 29 contaba `__pycache__`).
- `'OK'` vs `'EXITO'` **ya está unificado** en el código vivo y en `p2` (891/891 `EXITO`); el único `'OK'` es texto histórico de `0027` (`FO_UNIFICADO`, eventos ya purgados). `0027` no se edita.
- `ActaItem` (TS) no contiene `origen_almacen_id`/`origen_nombre`: faltan respecto a `schemas/reporte.py:33-34`.
- Los filtros `@deprecated` son **cuatro** (incluye `desde_sku`/`hasta_sku`).
- `docs/1 Changes.docx` está rastreado; los paquetes archivados lo citan con otra ruta histórica, por lo que «sin referencias» se limita a fuera de `openspec/changes/archive/`.
- El rechazo de IDs gigantes es del servidor PostgreSQL (SQLSTATE `22003`), no del cliente psycopg (dictamen T2).

---

## 2. Requisitos

### Requirement: RF-1 Gobernanza y documentación alineadas con el estado real

- **(Ubiquitous)** `.agents.md` **deberá** no mencionar `FO_PAQUETE`/`FO_EN_USO` como nomenclatura vigente: se retiran de §3 (línea 33) y del ejemplo ilustrativo (línea 670), conservando el resto de la lista deprecada (`Equipo`, `TEAMS`, `DEVOL`). **Se conserva** la fila de la tabla de §3 «FO Paquete / FO En Uso → Inventario FO» (línea ~40): es el mapeo oficial de nomenclatura deprecada y la spec maestra `003` (REQ-FO-003) sigue vetando esos rótulos. El commit de §5 ya existe (verificación).
- **(Ubiquitous)** `docs/1 Changes.docx` **deberá** eliminarse del repositorio (`git rm`) sin dejar referencias a él fuera de `openspec/changes/archive/` (inmutable; los paquetes archivados lo citan con otra ruta histórica).
- **(Ubiquitous)** `README.md` **deberá** reflejar el estado real: cabeza `0028`, 28 migraciones, conteos de pruebas medidos en las compuertas finales (pytest, archivos de prueba, vitest, archivos vitest), el Inventario FO unificado (sin «módulos `PAQUETE`/`EN_USO`», sin la prosa de `GET /fibra/{modulo}` como estado actual), el historial de cambios de los paquetes `2026-10-fo-unificado-valor-unitario`, `2026-10-purga-legacy-fo` y este.
- **(Ubiquitous)** `backend/db/ddl.sql` **deberá** ser un snapshot schema-only reproducible del esquema `0028` (sin `modulo`, `FO_PAQUETE`, `inventario_fibra` con PK compuesta ni `despliegues`), con una cabecera que indique fecha, comando y cabeza `0028`, y **deberá** mantenerse marcado como referencia no ejecutable sobre bases reales.
- **(Ubiquitous)** `trazabilidad.md` **deberá** consolidar como dispensas formales: verificaciones internas 12(c) y 12(d) de `0028` no disparables desde pruebas externas, E12 solo a nivel de unidad (el rol QA no posee `CREATEDB`) y E9 sin re-ejecución explícita; con justificación y evidencia alternativa de cada una.
- **(Event-driven)** **Cuando** se cierre el paquete, el `pg_dump` `/tmp/opencode/p2_pre_0028.dump` y los scripts auxiliares de `/tmp/opencode` **deberán** destruirse de forma segura (`shred -u`), conservando el directorio. La purga de `p2` deja de ser recuperable; queda registrado.

#### Scenario: Sin referencias legacy en la gobernanza
- **WHEN** se ejecuta `grep -n "FO_PAQUETE\|FO_EN_USO" .agents.md README.md`
- **THEN** no hay coincidencias salvo en el historial de cambios del README que describe la purga

#### Scenario: README coherente
- **WHEN** se compara el README con `ls backend/alembic/versions` y las corridas de pytest/vitest
- **THEN** la cabeza, el conteo de migraciones y los conteos de pruebas coinciden

#### Scenario: DDL reproducible
- **WHEN** se crea una base vacía, se ejecuta `alembic upgrade head` y se vuelca schema-only
- **THEN** el volcado normalizado es idéntico a `backend/db/ddl.sql`

### Requirement: RF-2 IDs fuera de rango INT4 responden 400, nunca 500

- **(Unwanted behavior)** **Si** una solicitud lleva un identificador entero (ruta, query o cuerpo) cuyo valor excede el rango soportado por la columna (SQLSTATE `22003`, `NumericValueOutOfRange`) y la base lo rechaza, **entonces** el sistema **deberá** responder HTTP 400 con el cuerpo de error canónico (`{"error": {"code", "message", "coordinates"}}`) sin efectos secundarios y sin exponer detalles internos de la base.
- **(Ubiquitous)** Un handler global **deberá** cubrir `DBAPIError`/`DataError` con SQLSTATE `22003`, con el predicado **exclusivo** `orig.sqlstate == '22003'` (verificado por `@sec-ops`: PostgreSQL rechaza el valor en el servidor, incluso con `10**30`; **no** hay fallback por mensaje ni por `psycopg.DataError`, que enmascararía errores ajenos), sin alterar el mapeo `22003 → 400` existente en `services/transaccional.py` (mismo código y mensaje de dominio).
- **(Ubiquitous)** El handler **no deberá** enmascarar otros errores de base de datos: cualquier otro SQLSTATE se relanza y conserva su tratamiento actual. El mensaje del 400 es **fijo** (no interpola la excepción) y el cuerpo no contiene «integer», «psycopg» ni SQL.
- **(Ubiquitous)** El contrato OpenAPI **no deberá** cambiar por este requisito.

#### Scenario: ID gigante en ruta
- **WHEN** se solicita `GET /api/v1/equipos/1000000000000/inventario`
- **THEN** la respuesta es HTTP 400 con error canónico y la sesión no queda corrupta para la siguiente solicitud

#### Scenario: ID gigante en cuerpo
- **WHEN** se crea un movimiento con `origen_almacen_id = 10**12`
- **THEN** la respuesta es 400 (no 500) y no se persiste nada

#### Scenario: Otros errores intactos
- **WHEN** una operación viola una restricción UNIQUE
- **THEN** conserva su respuesta actual (409), sin pasar por el handler de `22003`

### Requirement: RF-3 Acotación del header `X-Actor`

- **(Unwanted behavior)** **Si** `X-Actor` está ausente, vacío, solo espacios, excede 100 caracteres o contiene caracteres de control (`\x00`-`\x1f`, `\x7f`-`\x9f`), **entonces** el sistema **deberá** rechazarlo con HTTP 422 antes de consultar la base de datos.
- **(Ubiquitous)** Los actores existentes en `p2` y en el seed de pruebas (`qa`, `intruso`, `demo-operador`, `p2admin` y equivalentes) **deberán** seguir siendo válidos.
- **(Ubiquitous)** La spec **deberá** declarar explícitamente que `X-Actor` es un identificador **no autenticado** y que la autenticación real (credenciales, tokens, rol del actor expuesto en el contrato) está **fuera de alcance** de este y de los paquetes anteriores. Se reconoce como **desviación conocida de la Constitución §3.1/§3.3, reconocida por el humano** (no es cumplimiento ni dispensa §8.2); se registra en `trazabilidad.md`.
- **(Ubiquitous)** `openspec.yaml › paths` **deberá** reflejar la restricción de longitud/formato del header.

#### Scenario: Actor demasiado largo
- **WHEN** se envía `X-Actor` de 101 caracteres
- **THEN** la respuesta es 422 y no se ejecuta ninguna consulta de scopes

#### Scenario: Actor con caracteres de control
- **WHEN** se envía `X-Actor` con un tabulador (por HTTP) o con un salto de línea / NUL (por `ASGITransport`/dependencia directa, pues h11 no admite un salto de línea real en un header)
- **THEN** la respuesta es 422

### Requirement: RF-4 Poda de código muerto y deprecado

- **(Ubiquitous)** `frontend/src/components/Sidebar.tsx` **deberá** no contener la propiedad `children` de `NavItem` ni su rama de renderizado.
- **(Ubiquitous)** `formatMxnConMoneda` (`utils/formatMxn.ts`) y `parseCantidadDecimal` (`utils/cantidad.ts`) **deberán** eliminarse junto con sus pruebas; solo las usan pruebas, sin consumidores de UI. `esCantidadDecimalValida`, `validarCantidad` y `formatMxn` **permanecen**.
- **(Ubiquitous)** Los filtros `desde_id_lista`, `hasta_id_lista`, `desde_sku` y `hasta_sku` **deberán** eliminarse del frontend (`services/catalog.ts`) y del backend (`api/v1/catalog.py`, `services/catalogo.py`, `tests/test_catalogo.py`). Los filtros vigentes (`buscar`, `categoria_id`, rangos ordinales y por descripción) **permanecen**.
- **(Unwanted behavior)** **Si** un cliente externo envía alguno de los cuatro filtros eliminados, **entonces** el sistema **deberá** ignorarlos sin error (parámetro de consulta desconocido).
- **(Ubiquitous)** `ActaItem` (TS) **deberá** declarar `origen_almacen_id?: number | null` y `origen_nombre?: string | null`, igualando `schemas/reporte.py`.
- **(Ubiquitous)** El OpenAPI **deberá** cambiar únicamente en: (a) la eliminación de los cuatro query params de `GET /api/v1/catalogo` y (b) las restricciones del header `X-Actor` (RF-3). Cualquier otra diferencia invalida la Congelación Contractual.

#### Scenario: Sidebar sin ramas muertas
- **WHEN** se ejecuta `grep -n "children" frontend/src/components/Sidebar.tsx`
- **THEN** no hay coincidencias

#### Scenario: Listado sin filtros eliminados
- **WHEN** se solicita `GET /api/v1/catalogo?desde_sku=B`
- **THEN** responde 200 y el filtro no se aplica

### Requirement: RF-5 Convención canónica `EXITO`

- **(Ubiquitous)** El único valor de `auditoria_eventos.resultado` emitido por el código vivo y por las stored functions vigentes **deberá** ser `'EXITO'`.
- **(Ubiquitous)** Un test guardián **deberá** fallar si: (a) alguna stored function vigente (`pg_get_functiondef` de `public`) inserta un `resultado` distinto de `'EXITO'`, o el `DEFAULT` de la columna es distinto de `'EXITO'` o nulo; (b) algún `INSERT`/asignación de `resultado` en `backend/app` usa otro literal (comprobación defensiva: hoy `backend/app` no contiene ninguno); o (c) `auditoria_eventos` contiene valores distintos de `'EXITO'` tras ejecutar la suite de flujos.
- **(Ubiquitous)** No se modifica `0027` ni se reescriben eventos históricos (ledger append-only); el `'OK'` histórico de `0027` queda exento y documentado.

#### Scenario: Valor distinto rechazado por el guardián
- **WHEN** una función inserta `resultado = 'OK'`
- **THEN** el test guardián falla

### Requirement: RF-6 No regresión

- **(Ubiquitous)** Tras el paquete **deberán** pasar, ejecutadas **en serie** (`p2_test` compartida): pytest, `sql_tests`, `mypy`, `tsc -b`, `eslint`, `vitest run` y `vite build` sin advertencias, y `openspec validate --specs --strict` 3/3.
- **(Ubiquitous)** No se añaden migraciones ni se modifica ninguna existente (`0027` y `0028` incluidas).
- **(Ubiquitous)** Los comportamientos vivos (RBAC por scope, `extra="forbid"`, idempotencia, ledger inmutable, saldos) **no deberán** cambiar.

---

## 3. Fuera de Alcance

- Autenticación real, tokens, MFA y exposición del rol del actor en el contrato (RFC aparte, D-3 del paquete `fo-unificado`).
- Tipo explícito de sección en `MovimientoOut`/`AuditoriaOut`.
- CHECK de base de datos sobre `resultado` o cualquier migración nueva.
- Cotas `le=INT4` en los esquemas Pydantic (D-2 usa solo el handler).
- Cambios de dominio, nuevas funcionalidades o cambios en las stored functions.
- Reescritura de eventos históricos o de `0027`.

## 4. Casos Límite

| ID | Caso | Resultado esperado |
| :-- | :-- | :-- |
| E1 | ID mayor que `bigint` (p. ej. `10**30`) | 400 (el rechazo es del servidor PostgreSQL, SQLSTATE `22003`); un entero de miles de dígitos da 422 de Pydantic y no llega a la BD |
| E2 | ID negativo o 0 | Comportamiento actual (404/422); no lo cubre `22003` |
| E3 | Excepción dentro de una transacción abierta con el handler | La sesión se revierte; la siguiente solicitud funciona |
| E4 | `X-Actor` de exactamente 100 caracteres | Válido |
| E5 | `X-Actor` con espacios internos (`Juan Perez`) | Válido (solo se rechazan caracteres de control) |
| E6 | Cliente externo con `desde_sku` | Parámetro ignorado, 200 |
| E7 | Regeneración de `ddl.sql` sin PostgreSQL disponible | Aborta la tarea; no se commitea un DDL vacío |
| E8 | `shred` sobre archivos ya inexistentes | No es un error; se registra |
| E9 | README con cifras distintas a las de la última corrida | Se corrige antes del cierre |

## 5. Riesgos

| # | Riesgo | Mitigación |
| :-- | :-- | :-- |
| R1 | Quitar filtros del backend rompe a un cliente externo desconocido | Los params desconocidos se ignoran (no 422); se documenta en el cierre |
| R2 | La validación de `X-Actor` rechaza actores existentes con formato inesperado | Verificación contra `p2` (actores en `actor_almacen_scopes`, `administradores`, `equipos_integrantes`) antes de activar la regla |
| R3 | El handler `22003` enmascara errores reales | Se acota por SQLSTATE; prueba negativa con `23505` |
| R4 | `shred` irreversible | Última tarea, con confirmación previa de que las compuertas finales pasaron |
| R5 | `ddl.sql` no reproducible por diferencias de versión de `pg_dump` | Cabecera con versión; verificación por normalización de líneas |
