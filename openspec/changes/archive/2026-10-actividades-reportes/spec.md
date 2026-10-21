# Especificación — ETAPA 2/3: ACTIVIDADES (Reportes y Exportación)

**Paquete:** `2026-10-actividades-reportes` · **Fase SDD:** 3 (Especificación) · **Estado:** aprobada (Fases 3-8 cerradas; archivado en Fase 9).
**Fuente de requisitos:** `docs/2 Unities Functions.docx` (Reports_Logical_Automation, Emision_Reportes_*) y las directrices del humano para la Etapa 2 (modelo 1 hoja = 1 folio, tope de 100 hojas, desglose por folio en la interfaz). Gobernanza: `docs/constitution.md` (L1), `.agents.md` (L2). Base: `REQ-ACT-001..020` (Etapa 1, `openspec/specs/003_inventory_dashboard`).

## 1. Propósito

Poner a disposición de los usuarios las actividades confirmadas en la Etapa 1 como **reporte oficial**: consulta filtrada por Unidad, fechas y operación (folio), inspección individual de cada folio y descarga en `REPORTE DE ACTIVIDADES.xlsx` sobre la plantilla corporativa, con una hoja por folio. Se completan además los selectores de operación de Entrega y Consumo diferidos desde la Etapa 1.

## 2. Alcance

**Dentro (Etapa 2):** endpoint de lectura/exportación, servicio de generación XLSX sobre plantilla, subsección Reportes › Actividades, selectores de operación en Entrega y Consumo, enlace desde el aviso de confirmación de actividad.
**Fuera (otras etapas / no objetivos):**
- «Referencia» de materiales → Etapa 3.
- Consultas agregadas o totales por periodo (el documento no los define).
- Bloque COLABORADORES de la plantilla (queda en blanco para firma manual).
- Edición o borrado de actividades; escritura en BD; migraciones; autenticación real.
- Cambios a los reportes de Entrega/Consumo en backend o plantillas.

## 3. Glosario y nomenclatura

- **Unidad:** texto oficial de UI. En código/rutas/parámetros el identificador técnico permanece `equipo`/`equipo_id` (REQ-UNI-005; protegido por `backend/tests/test_unidad_nomenclatura.py`).
- **Actividad / Folio:** definidos en la Etapa 1 (registro inmutable; folio `R0001…`).
- **Operación:** documento confirmado seleccionable por su identificador visible: **Acta** (Entrega), **Seguimiento** (Consumo), **Actividad** (folio) (docx, «Emision_Reportes_*»).
- **Libro consolidado:** archivo XLSX con una hoja por folio de la consulta. **Libro individual:** el mismo formato con una sola hoja (una operación).
- **Zona de negocio:** zona horaria IANA configurable del servidor (`P2_REPORTES_TZ`, por defecto `America/Mexico_City`) con la que se interpretan `desde`/`hasta` y se imprime la fecha de Actividades.
- **Plantilla oficial:** `backend/app/templates/REPORTE DE ACTIVIDADES.xlsx` (hoja `401-450`).

## 4. Reglas de negocio (extraídas del docx y de las directrices del humano)

- **RN-1** El reporte de actividades se llena con los datos confirmados en la subsección ACTIVIDADES de la Unidad; las celdas de materiales se automatizan según la cantidad de materiales existentes.
- **RN-2** Los reportes se pueden elegir por rango de fechas **y** por operación realizada.
- **RN-3** Cada folio se vuelca en una hoja independiente, titulada con el folio, con su cabecera, cliente, dirección, vehículo, actividades y materiales aislados de los demás.
- **RN-4** Máximo 100 hojas/folios por descarga; si la consulta los excede, HTTP 422.
- **RN-5** La interfaz muestra el desglose individual de cada folio del rango y permite tanto la descarga del libro consolidado como la inspección (y descarga) individual por folio.
- **RN-6** Entrega y Consumo reciben el mismo selector de operación (Acta, Seguimiento).

## 5. Requisitos funcionales (EARS)

Cada requisito tiene identificador inmutable `REQ-REP-NNN` (Constitución §1.5) y alias `RF-n` (§2 de `.agents.md`).

### RF-1 [REQ-REP-001] Subsección Actividades en Reportes (ubicuo)
The system SHALL ofrecer en Reportes una subsección llamada «Actividades», ubicada después de «Consumo» en la barra de subsecciones, sin alterar el orden ni el comportamiento de «Entrega» y «Consumo».

