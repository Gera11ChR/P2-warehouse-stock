import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import {
  FORMATO_LABEL,
  TIPO_LABEL,
  mensajeErrorExportacion,
} from '../utils/reporteExport'
import type { ReporteExportStatus, ReporteTipo } from '../utils/reporteExport'

// ============================================================================
// FEEDBACK DE EXPORTACIÓN XLSX — presentacional (REQ-P2-REP-005/008)
//
// Máquina de estados de PRESENTACIÓN de una exportación:
//   idle → loading → success | error   (error/success → loading al reintentar)
// La capa de estado (T4.4 @state-agent) produce el `ReporteExportStatus`
// a partir de la respuesta real; este componente solo lo traduce a copy
// operativo y a anuncios accesibles. No hace red ni decide validez.
//
// El backend responde 404 cuando no existen actas para los filtros
// (equipo/fechas): aquí se traduce a un mensaje accionable, nunca silencio.
// ============================================================================

export default function ReporteExportFeedback({
  tipo,
  status,
}: {
  tipo: ReporteTipo
  status: ReporteExportStatus
}) {
  const acta = `Acta de ${TIPO_LABEL[tipo]}`

  if (status.estado === 'error') {
    return (
      <div
        role="alert"
        className="mt-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">
            {mensajeErrorExportacion(tipo, status.httpStatus)}
          </p>
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
          Generando {acta} en formato {FORMATO_LABEL[status.formato]}…
        </p>
      )}
      {status.estado === 'success' && (
        <p className="mt-3 flex items-center gap-2 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
          {status.nombreArchivo
            ? `Archivo generado: ${status.nombreArchivo}.`
            : `${acta} (formato ${FORMATO_LABEL[status.formato]}) generada.`}{' '}
          Revisa la descarga de tu navegador.
        </p>
      )}
    </div>
  )
}
