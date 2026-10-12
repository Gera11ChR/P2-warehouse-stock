# Spec: Equipo → Unidad y opciones de Consulta

**Change ID:** `2026-10-12-equipo-a-unidad`
**Fuente:** Punto 1 de `docs/migracion-dms-telecom/P2_Implementaciones_Contexto_Agente.md` + `images/Consulta&Nomenclatura.png`
**Override vigente:** Unidad / TRANSF / Confirmar Devolución / Inventario FO (ver `.agents.md` §3).

> Convención de identificadores: cada requisito lleva un `RF-n` (directiva del sprint) y su identificador constitucional `[REQ-UNI-NNN]` (Constitución §1.5). Los tests citan `REQ-UNI-NNN`.

## Resumen

1. Sustituir "Equipo/Equipos" por "Unidad/Unidades" en todo texto visible al usuario (interfaz y mensajes `detail` de la API). El módulo pasa a llamarse **Inventario por Unidad**.
2. La pestaña **Consulta** incorpora un select box con tres vistas: **Inventario Unidad** (por defecto), **Descripción** e **Integrantes**.

## Alcance de la aplicación del Override en este paquete

El Override de `.agents.md` §3 se aplica aquí **solo a la capa de presentación y a los mensajes de error** (UI, `detail` de la API, textos `RAISE EXCEPTION`). No se renombran rutas (`/equipos`), campos (`equipo_id`), tablas, columnas ni enumeraciones: eso es una decisión de arquitectura aprobada para este paquete (ver `plan.md` D1) y cualquier renombrado estructural requeriría su propio paquete.

## Historias de usuario

- Como administrador, quiero ver "Unidad" en todo el sistema para que coincida con el lenguaje de la operación.
- Como administrador, quiero consultar la descripción y los integrantes de una unidad sin abrir el formulario de edición.

## Requisitos funcionales (EARS)

### Nomenclatura

- **RF-1 [REQ-UNI-001] (Ubiquitous).** La interfaz **deberá** mostrar "Unidad"/"Unidades" en lugar de "Equipo"/"Equipos" en todo texto visible: menú lateral, breadcrumb, títulos, etiquetas, botones, modales, toasts, placeholders, estados vacíos, cabeceras de tabla, reportes y actas.
- **RF-2 [REQ-UNI-002] (Ubiquitous).** El módulo **deberá** titularse "Inventario por Unidad" en el menú lateral, el breadcrumb y el encabezado de la página.
- **RF-3 [REQ-UNI-003] (Ubiquitous).** Los textos **deberán** ser "Crear Unidad", "Seleccionar Unidad", "Modificar Unidad", "Eliminar Unidad" y "Nombre por Unidad" (hoy "Nombre de Cuadrilla").
- **RF-4 [REQ-UNI-004] (Ubiquitous).** Los textos **deberán** respetar la concordancia de género de "unidad" ("Unidad creada", "Unidad modificada", "Unidad eliminada", "Seleccione una unidad", "Unidad Origen", "Unidad Destino").
- **RF-5 [REQ-UNI-005] (Unwanted behavior).** **Si** un texto corresponde a la unidad de medida "EQUIPO" o a la categoría de material "Equipos", **entonces** el sistema **no deberá** renombrarlo. Tampoco **deberá** renombrar rutas `/equipos`, campos `equipo_id`, tablas, columnas, claves de ruta interna ni enumeraciones.
- **RF-6 [REQ-UNI-006] (Ubiquitous).** El campo `detail` de las respuestas de error de la API **deberá** usar "Unidad"/"unidad" donde hoy dice "Equipo"/"equipo".
- **RF-7 [REQ-UNI-007] (Unwanted behavior).** **Si** se cambia el texto de una excepción de función almacenada, **entonces** el mapeo de errores **deberá** conservar los códigos HTTP actuales (404 para "no pertenece a la unidad", 400 para "Stock insuficiente en la Unidad…"), y el cuerpo de las funciones **no deberá** cambiar salvo en los literales de texto.
- **RF-8 [REQ-UNI-008] (Ubiquitous).** El contrato de la API (rutas, métodos, campos, códigos) **deberá** permanecer sin cambios. `GET /equipos/{id}` **deberá** seguir devolviendo `descripcion` (nullable) e `integrantes`.

### Consulta