### RF-2 [REQ-REP-002] Consulta de actividades confirmadas (dirigido por evento)
WHEN el cliente solicita `GET /reportes/actividades` con `formato=json` (valor por defecto), the system SHALL devolver las actividades confirmadas (`ActividadListOut`, DTO congelado en la Etapa 1) que cumplan los filtros indicados, ordenadas de la más reciente a la más antigua, con folio, fecha, Unidad, vehículo, clientes, direcciones, actividades, comentarios y materiales. The system SHALL aceptar los filtros `equipo_id`, `desde`, `hasta` y `actividad_id`, combinables con semántica AND; sin filtros, el reporte abarca todas las Unidades visibles para el actor.

### RF-3 [REQ-REP-003] Aislamiento por Unidad (estado)
WHILE el actor no sea administrador, the system SHALL limitar el reporte a las Unidades de las que es integrante: IF `equipo_id` indica una Unidad ajena, THEN HTTP 403; IF `actividad_id` pertenece a una Unidad ajena, THEN la actividad SHALL tratarse como inexistente (resultado vacío; 404 en `formato=xlsx`) sin revelar su existencia. El administrador SHALL ver todas las Unidades. The system SHALL NOT excluir actividades de Unidades dadas de baja (el historial documental se conserva). IF `equipo_id` no corresponde a ninguna Unidad, THEN el administrador SHALL recibir un resultado vacío (HTTP 404 en `formato=xlsx`) y el actor no administrador HTTP 403, indistinguible del de una Unidad ajena; esta consulta no aplica la regla «404 antes que 403» de REQ-ACT-014, propia de los endpoints por Unidad.

### RF-4 [REQ-REP-004] Filtro de fechas en zona de negocio (dirigido por evento)
WHEN se indican `desde` y/o `hasta` (fechas calendario `AAAA-MM-DD`), the system SHALL interpretarlas como días completos de la zona de negocio e incluir las actividades cuya fecha de confirmación (REQ-ACT-009) cumpla `>= inicio de desde` y `< inicio del día siguiente a hasta`, de forma que ambos extremos sean inclusivos. Cada extremo SHALL aplicarse de forma independiente: con solo `desde` el filtro es `>= inicio de desde`; con solo `hasta`, `< inicio del día siguiente a hasta`. IF `desde` es posterior a `hasta`, THEN the system SHALL responder HTTP 422 sin consultar datos de negocio; la validación de parámetros (formato y `desde > hasta`) SHALL preceder a la autorización y a la consulta. The system SHALL usar la misma zona de negocio para imprimir la FECHA del XLSX (REQ-REP-007).

### RF-5 [REQ-REP-005] Selección por operación (dirigido por evento)
WHEN se indica `actividad_id`, the system SHALL devolver únicamente esa actividad (si cumple los demás filtros y el aislamiento), de modo que el usuario pueda elegir reportes por operación y no solo por fechas. The system SHALL exponer en la respuesta JSON, por cada actividad, el folio `R`+número como etiqueta de la operación. `actividad_id` SHALL combinarse con AND con los demás filtros: una actividad que no cumple otro filtro produce resultado vacío (404 en `formato=xlsx`).

### RF-6 [REQ-REP-006] XLSX sobre la plantilla oficial (dirigido por evento)
WHEN el cliente solicita `formato=xlsx`, the system SHALL generar el libro cargando la plantilla oficial `REPORTE DE ACTIVIDADES.xlsx` e inyectando datos en sus celdas, conservando estilos, celdas combinadas y el logo corporativo; the system SHALL NOT generar un workbook desde cero. La ruta de la plantilla SHALL ser una constante del servidor (sin participación de datos de usuario) y el archivo en disco SHALL permanecer sin modificar.

### RF-7 [REQ-REP-007] Mapeo de campos desde el snapshot (ubicuo)
The system SHALL volcar en cada hoja, exclusivamente desde el registro persistido (nunca del catálogo ni del stock vigentes): FOLIO (`FOLIO: R0001`), FECHA (fecha de confirmación en la zona de negocio, texto `20 / OCTUBRE / 2026`), VEHÍCULO, NOMBRE (clientes), DIRECCION, una fila de materiales por línea del snapshot (CANTIDAD, U.M., MATERIAL y VALOR UNITARIO **congelado**), una fila por actividad realizada y COMENTARIOS (vacío si no hay). The system SHALL NOT realizar aritmética de stock ni de valor: las cantidades y el valor unitario se transportan tal como están registrados; el bloque COLABORADORES SHALL quedar en blanco.

