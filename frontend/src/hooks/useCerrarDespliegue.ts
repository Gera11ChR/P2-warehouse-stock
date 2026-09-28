import { useMutation, useQueryClient } from '@tanstack/react-query'
import { cerrarDespliegue } from '../services/despliegues'
import type { CerrarDesplieguePayload } from '../types'

/**
 * POST /equipos/{equipoId}/despliegues/{despliegueId}/cerrar — cierre con
 * sobrantes. El backend calcula consumos y reintegra sobrantes en
 * PostgreSQL; tras success se invalidan despliegues + inventario del equipo
 * + reportes (React re-renderiza estado PERSISTIDO, nunca stock local).
 * Errores: el hook NO traduce (error-agnostic).
 */
export function useCerrarDespliegue(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      despliegueId,
      payload,
    }: {
      despliegueId: number
      payload: CerrarDesplieguePayload
    }) => cerrarDespliegue(equipoId, despliegueId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['despliegues', equipoId] })
      queryClient.invalidateQueries({ queryKey: ['equipo', equipoId] })
      queryClient.invalidateQueries({ queryKey: ['reportes'] })
    },
  })
}
