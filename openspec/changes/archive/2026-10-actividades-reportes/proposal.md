# Propuesta — ETAPA 2/3: ACTIVIDADES (Reportes y Exportación)

**Paquete:** `2026-10-actividades-reportes` · Requerida por Constitución §1.1. Fuente: `docs/2 Unities Functions.docx` (secciones «Reports_Logical_Automation», «Emision_Reportes_Actividades/Entrega/Consumo»). Depende de la Etapa 1 (`2026-10-actividades-unidad`, archivada).

## Motivación

La Etapa 1 registra actividades confirmadas e inmutables (folio `R0001…`, fecha, snapshot de materiales con valor unitario congelado), pero hoy solo pueden consultarse una Unidad a la vez desde Inventario por Unidad. El formato oficial `REPORTE DE ACTIVIDADES.xlsx` (ya presente en `backend/app/templates/`) no se llena en ningún flujo, y la sección Reportes solo ofrece Entrega y Consumo, que además solo filtran por Unidad y fechas: el documento pide poder elegir también por **operación** (Acta, Seguimiento, Actividad).

## Qué cambia

- **Reportes › Actividades** (nueva subsección, tras Consumo): listado con desglose individual por folio, filtros por Unidad, rango de fechas y operación (folio), inspección individual de cada folio y descarga del XLSX.
- **Exportación XLSX** sobre la plantilla oficial, sin crear un Excel desde cero: modelo **1 hoja = 1 folio**; un libro consolidado con una hoja por folio (hoja titulada con el folio, tope de 100 hojas por descarga → HTTP 422) o un libro de una sola hoja al elegir una operación.
- **Endpoint** `GET /api/v1/reportes/actividades` (solo lectura; `formato=json|xlsx`), con aislamiento por Unidad y fechas interpretadas en una zona horaria de negocio configurable.
- **Selectores de operación** en Reportes › Entrega (Acta) y Reportes › Consumo (Seguimiento), diferidos desde la Etapa 1; solo frontend: el backend ya acepta `acta_id`.
- **Enlace directo** desde el aviso de éxito al confirmar una actividad hacia Reportes › Actividades, con la Unidad y el folio recién confirmado preseleccionados.

## No objetivos (fuera de la Etapa 2)

- «Referencia» de materiales → **Etapa 3**.
- Consultas agregadas/totales por periodo (el documento no las define).
- Bloque COLABORADORES de la plantilla: las líneas de firma quedan **en blanco** para firma manual.
- Edición o borrado de actividades; cualquier escritura en BD; autenticación real (X-Actor sigue sin autenticar, desviación ya reconocida).
- Cambios a los reportes de Entrega y Consumo (backend, plantillas, contrato).

## Impacto

- **Constitucional:** respeta §2.4 (solo lectura sobre un ledger inmutable), §3.1 (default-deny y aislamiento por Unidad), §3.5 (parámetros validados; XLSX sin inyección de fórmulas), §1.5 (identificadores `REQ-REP-NNN`) y §7.1 (cada REQ con verificación). Sin enmienda.
- **Datos:** **sin migración**. `actividades_reportes` ya tiene `equipo_id`, `created_at` indexado `(equipo_id, created_at DESC)` y el snapshot de materiales. Si el `EXPLAIN` de T4 demostrara que el filtro por fechas sin Unidad requiere un índice, se tramita como RFC (nunca un parche silencioso).
- **Contrato:** un endpoint nuevo; reutiliza `ActividadListOut`/`ActividadOut` congelados en la Etapa 1 (no se modifica el contrato archivado).
- **Frontend:** nueva subsección y componentes; cambios acotados en `Reportes.tsx`, `ActividadesPanel.tsx`, `queryKeys.ts` y el tipo `NavigationTarget` (campo opcional).
- **Seguridad:** el XLSX incorpora texto libre de usuario (vehículo, clientes, direcciones, actividades, comentarios); toda celda se sanitiza contra inyección de fórmulas y el nombre de archivo es constante saneada.

## Incompatibilidades y riesgos conocidos

| # | Hallazgo | Tratamiento |
| --- | --- | --- |
| I-1 | `wb.copy_worksheet` de openpyxl **no copia el logo** (verificado: 0 imágenes en la copia). | Re-incrustar el logo en cada hoja; spike en T2, cubierto por pruebas (T3). |
| I-2 | La plantilla admite 10 materiales, 4 actividades y 3 filas de comentarios; la Etapa 1 permite hasta 30 actividades de 500 caracteres, comentarios de 2000 y materiales sin tope fijo. | Insertar filas (reutilizando `_desplazar_filas`) y ajustar alturas; REQ-REP-008. |
| I-3 | La plantilla trae una hoja residual `Sheet1` (líneas de firma sueltas) además de la hoja `401-450`. | El libro generado contiene solo hojas de folio; la plantilla en disco no se modifica. |
| I-4 | La zona de sesión de la BD es `America/Ojinaga` (UTC-5 en horario de verano), mientras que México no observa horario de verano (`America/Mexico_City`, UTC-6). | Zona de negocio configurable (por defecto `America/Mexico_City`, decisión del humano); C-1 **decidida** por el humano en T1 (zona verificada en `pg_timezone_names`). |
| I-5 | El listado JSON no tiene tope (igual que las actas). | Filtros obligatorios por uso; paginación fuera de alcance, registrada como deuda. |
| I-6 | Entrega y Consumo filtran fechas con la zona de **sesión** de la BD (`America/Ojinaga`) y Actividades con la zona de negocio: la misma jornada puede caer en días distintos entre las 23:00 y las 24:00 (horario de verano de EE. UU.). | DECIDIDO en T1 (B-1, opción a): registrado como C-8 (deuda técnica); alinear `reportes.py` requiere un RFC aparte. |

## Documentos

`spec.md` (REQ-REP-001..017) · `plan.md` (Backend-First) · `tasks.md` (T1..T12) · `.openspec.yaml`.
