import { useMutation, useQueryClient } from '@tanstack/react-query'
import { crearDespliegue } from '../services/despliegues'
import type { DespliegueCreatePayload } from '../types'

/**
 * POST /equipos/{equipoId}/despliegues — apertura de despliegue (201).
 *
 * Regla de invalidación (State-Agent): tras HTTP success se invalidan
 * despliegues + inventario del equipo + reportes; React re-renderiza el
 * estado PERSISTIDO del backend. NUNCA se calcula stock en cliente.
 * Errores: el hook NO traduce (error-agnostic); la página los formatea.
 */
export function useCrearDespliegue(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: DespliegueCreatePayload) =>
      crearDespliegue(equipoId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['despliegues', equipoId] })
      queryClient.invalidateQueries({ queryKey: ['equipo', equipoId] })
      queryClient.invalidateQueries({ queryKey: ['reportes'] })
    },
  })
}
