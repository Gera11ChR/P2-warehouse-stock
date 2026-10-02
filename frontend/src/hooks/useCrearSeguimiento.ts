import { useMutation, useQueryClient } from '@tanstack/react-query'
import { crearSeguimiento } from '../services/seguimientos'
import type { SeguimientoCreatePayload } from '../types'
import { invalidarAuditoria, invalidarSeguimientoEquipo } from './queryKeys'

/**
 * POST /equipos/{equipoId}/seguimientos — apertura de seguimiento (201).
 *
 * Regla de invalidación (State-Agent): tras HTTP success se invalidan los
 * seguimientos del equipo + su inventario + auditoría; React re-renderiza el
 * estado PERSISTIDO del backend. NUNCA se calcula stock en cliente. (La
 * apertura no genera acta: el Acta de Consumo nace al CERRAR.)
 * Errores: el hook NO traduce (error-agnostic); la página los formatea.
 */
export function useCrearSeguimiento(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SeguimientoCreatePayload) =>
      crearSeguimiento(equipoId, payload),
    onSuccess: () =>
      Promise.all([
        invalidarSeguimientoEquipo(queryClient, equipoId),
        invalidarAuditoria(queryClient),
      ]),
  })
}
