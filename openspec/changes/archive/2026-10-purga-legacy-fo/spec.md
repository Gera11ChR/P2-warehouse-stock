# Spec: Purga radical del legado Paquete / En Uso del dominio Fibra Óptica

**Change ID:** `2026-10-purga-legacy-fo`
**Identificadores:** `RF-1`..`RF-8` (primarios, usados en `tasks.md` y en `test_RF_<n>_...`) con alias constitucional según este mapeo (Constitución §1.5; coincide con las specs maestras): RF-1, RF-2 y RF-3 → `[REQ-PURGA-001]` (RF-2 además `[REQ-FO-002]`); RF-6 → `[REQ-PURGA-002]`; RF-4 y RF-5 → `[REQ-PURGA-003]`; RF-7 y RF-8 son de procedimiento (sin alias).
**Alcance de esta especificación:** *qué* debe cumplirse (Constitución §1.2). El *cómo* (SQL, archivos) vive en `plan.md`.
**Antecedente:** `archive/2026-10-fo-unificado-valor-unitario` unificó el Inventario FO (0027) pero conservó por compatibilidad las secciones `FO_PAQUETE`/`FO_EN_USO`, su historial y el «código puente» (RF-9 de ese paquete, REQ-FO-002). Este paquete elimina esa compatibilidad.
**Terminología oficial (`.agents.md` §3):** `Inventario FO`, `Unidad`, `TRANSF`, `Confirmar Devolución`. `Paquete`/`En Uso` como inventarios FO quedan **inexistentes**, no solo deprecados.

> **Distinción importante (no son legado FO y NO se tocan):** la unidad de medida `PAQUETE (100 PZ)` del catálogo, los valores `modulo = 'CATALOGO'` de `MATERIAL_MODIFICADO`, los eventos `DESPLIEGUE_*`, y los tipos de movimiento `TEAMS`/`DEVOL`. Ver §4.

---

## 1. Contexto operativo y decisiones de diseño (aprobadas)

- El sistema está en construcción; los datos de `p2` son de prueba (no oficiales). Se prioriza flexibilidad, ergonomía y un esquema mínimo.
- **D-1 (aprobada):** los datos legacy se **borran físicamente**; no se remapean a `FO`.
- **D-2 (aprobada):** la excepción constitucional se formaliza como **enmienda acotada dentro de este paquete** (§3.1); `docs/constitution.md` **no** se modifica.
- **D-3 (aprobada, refinada por la evidencia):** los eventos de auditoría con `modulo` legacy se borran solo si son de dominio FO. El criterio es **por clave JSON** (`modulo`/`origen_modulo`/`destino_modulo` con valor `PAQUETE` o `EN_USO`), no por texto: `MATERIAL_MODIFICADO`/`UM_*` contienen la cadena «PAQUETE (100 PZ)» y `modulo: "CATALOGO"` y **no** son legado FO, por lo que no se borran ni se editan (en la propuesta inicial se preveía quitar la clave `modulo` en ellos; la inspección demostró que no hay nada que quitar).
- **D-4 (aprobada):** `downgrade()` revierte solo el esquema y no aborta (los datos purgados solo se recuperan del `pg_dump`).
- RBAC de producción y autenticación real quedan fuera de alcance (§4); no se relaja ni se añade nada de seguridad.

### 1.1 Inventario de datos afectados en `p2` (medido 2026-10-16, solo lectura)

| Tabla | Criterio de «legacy» | Filas aprox. |
| :-- | :-- | :-- |
| `secciones` | `tipo IN ('FO_PAQUETE','FO_EN_USO')` (ids 2 y 3) | 2 |
| `movimientos_cabecera` | origen/destino legacy **o** alguna línea con origen legacy | 31 (4 BORRADOR, 25 CONFIRMADO, 2 CANCELADO; 10 son mixtos con líneas no legacy) |
| `movimientos_detalle` | `movimiento_id` de los anteriores | cascada |
| `actas_reportes` (ledger, con trigger de inmutabilidad) | `movimiento_id` de los anteriores | 13 |
| `actor_almacen_scopes` | `almacen_id` legacy | 2 |
| `auditoria_eventos` | (a) columnas de almacén legacy; (b) JSON con `modulo` legacy; (c) `tipo_accion='FO_UNIFICADO'`; (d) `detalles.movimiento_id`/`acta_id` de filas purgadas | ≈ 129 de 1016 |
| `operaciones_idempotencia` | `resultado.modulo` legacy | 7 |
| `inventario_almacen` / `inventario_fibra` | no hay filas legacy; **no se tocan** | 0 |