### RF-8 [REQ-REP-008] Desborde de la plantilla (estado)
WHILE una actividad tenga más de 10 materiales, más de 4 actividades realizadas o comentarios más largos que el área de la plantilla, the system SHALL ampliar la hoja sin perder información ni formato: insertar filas de materiales y de actividades copiando el estilo y las celdas combinadas de la fila de referencia, desplazar hacia abajo el contenido posterior (celdas, combinaciones, alturas e imágenes) y ajustar las alturas de las filas del área de COMENTARIOS y, si la altura requerida supera la capacidad de sus filas (409,5 pt por fila, límite de Excel), ampliar el área insertando filas y extendiendo sus celdas combinadas, de modo que el texto completo (hasta 2000 caracteres, con saltos de línea) quede íntegro y visible. Criterio verificable: la suma de alturas de las filas del área ≥ líneas estimadas × 13,2 pt (líneas estimadas = Σ por párrafo de `max(1, ceil(largo / caracteres por línea))`), ninguna fila supera 409,5 pt y el valor de la celda es igual al texto original. Las descripciones de material más largas que el ancho de su celda SHALL envolverse con la misma regla. Una actividad con cero materiales SHALL generar la hoja con la tabla de materiales vacía.

### RF-9 [REQ-REP-009] Una hoja por folio y tope de 100 (ubicuo)
The system SHALL generar el libro con exactamente una hoja por folio de la consulta, titulada con el folio (`R0001`), ordenadas por folio ascendente, e incluir el logo corporativo en **todas** las hojas. El libro SHALL contener únicamente hojas de folio (la hoja residual `Sheet1` de la plantilla no se incluye). IF la consulta excede 100 folios, THEN the system SHALL responder HTTP 422 con mensaje indicativo y SHALL NOT generar el archivo.

### RF-10 [REQ-REP-010] Seguridad y límites del XLSX (no deseado)
IF un texto de usuario inicia (tras espacios) con `=`, `+`, `-` o `@`, THEN the system SHALL neutralizarlo antes de escribirlo en la celda (sin evaluación de fórmulas). The system SHALL construir el nombre del adjunto solo con constantes, el folio y la fecha, saneado a `[A-Za-z0-9._-]`. IF `formato=xlsx` no produce ninguna actividad, THEN HTTP 404 sin archivo. The system SHALL imponer un límite de 10 000 filas inyectadas por libro (materiales + actividades de todas las hojas) con HTTP 422 `LIMITE_FILAS_EXCEDIDO`, y generar el XLSX sin bloquear la atención de otras solicitudes.

### RF-11 [REQ-REP-011] Contrato y errores canónicos (ubicuo)
The system SHALL exponer el endpoint `GET /api/v1/reportes/actividades` con los códigos 200, 400, 403, 404 y 422, reutilizando los DTOs `ActividadListOut`/`ActividadOut`; los parámetros inválidos (`formato`, fechas, identificadores no numéricos o ≤ 0) y los parámetros no declarados SHALL responder HTTP 422 con el cuerpo estándar de validación `{"detail":[…]}`; los identificadores positivos fuera de INT4 SHALL responder el 400 canónico `NUMERIC_OUT_OF_RANGE`; los errores de regla de negocio (404 sin resultados; 422 `RANGO_FECHAS_INVALIDO`, `LIMITE_HOJAS_EXCEDIDO`, `LIMITE_FILAS_EXCEDIDO`) SHALL usar el cuerpo `{"error":{"code","message","coordinates"}}`; el 403 conserva el cuerpo vigente de autorización. La ausencia o invalidez de `X-Actor` SHALL responder 422 sin consultar datos de negocio. Ningún error de regla de negocio SHALL producir HTTP 500 ni exponer detalles SQL.

