import { useQuery } from '@tanstack/react-query'
import { reporteDesplieguesJson } from '../services/reportes'
import type { ReporteParams } from '../types'

/**
 * Query del reporte de despliegues en JSON (clave ['reportes', params]).
 * TanStack serializa el objeto `params` como parte de la clave: cambiar
 * filtros (equipo/rango/formato) refetcha.
 *
 * FAIL-CLOSED: errores se exponen tal cual (isError/error).
 */
export function useReporteDespliegues(params: ReporteParams) {
  return useQuery({
    queryKey: ['reportes', params],
    queryFn: () => reporteDesplieguesJson(params),
  })
}