- **RF-9 [REQ-UNI-010] (State-driven).** **Mientras** haya una Unidad seleccionada, la pestaña Consulta **deberá** mostrar un select box con las opciones "Inventario Unidad", "Descripción" e "Integrantes".
- **RF-10 [REQ-UNI-011] (State-driven).** **Mientras** no se haya elegido ninguna opción, Consulta **deberá** mostrar "Inventario Unidad".
- **RF-11 [REQ-UNI-012] (Event-driven).** **Cuando** se elija "Descripción", el sistema **deberá** mostrar la descripción de la Unidad. **Si** es nula, vacía o solo espacios, **deberá** mostrar el apartado vacío, sin error ni texto inventado (campo opcional).
- **RF-12 [REQ-UNI-013] (Event-driven).** **Cuando** se elija "Integrantes", el sistema **deberá** listar los integrantes de la Unidad y su cantidad. **Si** no hay integrantes, **deberá** mostrar el apartado vacío.
- **RF-13 [REQ-UNI-014] (Event-driven).** **Cuando** cambie la Unidad seleccionada, el select de Consulta **deberá** volver a "Inventario Unidad". *(Confirmado por el solicitante.)*
- **RF-14 [REQ-UNI-015] (Unwanted behavior).** **Si** no hay Unidad seleccionada, la interfaz **no deberá** mostrar el select de Consulta y **deberá** mostrar "Seleccione una unidad".
- **RF-15 [REQ-UNI-016] (Ubiquitous).** Consulta **deberá** ser de solo lectura: no **deberá** invocar endpoints de escritura ni requerir endpoints nuevos.
- **RF-16 [REQ-UNI-017] (Event-driven).** **Cuando** se elija "Inventario Unidad", la tabla y sus columnas actuales **deberán** permanecer sin cambios. Los botones Modificar y Eliminar **deberán** permanecer donde están, visibles con cualquier opción del select.

### Calidad

- **RF-17 [REQ-UNI-020] (Ubiquitous).** `pytest`, `sql_tests`, `vitest`, `tsc -b`, `eslint .`, `mypy` y `openspec validate --specs --strict` **deberán** pasar al 100% (Constitución §7.2).
- **RF-18 [REQ-UNI-021] (Ubiquitous).** Un test automatizado **deberá** fallar si aparece "Equipo/Equipos" en texto visible del frontend fuera de la lista blanca de RF-5.

## Casos límite

- Descripción nula, vacía o solo espacios.
- Unidad con cero integrantes.
- Unidad eliminada (soft delete) o inactiva mientras el select está abierto.
- Cambio de unidad con "Integrantes" o "Descripción" activos (RF-13).
- Usuario sin acceso a la unidad: el 403 conserva su código y su texto usa "unidad".
- Colisión con la U.M. "EQUIPO" y la categoría "Equipos" (RF-5).
- Nombres de unidad almacenados que contengan la palabra "Equipo": son datos, no se modifican.
- Snapshots históricos (p. ej. `equipo_nombre` en actas ya generadas): son registros inmutables (Constitución §2.4) y no se reescriben.

## Fuera de alcance

- Puntos 2-10 del documento de contexto (Inventario FO, Consumido, TRANSF/Confirmar Devolución, Valor Unitario, Referencia de materiales y su botón "Referencia").
- Renombrar rutas, campos, tablas, columnas, vistas o enumeraciones.
- Cambios de lógica de stock o de funciones transaccionales distintos del texto de sus excepciones.
- Edición de los prompts de `.opencode/agents/`.

## Criterios de finalización

1. RF-1..RF-18 con evidencia de test automatizado.
2. Matriz de trazabilidad RF → T → Test completa.
3. Contrato API congelado y sin diff de rutas ni DTOs antes de iniciar el frontend.
4. Gates de Constitución §7.2 en verde.
5. Aprobación humana.

## Matriz de trazabilidad

| RF | REQ | Tareas | Verificación |
| --- | --- | --- | --- |
| RF-1..RF-4 | REQ-UNI-001..004 | T11, T12 | vitest (textos) + RF-18 |
| RF-5 | REQ-UNI-005 | T11, T12 | lista blanca en test RF-18 |
| RF-6 | REQ-UNI-006 | T4, T6 | pytest `test_REQ_UNI_006_*` |
| RF-7 | REQ-UNI-007 | T4, T7, T8 | pytest + sql_tests `test_REQ_UNI_007_*` |
| RF-8 | REQ-UNI-008 | T4, T10 | pytest + diff OpenAPI |
| RF-9..RF-16 | REQ-UNI-010..017 | T13 | vitest `InventarioPorEquipos` |
| RF-17 | REQ-UNI-020 | T9, T15 | ejecución de suites |
| RF-18 | REQ-UNI-021 | T12 | vitest (barrido de textos) |
