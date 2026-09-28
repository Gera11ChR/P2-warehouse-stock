import api from './api'
import type {
  ReporteDespliegue,
  ReporteDespliegueList,
  ReporteParams,
} from '../types'

// ============================================================================
// REPORTES — contrato real GET /api/v1/reportes/despliegues
//
// `format=json` devuelve {despliegues: [...]}; `format=csv` devuelve un
// blob text/csv descargable. El frontend NO agrega ni transforma datos:
// consume el reporte tal como lo sirve el backend.
// ============================================================================

/** GET /reportes/despliegues?format=json — despliegues reportables. */
export async function reporteDesplieguesJson(
  params: ReporteParams,
): Promise<ReporteDespliegue[]> {
  const { data } = await api.get<ReporteDespliegueList>(
    '/reportes/despliegues',
    {
      params: { ...params, format: 'json' },
    },
  )
  return data.despliegues
}

/** GET /reportes/despliegues?format=csv — descarga CSV del lado cliente
 *  (Blob + URL.createObjectURL + ancla temporal; el URL se revoca al
 *  terminar). */
export async function descargarReporteCsv(
  params: ReporteParams,
): Promise<void> {
  const response = await api.get('/reportes/despliegues', {
    params: { ...params, format: 'csv' },
    responseType: 'blob',
  })
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const hoy = new Date().toISOString().slice(0, 10)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `reporte-despliegues-${hoy}.csv`
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  URL.revokeObjectURL(url)
}