Las cifras son indicativas; la migración y `T2` las recalculan y verifican.

---

## 2. Historias de Usuario

- **HU-1.** Como operador quiero que el sistema no ofrezca ni muestre jamás «Paquete»/«En Uso», para operar solo con **Inventario FO**.
- **HU-2.** Como administrador de base de datos quiero un esquema en el que solo existan secciones `GENERAL` y `FO`, para no mantener ramas ni CHECKs muertos.
- **HU-3.** Como desarrollador quiero eliminar el código puente de 0027, para que el backend y el frontend reflejen solo el dominio vivo.
- **HU-4.** Como auditor quiero que la excepción a la inmutabilidad del ledger esté acotada, justificada y verificada, para que no debilite el resto del control.

---

## 3. Requisitos Funcionales

### Requirement: RF-1 [REQ-PURGA-001] Purga física de datos FO legacy

- **(Event-driven)** **Cuando** se aplique la migración `0028`, el sistema **deberá** eliminar físicamente toda fila que dependa de las secciones `FO_PAQUETE`/`FO_EN_USO` según los criterios de §1.1, incluidos movimientos (cabeceras y líneas, en cualquier estado), actas, scopes de actor, eventos de auditoría y claves de idempotencia asociados.
- **(Ubiquitous)** Un movimiento **deberá** considerarse legacy si su cabecera **o cualquiera de sus líneas** referencia una sección legacy; en ese caso se elimina completo (incluidas sus líneas no legacy), sin alterar ninguna existencia.
- **(Ubiquitous)** Un evento de auditoría **deberá** eliminarse si cumple alguno de: (a) `almacen_origen_id`/`almacen_destino_id` legacy; (b) clave JSON `modulo`/`origen_modulo`/`destino_modulo` (a cualquier profundidad) con valor `PAQUETE` o `EN_USO`; (c) `tipo_accion = 'FO_UNIFICADO'`; (d) `detalles.movimiento_id` o `detalles.acta_id` de una fila purgada.
- **(Ubiquitous)** La lista de criterios (a)–(d) es **cerrada** y es el alcance máximo de E-1. Un movimiento mixto se elimina completo porque un borrado parcial dejaría un movimiento cuya cancelación restituiría solo las líneas no legacy (violaría §2.1). El criterio (c) se justifica como «evidencia de las cantidades Paquete/En Uso», no como dependencia de sección. Consecuencia aceptada: tras la purga el ledger restante ya no concilia con `inventario_fibra` (se pierden `STOCK_INICIAL_FO` y `FO_UNIFICADO`); es aceptable porque los datos son de prueba.
- **(Ubiquitous)** `operaciones_idempotencia` **deberá** purgarse también por `resultado->>'movimiento_id'` de un movimiento purgado (un reintento no puede devolver un movimiento inexistente) y por `resultado.modulo` legacy.
- **(Ubiquitous)** `inventario_equipos.ultimo_movimiento_id` (puntero de trazabilidad sin FK, no es saldo) **deberá** ponerse en `NULL` cuando apunte a un movimiento purgado; ninguna cantidad de unidad cambia.
- **(Ubiquitous)** La migración **deberá** ejecutar un barrido diagnóstico de los literales `FO_PAQUETE`/`FO_EN_USO` (en `detalles`, `actas_reportes.snapshot` y `resultado`) y de claves `almacen_id`/`origen_almacen_id`/`destino_almacen_id` que apunten a ids de secciones legacy en filas supervivientes; si hay residuos, **deberá** abortar (la verificación no puede ser circular con el predicado de borrado).
- **(Unwanted behavior)** **Si** tras la purga persiste cualquier fila que referencie una sección legacy, **entonces** la migración **deberá** abortar y hacer rollback completo.

#### Scenario: Movimiento legacy eliminado con sus dependientes
- **WHEN** existe un movimiento con `origen_almacen_id` = sección `FO_PAQUETE`, con 2 líneas y 1 acta
- **THEN** tras `0028` no existen el movimiento, sus líneas ni su acta, y los eventos que lo citan en `detalles.movimiento_id`

