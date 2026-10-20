# Especificación — ETAPA 1/3: ACTIVIDADES (Registro) en Inventario por Unidad

**Paquete:** `2026-10-actividades-unidad` · **Fase SDD:** 3 (Especificación) · **Estado:** aprobado por el humano; Fase 4 (T1) clarificada, ver §9.
**Fuente de requisitos:** `docs/2 Unities Functions.docx` (secciones "Actividades" e interfaz de captura). Gobernanza: `docs/constitution.md` (L1), `.agents.md` (L2).

## 1. Propósito

Añadir la subsección **ACTIVIDADES** a *Inventario por Unidad* (junto a Consulta, Configuración y CONSUMO) para registrar las actividades hechas en el día. Cada registro confirmado es un documento inmutable que hereda los materiales del seguimiento de CONSUMO cerrado, recibe un folio y una fecha automáticos y queda disponible como fuente de datos para los reportes de la Etapa 2.

## 2. Alcance

**Dentro (Etapa 1):** tabla y función de BD, endpoints FastAPI, pestaña y formulario de captura, auditoría del evento.
**Fuera (otras etapas / no objetivos):**
- Emisión, listado por fechas/operación y llenado de `REPORTE DE ACTIVIDADES.xlsx` → Etapa 2.
- Selectores de Entrega/Consumo en Reportes → Etapa 2.
- "Referencia" de materiales → Etapa 3.
- Edición o borrado de actividades confirmadas; autenticación real (X-Actor sigue siendo no autenticado, desviación ya reconocida).
- Modificar stock, seguimientos, actas o catálogo.

## 3. Glosario y nomenclatura

- **Unidad:** texto oficial de UI. En código/BD/rutas el identificador técnico permanece `equipo`/`equipos`/`equipo_id` (no se renombra; regla vigente protegida por `backend/tests/test_unidad_nomenclatura.py`, REQ-UNI-005).
- **Actividad (registro):** documento confirmado, asociado a un seguimiento CERRADO.
- **Seguimiento pendiente de actividad:** el seguimiento `CERRADA` más reciente (por `closed_at`) de la Unidad que no tiene actividad confirmada.
- **Folio:** identificador visible `R` + número correlativo global con mínimo 4 dígitos (`R0001`, `R0002`, …, `R10000`; sin truncar).
- **Materiales consumidos:** líneas de `seguimiento_items` con `cantidad_consumida`, tal como las registra CONSUMO.

## 4. Reglas de negocio (extraídas del docx, aplicables a la Etapa 1)

- **RN-1** Los materiales no se capturan: son los consumidos del seguimiento cerrado (CANTIDAD | MATERIAL | U.M.), más VALOR UNITARIO tomado del valor referente del material.
- **RN-2** El folio es automático. La fecha es automática y se registra al confirmar.
- **RN-3** Los campos Cliente(s) y Dirección(es) muestran placeholders de ejemplo, tal cual.
- **RN-4** "+ Agregar" añade celdas manuales para más actividades realizadas.
- **RN-5** Campos manuales: Vehículo, Cliente(s), Dirección(es), Actividades realizadas, Comentarios.
- **RN-6** El botón "Confirmar" emite el registro.

## 5. Requisitos funcionales (EARS)

Cada requisito tiene identificador inmutable `REQ-ACT-NNN` (Constitución §1.5) y alias `RF-n` (§2 de `.agents.md`).

### RF-1 [REQ-ACT-001] Subsección ACTIVIDADES (ubicuo)
The system SHALL ofrecer en Inventario por Unidad una subsección llamada "ACTIVIDADES", ubicada después de CONSUMO en la barra de subsecciones.

### RF-2 [REQ-ACT-002] Herencia de materiales consumidos (dirigido por evento)
WHEN el usuario abre ACTIVIDADES de una Unidad que tiene un seguimiento pendiente de actividad, the system SHALL mostrar en solo lectura los materiales consumidos de ese seguimiento con CANTIDAD, MATERIAL, U.M. y VALOR UNITARIO (valor vigente del material al momento de la consulta).

### RF-3 [REQ-ACT-003] Vínculo 1 a 1 con el seguimiento (no deseado)
IF la Unidad no tiene seguimiento pendiente de actividad, THEN the system SHALL deshabilitar "Confirmar", mostrar un aviso indicando que debe cerrarse un seguimiento en CONSUMO, y el backend SHALL rechazar la confirmación con HTTP 409.
IF el `seguimiento_id` enviado no existe o no pertenece a la Unidad, THEN the system SHALL responder 404.
IF el seguimiento no está `CERRADA` o ya tiene una actividad confirmada, THEN the system SHALL responder 409 sin crear registro.
The system SHALL NOT imponer en el backend que el seguimiento sea el más reciente: cualquier seguimiento `CERRADA` de la Unidad sin actividad es confirmable; solo la interfaz ofrece el más reciente (C-1 resuelta).

