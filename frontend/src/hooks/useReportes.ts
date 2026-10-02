import { useCallback, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  descargarActaXlsx,
  ErrorDescargaReporte,
  listarActas,
} from '../services/reportes'
import { guardarBlob } from '../utils/descargaArchivo'
import type { ReporteExportStatus, ReporteTipo } from '../utils/reporteExport'
import type { FormatoXlsx, ReporteParams } from '../types'
import { queryKeys } from './queryKeys'

// ============================================================================
// REPORTES — actas de Entrega y Consumo (REQ-P2-REP-005/008)
//
// useReporteActas  → GET /reportes/{entrega|consumo}?formato=json (tabla).
// useExportarReporte → GET .../?formato=normal|extenso (XLSX como Blob) con el
//                      estado `ReporteExportStatus` que consume la UI.
// El frontend no agrega ni recalcula nada: renderiza las actas del servidor.
// ============================================================================

/**
 * Listado de actas (json). Clave ['reportes','actas', tipo, params]: cambiar
 * filtros refetcha; invalidar ['reportes','actas', tipo] (p. ej. tras
 * confirmar TEAMS o cerrar un seguimiento) lo recarga.
 * FAIL-CLOSED: errores se exponen tal cual (isError/error).
 */
export function useReporteActas(tipo: ReporteTipo, params: ReporteParams) {
  return useQuery({
    queryKey: queryKeys.actas(tipo, params),
    queryFn: () => listarActas(tipo, params),
  })
}

/**
 * Exportación XLSX de un tipo de acta. `exportar(formato, params)` descarga
 * el Blob, lo entrega al navegador con el nombre de Content-Disposition
 * (saneado, con fallback) y libera el object URL.
 *
 * Estado (`status`): idle → loading → success | error. En error conserva
 * `httpStatus` (404 sin actas, 422 filtros inválidos, 403 equipo ajeno…) y
 * el `detalle` del backend. `reiniciar()` vuelve a idle (p. ej. al cambiar
 * filtros, para no mostrar un resultado de otros filtros).
 */
export function useExportarReporte(tipo: ReporteTipo) {
  const [status, setStatus] = useState<ReporteExportStatus>({ estado: 'idle' })

  const mutation = useMutation({
    mutationFn: ({
      formato,
      params,
    }: {
      formato: FormatoXlsx
      params: ReporteParams
    }) => descargarActaXlsx(tipo, formato, params),
    onMutate: ({ formato }) => setStatus({ estado: 'loading', formato }),
    onSuccess: ({ blob, nombreArchivo }, { formato }) => {
      guardarBlob(blob, nombreArchivo)
      setStatus({ estado: 'success', formato, nombreArchivo })
    },
    onError: (error, { formato }) => {
      setStatus({
        estado: 'error',
        formato,
        httpStatus:
          error instanceof ErrorDescargaReporte ? error.httpStatus : undefined,
        detalle:
          error instanceof ErrorDescargaReporte ? error.detalle : undefined,
      })
    },
  })

  const { mutate, isPending } = mutation
  const exportar = useCallback(
    (formato: FormatoXlsx, params: ReporteParams) => {
      mutate({ formato, params })
    },
    [mutate],
  )
  // No se reinicia mientras hay una descarga en curso (evita reactivar los
  // botones y lanzar una segunda descarga simultánea).
  const reiniciar = useCallback(() => {
    if (!isPending) setStatus({ estado: 'idle' })
  }, [isPending])

  return { status, exportar, reiniciar, isPending }
}