#### Scenario: Movimiento mixto
- **WHEN** un movimiento TEAMS tiene una línea con origen `FO_EN_USO` y otra con origen GENERAL
- **THEN** el movimiento completo se elimina y el saldo de `inventario_almacen` no cambia

#### Scenario: Unidad de medida no se confunde con legado
- **WHEN** un evento `MATERIAL_MODIFICADO` contiene `"u_m": "PAQUETE (100 PZ)"` y `"modulo": "CATALOGO"`
- **THEN** el evento permanece intacto tras `0028`

### Requirement: RF-2 [REQ-PURGA-001 / REQ-FO-002] Esquema con una sola sección FO

- **(Ubiquitous)** La tabla `secciones` **deberá** contener únicamente filas de `tipo IN ('GENERAL','FO')`, con `CHECK ck_secciones_tipo` redefinido a ese conjunto; las secciones legacy **no deberán** existir.
- **(Ubiquitous)** Las funciones PL/pgSQL `fn_procesar_movimiento` y `fn_cancelar_movimiento` **deberán** enrutar FO únicamente mediante `tipo = 'FO'`, sin ramas, comentarios ni literales `FO_PAQUETE`/`FO_EN_USO`.
- **(Ubiquitous)** No **deberá** quedar enum, tipo ni constraint de base de datos que enumere los valores legacy.

#### Scenario: CHECK restringido
- **WHEN** se intenta insertar una sección con `tipo = 'FO_PAQUETE'`
- **THEN** PostgreSQL rechaza la fila por violación de `ck_secciones_tipo`

#### Scenario: Sin residuos en funciones
- **WHEN** se inspecciona `pg_get_functiondef` de todas las funciones tras `0028`
- **THEN** ninguna contiene `FO_PAQUETE` ni `FO_EN_USO`

### Requirement: RF-3 [REQ-PURGA-001] Preservación del dominio vivo

- **(Ubiquitous)** La migración **no deberá** modificar saldos de `inventario_almacen`/`inventario_fibra`/`inventario_equipos` (salvo el puntero `ultimo_movimiento_id` de RF-1), el catálogo, los equipos/unidades, los seguimientos, la sección `FO` ni la sección `GENERAL`, ni los eventos de auditoría y movimientos que no cumplan los criterios de RF-1. La única adición es el evento `PURGA_LEGACY_FO` de RF-6.
- **(Ubiquitous)** La suma global de existencias por material **deberá** ser idéntica antes y después (verificación interna con aborto).
- **(Ubiquitous)** Los saldos **no** se derivan de movimientos (confirmado en el esquema): borrar movimientos no cambia existencias; el ledger restante pierde únicamente historial legacy.
- **(Ubiquitous)** Las secuencias de `id` **no** se reinician.

#### Scenario: Stock intacto
- **WHEN** la migración termina
- **THEN** `SUM(cantidad)` por material en `inventario_almacen` + `inventario_fibra` es igual al valor previo

#### Scenario: Conteo del ledger no legacy
- **WHEN** se comparan los eventos no legacy antes y después
- **THEN** el conteo y el contenido de cada uno son idénticos

### Requirement: RF-4 [REQ-PURGA-003] Backend sin código puente

- **(Ubiquitous)** El backend **deberá** eliminar toda aceptación, ruteo y tratamiento especial de secciones legacy: el `CHECK` del modelo `Seccion` (`models/inventario.py`) **deberá** ser `tipo IN ('GENERAL','FO')`, y `services/movimientos.py` **deberá** validar secciones sin la excepción de BORRADOR legacy (caso E8 de 0027).
- **(Unwanted behavior)** **Si** una solicitud referencia el `almacen_id` de una sección legacy ya purgada, **entonces** el sistema **deberá** responder con la clasificación vigente para sección inexistente (HTTP 422, `"Sección origen inexistente"` / `"Sección destino inexistente"`), sin efectos secundarios.
- **(Ubiquitous)** Docstrings, comentarios, descripciones OpenAPI y mensajes **deberán** dejar de mencionar `FO_PAQUETE`/`FO_EN_USO`/«orígenes históricos».
- **(Ubiquitous)** El contrato OpenAPI **no deberá** cambiar en rutas, campos, tipos, enums ni códigos de estado; solo pueden variar textos de `description`. La diferencia se registra como evidencia (Congelación Contractual).