### RF-4 [REQ-ACT-004] Seguimiento sin consumo (estado)
WHILE un seguimiento cerrado tenga cero materiales con `cantidad_consumida` > 0, the system SHALL permitir confirmar la actividad con la lista de materiales vacía.

### RF-5 [REQ-ACT-005] Campos de cabecera y placeholders (ubicuo)
The system SHALL presentar los campos Fecha (solo lectura, etiqueta "Automatizado"), Vehículo, Nombre Cliente(s) y Dirección(es), con los placeholders exactos «Ej. Acelmo Hernández, Guillermina Juárez, …» (Cliente) y «Ej. Huapacal 2da, Los Palmares, …» (Dirección).
The system SHALL exigir Vehículo, Cliente(s) y Dirección(es) no vacíos (tras recortar espacios) y con longitud máxima 100, 500 y 500 caracteres respectivamente.

### RF-6 [REQ-ACT-006] Actividades realizadas y "+ Agregar" (dirigido por evento)
The system SHALL presentar inicialmente una celda de actividad realizada.
WHEN el usuario pulsa "+ Agregar", the system SHALL añadir una celda adicional vacía, hasta un máximo de 30 celdas.
The system SHALL exigir al menos una celda con contenido; las celdas vacías se descartan al confirmar; cada celda admite máximo 500 caracteres.

### RF-7 [REQ-ACT-007] Comentarios (opcional)
WHERE el usuario capture Comentarios, the system SHALL guardarlos (máximo 2000 caracteres); si se omiten, SHALL guardar ausencia de comentarios.

### RF-8 [REQ-ACT-008] Folio automático (dirigido por evento)
WHEN se confirma una actividad, PostgreSQL SHALL asignar el siguiente número correlativo global, único y sin huecos (los confirmados exitosamente), y el sistema SHALL exponer el folio como `R` + número con relleno de ceros a 4 dígitos mínimo.
The system SHALL NOT aceptar un folio enviado por el cliente.

### RF-9 [REQ-ACT-009] Fecha automática (dirigido por evento)
WHEN se confirma una actividad, PostgreSQL SHALL registrar la fecha-hora con `now()` (timestamptz). The system SHALL NOT aceptar una fecha enviada por el cliente. La interfaz SHALL presentar la fecha en hora local del navegador del usuario.

### RF-10 [REQ-ACT-010] Snapshot de materiales y valor unitario (ubicuo)
WHEN se confirma una actividad, the system SHALL congelar en el registro la lista de materiales (`material_id`, código, descripción, U.M., cantidad consumida y `valor_unitario` vigente) derivada exclusivamente de PostgreSQL. Cambios posteriores en catálogo o seguimientos SHALL NOT alterar el registro confirmado. The system SHALL NOT aceptar materiales ni valores unitarios enviados por el cliente.

### RF-11 [REQ-ACT-011] Atomicidad e idempotencia (ubicuo)
The system SHALL ejecutar la confirmación en una única transacción mediante una Stored Function de PostgreSQL, con bloqueo `FOR UPDATE` sobre el seguimiento y restricción UNIQUE sobre `seguimiento_id`. Dos confirmaciones concurrentes o un reintento sobre el mismo seguimiento SHALL producir exactamente un registro; la otra solicitud SHALL responder 409.

### RF-12 [REQ-ACT-012] Inmutabilidad y auditoría (ubicuo)
The system SHALL tratar la actividad confirmada como append-only: UPDATE y DELETE SHALL ser rechazados por trigger de base de datos. The system SHALL NOT ofrecer edición ni borrado de actividades confirmadas.
WHEN se confirma una actividad, the system SHALL emitir en `auditoria_eventos` un evento `ACTIVIDAD_CONFIRMADA` con `usuario` = actor, `equipo_origen_id` = Unidad, resultado `EXITO` y `detalles` con `actividad_id`, `folio`, `seguimiento_id` y `equipo_id` (convención de `ACTA_CONSUMO_GENERADA`).

> **Nota de alcance de la corrección (consulta para Fase 4):** como `seguimiento_id` es UNIQUE, un seguimiento con actividad confirmada no admite otra. Si el usuario se equivoca no hay vía de corrección en la Etapa 1. Esto se acepta explícitamente por la decisión de inmutabilidad (Constitución §2.4) y se señala como riesgo conocido.

### RF-13 [REQ-ACT-013] Validación de entrada (no deseado)
IF el cuerpo de la solicitud contiene campos no declarados, tipos incorrectos, textos fuera de los límites de RF-5/RF-6/RF-7 o caracteres de control (C0 excepto salto de línea en Comentarios, DEL, C1), THEN the system SHALL responder HTTP 422 sin acceder a datos de negocio.

