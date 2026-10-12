# Plan técnico (Backend-First): Equipo → Unidad y Consulta

**Change ID:** `2026-10-12-equipo-a-unidad` · **Spec:** `spec.md` (RF-1..RF-18)

## 1. Estrategia

Renombrado exclusivamente en la capa de presentación y en los mensajes de error. Sin cambios de esquema, contrato ni lógica transaccional. Orden: tests rojos → textos `detail` → migración `0024` → suite backend → congelamiento del contrato → frontend.

## 2. Revisión de impacto constitucional

| Artículo | Impacto |
| --- | --- |
| §2.1 Saldo no negativo | Ninguno: no se toca la aritmética de stock. |
| §2.3 Serialización | Ninguno: los `FOR UPDATE` de las funciones permanecen. |
| §2.4 Ledger inmutable | Ninguno: no se reescriben `auditoria_eventos` ni snapshots (`equipo_nombre` en actas). |
| §3.1/§3.2 Autorización | Ninguno: `assert_equipo_access` y su 403 conservan comportamiento; solo cambia el texto. |
| §3.5 Payloads | Ninguno: `extra="forbid"` intacto. |
| §4.1 Atomicidad | Ninguno: la lógica sigue en PL/pgSQL. |

Conclusión (@arq-reviewer): **cambio de nomenclatura, no de dominio**. Sin enmienda constitucional.

## 3. Modelo de datos (PostgreSQL / PL/pgSQL)

- Sin cambios en tablas, columnas, vistas, índices ni enumeraciones (`equipos`, `equipos_integrantes`, `inventario_equipos`, `equipo_id`, `TEAMS`, `DEVOL`, `FO_*` permanecen).
- **Migración `0024_unidad_textos_raise`** (solo literales de texto), `down_revision = 0023`.
  - Mecanismo: para cada función afectada, `upgrade()` lee la definición vigente con `pg_get_functiondef(oid)`, sustituye únicamente los literales listados abajo y la re-crea con `CREATE OR REPLACE`. Así el cuerpo parte siempre de la versión viva (hoy repartida en `0014`, `0016`, `0020` y `0021`) y no se copia a mano.
  - `downgrade()` aplica la sustitución inversa.
  - Se aborta (`RAISE`) si un literal esperado no se encuentra en la función, para evitar migraciones silenciosamente vacías.
- Funciones y literales (versión vigente → nueva):

| Función | Literal actual | Literal nuevo |
| --- | --- | --- |
| `fn_procesar_movimiento` | `El equipo ID % no cuenta con stock suficiente del material ID LISTA % para devolver.` | `La unidad ID % no cuenta con stock suficiente del material ID LISTA % para devolver.` |
| `fn_cancelar_movimiento` | `Stock insuficiente en el Equipo destino (ID %) para revertir …` | `Stock insuficiente en la Unidad destino (ID %) para revertir …` |
| `fn_crear_seguimiento` | `El equipo ID % no existe o se encuentra inactivo.` | `La unidad ID % no existe o se encuentra inactiva.` |
| `fn_crear_seguimiento` | `El equipo ID % ya posee un seguimiento abierto.` | `La unidad ID % ya posee un seguimiento abierto.` |
| `fn_cerrar_seguimiento` | `Stock insuficiente en el Equipo ID % para el material ID LISTA % …` | `Stock insuficiente en la Unidad ID % para el material ID LISTA % …` |
| `fn_agregar_todo_seguimiento` | `El seguimiento ID % no pertenece al equipo ID %.` | `El seguimiento ID % no pertenece a la unidad ID %.` |

- `fn_crear_despliegue` / `fn_cerrar_despliegue` son restos de la renombra a `seguimiento`: si existen en la BD, se procesan igual que las anteriores; si no, se ignoran.
- Verificación (@dba-guard): `pg_get_functiondef` antes y después; el diff debe contener solo los literales de la tabla. `alembic upgrade head` → `downgrade -1` → `upgrade head` debe ejecutar limpio.

## 4. Contrato de API (FastAPI / Pydantic v2)

- Rutas, métodos, DTOs y códigos HTTP: **sin cambios** (RF-8). `EquipoOut` ya expone `descripcion: str | None` e `integrantes: list[str]`; Consulta reutiliza `GET /equipos/{id}`. Sin endpoints nuevos.
- Mensajes `detail` → "Unidad" (RF-6):