#### Scenario: Sección purgada
- **WHEN** un cliente crea un borrador TEAMS con `origen_almacen_id = 2` (antes `FO_PAQUETE`)
- **THEN** la respuesta es 422 «Sección origen inexistente» y no se persiste nada

#### Scenario: Sin referencias en el código
- **WHEN** se ejecuta `grep -rnE "FO_PAQUETE|FO_EN_USO" backend/app`
- **THEN** no hay coincidencias

### Requirement: RF-5 [REQ-PURGA-003] Frontend sin lógica ni tipos legacy

- **(Ubiquitous)** `Seccion.tipo` en `frontend/src/types.ts` **deberá** ser `'GENERAL' | 'FO'`.
- **(Ubiquitous)** `utils/auditoriaPresentacion.ts` (que solo oculta módulos históricos) **deberá** eliminarse junto con su uso en `Auditoria.tsx`.
- **(Ubiquitous)** `utils/seccionLabel.ts` **deberá** conservar solo `ETIQUETA_INVENTARIO_FO` y `etiquetaSeccion` (`FO` → «Inventario FO», `GENERAL` → nombre del almacén), sin ramas legacy. `etiquetaSeccionPorId` **deberá** reducirse a una búsqueda por id cuyo respaldo para un id desconocido sea un rótulo neutro (`Sección #<id>`) y **no** «Inventario FO».
- **(Ubiquitous)** Comentarios y textos sobre «orígenes FO históricos» **deberán** eliminarse; no se altera ningún flujo vivo.

#### Scenario: Historial con sección desconocida
- **WHEN** el historial referencia un `almacen_id` que no figura en las secciones transferibles (p. ej. un almacén GENERAL desactivado)
- **THEN** se muestra «Sección #<id>», nunca «Inventario FO»

#### Scenario: Sin referencias en el frontend
- **WHEN** se ejecuta `grep -rnE "FO_PAQUETE|FO_EN_USO" frontend/src`, y se buscan `PAQUETE`/`EN_USO` como valores de sección o módulo (excluidas la unidad `PAQUETE (100 PZ)` y las aserciones negativas de `queryKey` `['fibra','PAQUETE']` que verifican la ausencia de módulos)
- **THEN** no hay coincidencias

### Requirement: RF-6 [REQ-PURGA-002] Migración destructiva, atómica, verificada e irreversible

- **(Ubiquitous)** La revisión `0028` (`down_revision = "0027"`) **deberá** ejecutarse en una sola transacción (§4.1/§4.3): ante cualquier fallo, rollback total.
- **(Unwanted behavior)** **Si** existen filas que dependen del legado FO (movimientos, scopes, saldos de sección o eventos que cumplan RF-1) y `current_database()` no es `p2` ni `p2_test`, **entonces** `0028` **deberá** abortar sin efectos (guardia técnica de E-1). Una base nueva, donde `0010` siembra las secciones legacy sin dependientes, **no** aborta; sin secciones legacy es un no-op de datos.
- **(Event-driven)** **Cuando** la purga termine, la migración **deberá** insertar **un único** evento `tipo_accion = 'PURGA_LEGACY_FO'` (usuario `migracion-0028`) con `detalles` que contenga: referencia `E-1`/`0028`, conteos eliminados por tabla y por `tipo_accion`, y la ruta del `pg_dump` (sin secretos). Es el único evento añadido (§6.2).
- **(State-driven)** **Mientras** dure la migración, los triggers `tg_ledger_auditoria_inmutable` (sobre `auditoria_eventos`) y `tg_ledger_actas_inmutable` (sobre `actas_reportes`) **deberán** estar deshabilitados, y **deberán** quedar habilitados al terminar; la migración **deberá** verificar ambos (`pg_trigger.tgenabled = 'O'`) y abortar si alguno no lo está.
- **(Ubiquitous)** Los **datos** purgados son irrecuperables por Alembic (solo desde el `pg_dump` previo). El `downgrade()` **deberá** revertir únicamente el **esquema** (restablecer `ck_secciones_tipo` ampliado y las funciones de 0027), emitir `RAISE NOTICE` «esquema restaurado; los datos purgados no se restauran (usar pg_dump)» y **no deberá** recrear filas ni abortar. La cadena es recorrible en bases sin referencias a la sección `FO` (p. ej. `p2_test` limpia, que es lo que usan las pruebas `esquema_en("0024"|"0025"|"0026")`); en una base con referencias a `FO` el `downgrade` de 0027 aborta por su paso 1b, comportamiento aceptado y documentado.
- **(Ubiquitous)** El procedimiento operativo **deberá** exigir un `pg_dump` previo de `p2` antes de aplicar `0028`.
- **(Ubiquitous)** La migración **no deberá** modificar `REVOKE`/permisos, roles, RBAC ni dejar objetos nuevos.

