# Propuesta — ETAPA 1/3: ACTIVIDADES (Registro) en Inventario por Unidad

**Paquete:** `2026-10-actividades-unidad` · Requerida por Constitución §1.1. Fuente: `docs/2 Unities Functions.docx`.

## Motivación
Hoy el cierre de un seguimiento en CONSUMO descuenta stock y emite el Acta de Consumo, pero no existe un registro de las actividades realizadas durante la jornada (cliente, dirección, vehículo, trabajos) asociado a ese consumo. Los reportes de actividades del formato oficial necesitan esa información como dato confirmado y trazable.

## Qué cambia
- Nueva subsección **ACTIVIDADES** en Inventario por Unidad (tras CONSUMO).
- Nuevo documento inmutable "Actividad", 1 a 1 con un seguimiento CERRADO, con folio `R0001…` y fecha automáticos, materiales heredados del consumo (con valor unitario congelado) y campos manuales: Vehículo, Cliente(s), Dirección(es), Actividades realizadas (+ Agregar) y Comentarios.
- Migración 0029, 3 endpoints bajo `/api/v1/equipos/{equipo_id}/actividades`, pestaña y formulario en React.

## No objetivos
- Emitir o descargar el reporte XLSX, filtros por fecha/operación y selectores de Reportes → Etapa 2.
- "Referencia" de materiales → Etapa 3.
- Editar o borrar actividades confirmadas; autenticación real; modificar stock, seguimientos, actas o catálogo.

## Impacto
- **Constitucional:** respeta §2.4 (ledger inmutable), §2.3/§4.1 (atomicidad y serialización), §3.5 (`extra="forbid"`), §6.2 (evento de auditoría). Sin enmienda.
- **Datos:** una tabla nueva y dos funciones; ninguna tabla existente se modifica.
- **Riesgo conocido:** sin vía de corrección tras confirmar (decisión de inmutabilidad).

## Documentos
`spec.md` (REQ-ACT-001..020) · `plan.md` (Backend-First) · `tasks.md` (T1..T12).