### RF-14 [REQ-ACT-014] Autorización por Unidad (estado)
WHILE el actor no sea administrador ni integrante de la Unidad, the system SHALL responder 403 en todos los endpoints de actividades; IF la Unidad no existe, THEN 404 (404 antes de 403, patrón vigente de seguimientos). The system SHALL exigir actor autenticado (`assert_authenticated`) en el POST.

### RF-15 [REQ-ACT-015] Sin efectos sobre inventario (ubicuo)
The system SHALL NOT modificar `inventario_equipos`, `seguimientos`, `seguimiento_items`, `actas_reportes`, el catálogo ni cualquier saldo de stock al consultar o confirmar una actividad.

### RF-16 [REQ-ACT-016] Consulta de actividades de la Unidad (dirigido por evento)
WHEN el cliente solicita `GET /equipos/{equipo_id}/actividades`, the system SHALL devolver las actividades confirmadas de esa Unidad, ordenadas de la más reciente a la más antigua, con folio, fecha, vehículo, clientes, direcciones, actividades, comentarios y materiales.

### RF-17 [REQ-ACT-017] Presentación del estado de la operación (ubicuo)
The system SHALL mostrar al usuario en todo momento el estado de la operación de confirmación (pendiente, exitosa, rechazada); tras éxito SHALL mostrar el folio asignado y refrescar el estado desde el backend (sin estado de stock local), y el formulario SHALL quedar sin seguimiento pendiente (RF-3).

## 6. Requisitos no funcionales

### NF-1 [REQ-ACT-018] Contrato y nomenclatura
The system SHALL exponer los campos en snake_case en español conforme al contrato de `plan.md` §4; ningún alias legacy. Los textos de UI SHALL usar "Unidad" (nunca "Equipo").

### NF-2 [REQ-ACT-019] Errores deterministas
The system SHALL mapear los errores de las Stored Functions a HTTP 400/404/409/422 con el cuerpo de error canónico `{"error":{"code","message","coordinates"}}`; nunca 500 por reglas de negocio ni exposición de detalles SQL.

### NF-3 [REQ-ACT-020] Reversibilidad y regresión
The system SHALL proveer migración Alembic 0029 con `downgrade()` sin pérdida de las tablas preexistentes, y SHALL mantener en verde las suites completas de backend y frontend, build sin warnings y `openspec validate --specs --strict`.

## 7. Matriz de verificación (Constitución §7.1)

| REQ | Método de verificación |
| --- | --- |
| 001, 005, 006, 007, 017 | vitest (componente `ActividadesPanel`, pestaña, placeholders, "+ Agregar", estados) |
| 002, 003, 004, 016 | pytest API + BD (GET pendiente / POST / GET lista) |
| 008, 009, 010, 011 | pytest SQL/API: folio correlativo, concurrencia (2 POST simultáneos), snapshot, `now()` |
| 012 | pytest: UPDATE/DELETE rechazados por trigger; evento en `auditoria_eventos` |
| 013 | pytest API: 422 por extras, límites, caracteres de control |
| 014 | pytest API: 403/404 con `client_sin_scope`, admin, integrante |
| 015 | pytest: snapshot de `inventario_equipos`/`seguimientos`/`actas_reportes` antes/después idéntico |
| 018, 019 | @qa-agent compuerta de contrato (OpenAPI vs spec) + pytest de mapeo de errores |
| 020 | `alembic upgrade/downgrade` en `test_migracion_0029`, suites completas, build |

## 8. Supuestos aprobados por el humano

1. Un seguimiento cerrado con cero consumo permite registrar la actividad con materiales vacíos (RF-4).
2. El folio es global y correlativo (RF-8).
3. La fecha se presenta en hora local (RF-9).

## 9. Clarificaciones de Fase 4 (T1, `@arq-reviewer`) — resueltas

- **C-1 (resuelta):** la interfaz ofrece solo el seguimiento cerrado más reciente sin actividad; el backend acepta cualquier seguimiento `CERRADA` de la Unidad sin actividad (RF-3). Los anteriores solo son alcanzables por API y no se garantiza que todos tengan actividad (la actividad es documental).
- **C-2 (aceptada):** el folio no tiene huecos entre transacciones confirmadas; una transacción revertida no consume número (RF-8).
- **C-3 (aceptada):** el valor unitario mostrado antes de confirmar (RF-2) puede diferir del congelado (RF-10) si el catálogo cambia entre ambos instantes; el congelado manda.
- **C-4 (resuelta):** el evento de auditoría sigue la convención de `ACTA_CONSUMO_GENERADA` (RF-12); no se usa payload `modulo/accion/valores_*`, que el contrato maestro vigente no exige.
- **C-5 (resuelta):** `auditoria_eventos.tipo_accion` es `varchar(50)` sin CHECK de enumeración; la migración 0029 no lo modifica.
- **C-6 (resuelta):** Constitución §1.1 (L1) exige `proposal.md`; se agrega `proposal.md` al paquete (L1 prevalece sobre la lista de L2 en `.agents.md` §2).
