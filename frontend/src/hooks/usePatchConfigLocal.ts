import { useMutation, useQueryClient } from '@tanstack/react-query'
import { patchInventarioLocal } from '../services/equipos'
import type { EquipoConfigLocalPayload } from '../types'

/**
 * PATCH /equipos/{equipoId}/inventario/{materialId} — configuración local
 * del inventario del equipo. Tras success se invalidan el inventario del
 * equipo y los reportes; el eco del contrato (EquipoConfigLocal) es la
 * ÚNICA fuente del estado persistido.
 * Errores: el hook NO traduce (error-agnostic).
 */
export function usePatchConfigLocal(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      materialId,
      payload,
    }: {
      materialId: number
      payload: EquipoConfigLocalPayload
    }) => patchInventarioLocal(equipoId, materialId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipo', equipoId] })
      queryClient.invalidateQueries({ queryKey: ['reportes'] })
    },
  })
}