### RF-12 [REQ-REP-012] Desglose por folio e inspección individual (ubicuo)
The system SHALL presentar en Reportes › Actividades el listado con una fila por folio (folio, fecha en hora local, Unidad, vehículo, cliente, dirección, número de actividades y de materiales, usuario) y SHALL permitir inspeccionar cada folio —materiales con CANTIDAD, MATERIAL, U.M. y VALOR UNITARIO congelado, actividades realizadas y comentarios— sin salir de la subsección. The system SHALL ofrecer los filtros Unidad, Desde, Hasta y el selector de operación (folio) con las etiquetas de interfaz «Unidad», «Desde», «Hasta» y «Actividad».

### RF-13 [REQ-REP-013] Descarga consolidada e individual con estados (dirigido por evento)
WHEN el usuario pulsa la descarga del libro consolidado, the system SHALL solicitar `formato=xlsx` con los filtros vigentes; WHEN pulsa la descarga de un folio, SHALL solicitar `actividad_id` de ese folio. The system SHALL mostrar en todo momento el estado de la descarga (en curso, exitosa con nombre de archivo, rechazada con el detalle del backend, incluidos 404 y 422 por tope de 100), SHALL deshabilitar las descargas con motivo visible mientras no haya listado, haya error o el resultado esté vacío, y SHALL limpiar el resultado al cambiar de filtros.

### RF-14 [REQ-REP-014] Selectores de operación en Entrega y Consumo (dirigido por evento)
WHEN el usuario elige una operación en Reportes › Entrega (Acta) o Reportes › Consumo (Seguimiento), the system SHALL restringir el listado y la exportación a esa operación enviando el `acta_id` existente del backend; las opciones SHALL derivarse de las actas del listado vigente (Unidad y fechas) y mostrar su identificador visible. The system SHALL NOT modificar el backend, los contratos ni las plantillas de Entrega y Consumo.

### RF-15 [REQ-REP-015] Enlace desde la confirmación y frescura del listado (dirigido por evento)
WHEN una actividad se confirma con éxito (REQ-ACT-017), the system SHALL ofrecer en el aviso de éxito un acceso directo a «Reportes › Actividades» que abra la subsección con la Unidad y el folio recién confirmado preseleccionados; IF no hay navegación disponible, THEN la acción SHALL ocultarse (sin botón inerte). The system SHALL invalidar el listado de Reportes › Actividades tras confirmar una actividad, de modo que el folio nuevo aparezca sin recarga manual.

### RF-16 [REQ-REP-016] Solo lectura sin efectos (ubicuo)
The system SHALL NOT modificar `actividades_reportes`, `inventario_equipos`, `seguimientos`, `seguimiento_items`, `actas_reportes`, el catálogo ni cualquier saldo de stock al consultar o exportar actividades, ni SHALL emitir eventos de auditoría por la consulta o la exportación.

## 6. Requisitos no funcionales

### NF-1 [REQ-REP-017] Regresión y reversibilidad
The system SHALL mantener en verde las suites completas de backend y frontend (incluidos los reportes de Entrega y Consumo y los endpoints `/equipos/{equipo_id}/actividades*`), el build sin warnings, los contratos de `/equipos/{equipo_id}/actividades*` de `openspec/openspec.yaml` sin drift y `openspec validate --specs --strict`. The system SHALL NOT requerir migración Alembic; revertir el paquete SHALL consistir en retirar el router, el servicio y los componentes nuevos.

## 7. Matriz de verificación (Constitución §7.1)

| REQ | Método de verificación |
| --- | --- |
| 001, 012, 013, 014, 015 | vitest (página Reportes, subsección Actividades, desglose, selectores, estados de descarga, enlace del aviso, invalidación) |
| 002, 003, 004, 005 | pytest API + BD (filtros, combinación AND, aislamiento 403/vacío/404, límites de día en zona de negocio, `desde > hasta`) |
| 006, 007, 008, 009 | pytest de plantilla + API: XLSX leído con openpyxl (hojas, celdas, merges, alturas, logo en cada hoja, plantilla sin modificar, desborde) |
| 010 | pytest: neutralización de fórmulas, nombre de archivo, 404/422, límites; revisión `@sec-ops` |
| 011 | `@qa-agent` compuerta de contrato (OpenAPI vs spec) + pytest de errores canónicos |
| 016 | pytest: snapshot de tablas antes/después idéntico y cero eventos de auditoría nuevos |
| 017 | suites completas, build, `openspec validate --specs --strict`, contratos de `/equipos/{equipo_id}/actividades*` de `openspec/openspec.yaml` sin drift |

## 8. Supuestos aprobados por el humano

