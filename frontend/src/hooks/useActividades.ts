import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  crearActividad,
  listarActividades,
  obtenerActividadPendiente,
} from '../services/actividades'
import type { ActividadCreatePayload } from '../types'
import { invalidarActividadesEquipo, queryKeys } from './queryKeys'

/**
 * GET /equipos/{equipoId}/actividades/pendiente — seguimiento CERRADA más
 * reciente sin actividad, con sus materiales consumidos y el valor unitario
 * vigente (RF-2). `seguimiento: null` sin pendiente (RF-3).
 *
 * `enabled` guard: no dispara hasta que haya Unidad seleccionada.
 * FAIL-CLOSED: 403/404 se exponen tal cual (isError/error); un error NUNCA
 * se reinterpreta como "sin pendiente".
 */
export function useActividadPendiente(equipoId: number | null) {
  return useQuery({
    queryKey: queryKeys.actividadPendiente(equipoId),
    queryFn: () => obtenerActividadPendiente(equipoId!),
    enabled: equipoId !== null,
  })
}

/** GET /equipos/{equipoId}/actividades — historial confirmado (RF-16). */
export function useActividades(equipoId: number | null) {
  return useQuery({
    queryKey: queryKeys.actividades(equipoId),
    queryFn: () => listarActividades(equipoId!),
    enabled: equipoId !== null,
  })
}

/**
 * POST /equipos/{equipoId}/actividades — confirmación (201). El folio y la
 * fecha los devuelve PostgreSQL en la respuesta.
 *
 * Regla de invalidación (State-Agent): tras HTTP success se invalidan
 * pendiente, historial y auditoría; React re-lee el estado persistido.
 * Errores: el hook NO traduce (error-agnostic); el panel los formatea.
 */
export function useCrearActividad(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ActividadCreatePayload) =>
      crearActividad(equipoId, payload),
    onSuccess: () => invalidarActividadesEquipo(queryClient, equipoId),
  })
}
