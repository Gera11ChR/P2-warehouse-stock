import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import type { ReporteActividadesExportStatus } from '../hooks/useReportes'

// ============================================================================
// FEEDBACK DE EXPORTACIÓN DEL REPORTE DE ACTIVIDADES — presentacional
// (REQ-REP-013)
//
// Máquina de estados de PRESENTACIÓN de la descarga del libro XLSX
// (consolidado o individual):
//   idle → loading → success | error
// La capa de estado produce el `ReporteActividadesExportStatus` a partir de
// la respuesta real; este componente solo lo traduce a copy operativo y a
// anuncios accesibles. No hace red ni decide validez. Nunca silencio: cada
// estado distinto de idle tiene un anuncio explícito.
// ============================================================================

const ALCANCE_LABEL = {
  consolidado: 'consolidado',
  individual: 'del folio',
} as const

/** El 422 por tope se distingue por el detalle del servidor (habla de
 *  folios/hojas): la UI debe mencionar el tope de 100 folios por libro. */
function excedeTopeFolios(detalle?: string): boolean {
  return detalle !== undefined && /\b(folio|hoja)s?\b/i.test(detalle)
}

export default function ReporteActividadesExportFeedback({
  status,
}: {
  status: ReporteActividadesExportStatus
}) {
  if (status.estado === 'error') {
    let mensaje: string
    if (status.httpStatus === 404) {
      mensaje =
        'No hay actividades para los filtros seleccionados, así que no se generó el archivo. Ajusta la unidad o el rango de fechas e inténtalo de nuevo.'
    } else if (status.httpStatus === 422 && excedeTopeFolios(status.detalle)) {
      mensaje =
        'La consulta excede el tope de 100 folios por libro, así que no se generó el archivo. Ajusta la unidad, las fechas o la actividad e inténtalo de nuevo.'
    } else if (status.httpStatus === 422) {
      mensaje =
        'Los filtros no son válidos y no se generó el libro. Revisa las fechas e inténtalo de nuevo.'
    } else if (status.httpStatus === 401 || status.httpStatus === 403) {
      mensaje = 'No tienes permiso para exportar este reporte.'
    } else {
      mensaje =
        'No se pudo generar el libro. Inténtalo nuevamente; si el problema continúa, avisa a soporte.'
    }
    return (
      <div
        role="alert"
        className="mt-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">{mensaje}</p>
          {status.detalle && (
            <p className="mt-1 text-xs text-red-600">
              Detalle del servidor: {status.detalle}
            </p>
          )}
        </div>
      </div>
    )
  }

  // Región viva persistente: los cambios idle→loading→success se anuncian.
  return (
    <div role="status" aria-live="polite">
      {status.estado === 'loading' && (
        <p className="mt-3 flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Descargando el libro {ALCANCE_LABEL[status.alcance]}…
        </p>
      )}
      {status.estado === 'success' && (
        <p className="mt-3 flex items-center gap-2 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          Libro descargado: {status.nombreArchivo} (
          {ALCANCE_LABEL[status.alcance]}). Revisa la descarga de tu navegador.
        </p>
      )}
    </div>
  )
}