1. Modelo **1 hoja = 1 folio**, libro consolidado, tope de 100 hojas con HTTP 422 (directriz del humano).
2. La interfaz muestra el desglose por folio, la inspección individual y las dos descargas (directriz del humano).
3. Zona de negocio configurable con valor por defecto `America/Mexico_City`.
4. Los selectores de operación de Entrega y Consumo se implementan solo en frontend.
5. Sin consultas agregadas; COLABORADORES en blanco.
6. Enlace directo desde el aviso de confirmación de actividad (adición aprobada por el humano) y promoción de los `REQ-REP` a `003_inventory_dashboard` en T12.

## 9. Clarificaciones de la Fase 4 (T1, `@arq-reviewer`) — decididas

- **C-1 (DECIDIDA por el humano en T1):** zona de negocio por defecto `America/Mexico_City` para filtros, FECHA impresa y generación de reportes. La zona de sesión de la BD es `America/Ojinaga` (UTC-5 en horario de verano estadounidense; UTC-6 en invierno), mientras `America/Mexico_City` es UTC-6 constante desde el 30-oct-2022 (tzdata 2026c); durante marzo-noviembre difieren una hora. Verificado: la zona existe en `pg_timezone_names` (`CST -06:00`, sin DST).
- **C-2 (propuesta, aceptada en T1):** la fecha del XLSX es **texto** `20 / OCTUBRE / 2026` (día con dos dígitos, sin prefijo «FECHA:» porque `A8` ya lo rotula; reutiliza los nombres de mes de `plantilla_reporte`) en lugar de una fecha de Excel con formato `d / mmmm / yyyy`, porque el nombre del mes de este último depende del idioma del Excel del usuario; el texto es determinista y consistente con las actas.
- **C-3 (ratificada por el humano en T1):** la interfaz muestra la fecha en hora local del **navegador** (REQ-ACT-009) y el XLSX en la zona de negocio; pueden diferir si el navegador está en otra zona. Aceptada y documentada.
- **C-4 (ratificada por el humano en T1):** hoja titulada con el folio (`R0001`) y sin numeración de las actividades (el documento no la define).
- **C-5 (propuesta, precisada en T1):** nombre de archivo `reporte-actividades-R0001.xlsx` cuando el libro tiene **una** hoja (con o sin `actividad_id`) y `reporte-actividades-AAAA-MM-DD.xlsx` cuando tiene dos o más, con la fecha de la actividad de mayor `fecha` en la zona de negocio (no la del último folio: bajo concurrencia el folio ascendente no implica `created_at` ascendente).
- **C-6 (ratificada por el humano en T1):** como en Entrega/Consumo, el listado JSON no tiene tope; el tope de 100 aplica solo a `formato=xlsx` y se evalúa antes de cargar todas las filas (`LIMIT 101`). La paginación queda registrada como deuda para una etapa posterior.
- **C-7 (ratificada por el humano en T1):** el aislamiento sigue el patrón de `/reportes/entrega` (`assert_equipo_access` y `equipos_visibles`), sin prechequeo de «Unidad activa», para no ocultar el historial de Unidades dadas de baja.
- **C-8 (DECIDIDA por el humano en T1, opción a):** Entrega y Consumo filtran `desde/hasta` con `CAST(created_at AS date)` en la zona de **sesión** de la BD (`America/Ojinaga`), mientras Actividades usa la zona de negocio (`America/Mexico_City`). Con los mismos Desde/Hasta de la interfaz, entre las 23:00 y las 24:00 de México en horario de verano estadounidense una misma jornada puede caer en días distintos según la subsección. Alinear `reportes.py` queda fuera de este paquete (plan D-9, REQ-REP-014) y requeriría un RFC aparte (queda registrado como deuda técnica, sin acción en este paquete).
- **C-9 (ratificada por el humano en T1):** el selector de Unidad lista solo Unidades activas (`GET /equipos` filtra `is_active`), igual que Entrega y Consumo; el historial de Unidades dadas de baja se consulta con «Todos» o por folio.
- **C-10 (DECIDIDA por el humano en T1, opción a):** mantener `sanitizar_celda` vigente (neutraliza `=`, `+`, `-`, `@` anteponiendo un apóstrofe literal: un texto legítimo como «- Instalación» se ve con apóstrofe en el XLSX; precedente de las actas). `@sec-ops` lo confirma en T5.
