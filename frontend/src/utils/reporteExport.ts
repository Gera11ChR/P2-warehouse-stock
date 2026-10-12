import type { FormatoExportacion } from '../components/ReporteExportButtons'

export type ReporteTipo = 'entrega' | 'consumo'

export type ReporteExportStatus =
  | { estado: 'idle' }
  | { estado: 'loading'; formato: FormatoExportacion }
  | { estado: 'success'; formato: FormatoExportacion; nombreArchivo?: string }
  | {
      estado: 'error'
      formato: FormatoExportacion
      /** Código HTTP de la respuesta (si lo hubo; undefined = sin respuesta). */
      httpStatus?: number
      /** Mensaje del backend (`error.message`), se conserva como detalle. */
      detalle?: string
    }

export const TIPO_LABEL: Record<ReporteTipo, string> = {
  entrega: 'Entrega',
  consumo: 'Consumo',
}

export const FORMATO_LABEL: Record<FormatoExportacion, string> = {
  normal: 'Normal',
  extenso: 'Extenso',
}

/** Traduce el fallo a contexto operativo (sin ocultar el detalle técnico). */
export function mensajeErrorExportacion(
  tipo: ReporteTipo,
  httpStatus?: number,
): string {
  const acta = `Acta de ${TIPO_LABEL[tipo]}`
  if (httpStatus === 404) {
    return `No hay actas de ${TIPO_LABEL[tipo]} para los filtros seleccionados, así que no se generó el archivo. Ajusta la unidad o el rango de fechas e inténtalo de nuevo.`
  }
  if (httpStatus === 422) {
    return `Los filtros no son válidos y no se generó el ${acta}. Revisa las fechas e inténtalo de nuevo.`
  }
  if (httpStatus === 401 || httpStatus === 403) {
    return `No tienes permiso para exportar el ${acta}.`
  }
  return `No se pudo generar el archivo del ${acta}. Inténtalo nuevamente; si el problema continúa, avisa a soporte.`
}