| Archivo | Texto actual | Texto nuevo |
| --- | --- | --- |
| `app/api/v1/equipos.py` | `Equipo no encontrado` | `Unidad no encontrada` |
| `app/services/transaccional.py` | `Equipo no encontrado` | `Unidad no encontrada` |
| `app/services/movimientos.py` | `Equipo destino inexistente` / `Equipo origen inexistente` | `Unidad destino inexistente` / `Unidad origen inexistente` |
| `app/security.py` | `El actor no tiene acceso a este equipo` | `El actor no tiene acceso a esta unidad` |

- **Mapeo de errores por subcadena** (`app/services/transaccional.py`, ~l.169 → 404 `no pertenece al equipo`; ~l.187 → 400 `Stock insuficiente en el Equipo`): se actualiza a `no pertenece a la unidad` / `Stock insuficiente en la Unidad` (RF-7). Durante la transición el mapeo acepta ambas variantes para que un despliegue con migración pendiente no cambie el código HTTP. Se revisan igualmente las demás subcadenas del mapeo (p. ej. `no existe o se encuentra inactivo` → `inactiva`).
- Seguridad (@sec-ops): sin cambios en RBAC ni en `extra="forbid"`.
- Los identificadores de Python (`EquipoOut`, `assert_equipo_access`, etc.) no se renombran (RF-5).

## 5. Tests backend (@tester)

Se citan con `REQ-UNI-NNN` en nombre o docstring:

- `test_REQ_UNI_006_*`: cada `detail` de equipos/movimientos/seguridad usa "Unidad".
- `test_REQ_UNI_007_*`: stock insuficiente → 400 y no pertenece → 404 tras el cambio de texto (también cubiertos en `sql_tests`).
- `test_REQ_UNI_008_*`: `GET /equipos/{id}` devuelve `descripcion` (incluido `null`) e `integrantes`; el OpenAPI no cambia en rutas ni DTOs.
- Ajustes a tests existentes con texto antiguo: `tests/test_fo_transferencias.py:371`, `sql_tests/test_fase1_consumo.py:697`; se revisa `:751` (el snapshot `equipo_nombre == "Equipo QA"` es dato de prueba, no texto de UI).

## 6. Frontend (bloqueado hasta congelar el contrato, T10)

- Textos visibles (RF-1..RF-4): `InventarioPorEquipos`, `EquipoForm`, `EquipoInventoryTable`, `Transferencias`, `Reportes`, `ReporteSubseccion`, `ReporteEntregaTable`, `ReporteConsumoTable`, `Auditoria`, `SeguimientoPanel`, `SeguimientoNuevaListaForm`, `ActaGeneradaAviso`, `Sidebar`, `MainLayout`, `utils/reporteExport`, `utils/agregarTodo`.
- Se mantienen: nombres de archivo/componente, tipos (`Equipo`), query keys, rutas `/equipos`, clave interna `inventario-por-equipos`.
- Select de Consulta (RF-9..RF-16) en `pages/InventarioPorEquipos.tsx`: estado local `consultaVista: 'inventario' | 'descripcion' | 'integrantes'` (por defecto `'inventario'`), reseteado al cambiar `equipoId`. `descripcion` e `integrantes` salen de la entidad `Equipo` ya cargada; sin servicio nuevo. Estados vacíos para descripción y para integrantes. Solo lectura.
- Test nuevo de la página (hoy inexistente) y test de barrido de textos con lista blanca para U.M. "EQUIPO" y categoría "Equipos" (RF-18).
- Agentes: `@state-agent` (tipos/keys), `@ux-agent` (flujo y vacíos), `@form-agent` (`EquipoForm`), `@ui-agent` (textos y select).

## 7. Decisiones arquitectónicas

- **D1** Renombrado solo en presentación y mensajes; API/BD conservan nombres técnicos. Un renombrado estructural exigiría un paquete propio (toca ~24 revisiones Alembic y el contrato).
- **D2** Migración de texto con rollback, basada en la definición viva de cada función.
- **D3** El mapeo de errores sigue acoplado al texto; se cubre con tests y con aceptación temporal de ambas variantes.
- **D4** Sin endpoints nuevos.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Migración con cuerpo desactualizado | Lectura de `pg_get_functiondef` + diff solo de literales. |
| Cambio silencioso de 404/400 | Tests REQ-UNI-007 y mapeo con ambas variantes. |
| Falsos positivos del barrido RF-18 | Lista blanca explícita (U.M. "EQUIPO", categoría "Equipos"). |
| Snapshots/actas históricas | No se reescriben (Constitución §2.4). |