#### Scenario: Trigger reactivado
- **WHEN** `0028` termina
- **THEN** `DELETE FROM auditoria_eventos ...` y `DELETE FROM actas_reportes ...` fallan con la excepción del trigger

#### Scenario: Downgrade solo de esquema
- **WHEN** se ejecuta `alembic downgrade 0027` tras `0028`
- **THEN** el comando termina sin error, `ck_secciones_tipo` vuelve a admitir los valores legacy, las funciones recuperan el cuerpo de 0027 y **no** reaparece ninguna fila purgada

#### Scenario: Fallo parcial
- **WHEN** la verificación interna detecta un residuo o diferencia de stock
- **THEN** se hace rollback y la base queda en `0027` con el trigger activo

### Requirement: RF-7 (procedimiento) Gobernanza y enmienda acotada

- **(Ubiquitous)** Este paquete **deberá** incluir la enmienda constitucional acotada **E-1** (§3.1) y **no deberá** modificar `docs/constitution.md`.
- **(Ubiquitous)** Al archivar, las specs maestras **deberán** actualizarse:
  - `REQ-FO-002` conserva su ID y se retitula: «no existen secciones legacy; solo `GENERAL` y `FO`; una referencia a un `almacen_id` purgado se rechaza con 422»; se conserva el contrato de `GET /secciones/transferibles` y el escenario «Former origins not selectable»; se retiran los escenarios «Legacy draft still processable» y «Cancelling a legacy movement», la cláusula de etiquetas «Inventario FO» para históricos y la de compatibilidad de borradores; se añade el escenario del 422 por sección purgada.
  - `REQ-FO-001`, escenario «Single balance per material after migration»: se reescribe como comportamiento de la migración histórica, sin exigir la persistencia del evento `FO_UNIFICADO`.
  - `openspec.yaml`: `historical_technical_values` (retira `FO_PAQUETE`/`FO_EN_USO`; mantiene `TEAMS`/`DEVOL`), `historical_events`, `fo_unificado.description` (E8, seguimiento, continuidad de permisos), `audit_ledger_immutability.events` (añade `PURGA_LEGACY_FO`) y `.description` (registra E-1 como dispensa singular), y las descripciones de `paths` afectadas.
- **(Ubiquitous)** `.agents.md` **no deberá** modificarse sin aprobación humana (L2); si hace falta, se propone el texto en el cierre.

### Requirement: RF-8 (procedimiento) No regresión

- **(Ubiquitous)** Tras el paquete **deberán** pasar: pytest (sin los tests de compatibilidad legacy retirados y con los nuevos de `0028`), `sql_tests`, `mypy`, `tsc`, `eslint`, `vitest` y `vite build`, ejecutadas **en serie** (la base `p2_test` es compartida).
- **(Ubiquitous)** Los tests que verificaban la compatibilidad legacy (E8, D-2, borradores y confirmados con origen legacy) **deberán** retirarse y reemplazarse por pruebas de que la compatibilidad ya no existe.
- **(Ubiquitous)** `0027` **no deberá** editarse: ya está publicada en commits; el cambio de esquema va solo en `0028`.

---

### 3.1 Enmienda constitucional acotada E-1 (Constitución §8.1)

**Naturaleza:** dispensa **singular, acotada y registrada** a las cláusulas §2.4 y §6.2; **no** edita el texto de `docs/constitution.md`. Este `spec.md` (E-1) y `plan.md` (impacto técnico y plan de migración) hacen de propuesta OpenSpec formal (`.agents.md` §2 define el paquete como `spec`/`plan`/`tasks`). El instrumento queda registrado además en `openspec.yaml › audit_ledger_immutability` para que un auditor que lea solo L1 lo encuentre.

| Campo (§8.1) | Contenido |
| :-- | :-- |
| **Base procedimental** | §8.1 (procedimiento de enmienda) y §8.2 (no-bypassability: por eso es una dispensa formal y no una interpretación) |
| **Cláusulas dispensadas** | §2.4 (ledger append-only: `auditoria_eventos` y `actas_reportes`) y §6.2 (eventos de auditoría inmutables) |
| **Justificación** | Datos exclusivamente de prueba; el esquema legacy impone costo permanente (CHECKs, ramas SQL, tipos TS, tests) sin valor probatorio. |
| **Impacto técnico** | `plan.md` §1 (migración `0028`) y §2-§3 (poda de código) |
| **Plan de migración de specs existentes** | RF-7 y `plan.md` §5 |
| **Alcance (limitativo)** | Lista **cerrada** RF-1 (a)–(d); una única migración (`0028`); solo `p2` y `p2_test` (guardia técnica de RF-6). |
| **Lo que NO se dispensa** | La inmutabilidad vía API; los triggers `tg_ledger_auditoria_inmutable` y `tg_ledger_actas_inmutable` (activos antes y después, verificados); saldo ≥ 0, atomicidad (§4.1/§4.3: transacción única y rollback total), default-deny, `extra="forbid"`. |
| **Rastro** | La purga emite un evento inmutable `PURGA_LEGACY_FO` (§6.2) con conteos y referencia a E-1. |
| **Irreversibilidad** | La irreversibilidad post-commit se acepta solo por E-1 y se mitiga con el `pg_dump` previo. |
| **Vigencia** | Autoriza la ejecución de `0028` únicamente sobre `p2` y `p2_test`; en cualquier otra base con datos legacy la guardia lo impide. No autoriza purgas futuras. |
| **Aprobación** | Aprobación humana del paquete registrada en `tasks.md` (2026-10-16) + dictámenes `@arq-reviewer` (T1) y `@sec-ops` (T3). |

---

## 4. Fuera de Alcance

- RBAC real, autenticación real (`X-Actor`), rol del actor y tipo explícito de sección (seguimientos del paquete anterior).
- Eventos `DESPLIEGUE_*` y sus etiquetas «(histórico)» en `types.ts` (legado distinto: nomenclatura Unidad, REQ-P2-CON-001).
- La unidad de medida `PAQUETE (100 PZ)` y los `modulo: 'CATALOGO'`.
- Los tipos de movimiento `TEAMS`/`DEVOL`.
- `backend/db/ddl.sql` (referencia histórica) y `0027` (no se edita).
- Cualquier cambio de contrato (rutas, campos, tipos) o funcionalidad nueva.

## 5. Casos Límite

| ID | Caso | Resultado esperado |
| :-- | :-- | :-- |
| E1 | Movimiento mixto (líneas legacy y no legacy) | Se elimina completo; stock intacto |
| E2 | Borradores legacy pendientes | Se eliminan |
| E3 | Evento `FO_UNIFICADO` | Se elimina (auditoría de la fusión legacy) |
| E4 | Evento que cita `acta_id`/`movimiento_id` purgado | Se elimina (sin referencias colgantes) |
| E5 | `MATERIAL_MODIFICADO` con «PAQUETE (100 PZ)» | Se conserva |
| E6 | Actor con scope solo legacy | Pierde el scope legacy; conserva el scope `FO` copiado por 0027 |
| E7 | Base en `0027` sin datos legacy | La migración es un no-op de datos y redefine CHECK/funciones |
| E8 | Reaplicar `0028` | Idempotente por Alembic; no se re-ejecuta |
| E9 | Re-ejecución tras fallo | Rollback total; `0027` intacta |
| E12 | `0028` en una base distinta de `p2`/`p2_test` con dependientes legacy | Aborta sin efectos (guardia); sin dependientes (base nueva) pasa |
| E13 | `ultimo_movimiento_id` apuntando a un movimiento purgado | Pasa a `NULL`; cantidades intactas |
| E11 | `downgrade` de 0028 y re-`upgrade` | El esquema vuelve a 0027 sin datos legacy; re-aplicar `0028` es un no-op de datos |
| E10 | Cliente con `almacen_id` 2/3 | 422 «Sección … inexistente» |
