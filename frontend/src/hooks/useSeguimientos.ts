import { useQuery } from '@tanstack/react-query'
import { getSeguimiento, listSeguimientos } from '../services/seguimientos'
import { queryKeys } from './queryKeys'

/**
 * Seguimientos de un equipo (clave ['seguimientos', equipoId]) + conveniencia
 * `abierta`: el seguimiento en estado ABIERTA vigente (el backend garantiza a
 * lo sumo UNO abierto por equipo) o `null`.
 *
 * `enabled` guard: no dispara hasta que haya equipo seleccionado.
 * FAIL-CLOSED: errores se exponen tal cual (isError/error).
 */
export function useSeguimientos(equipoId: number | null) {
  const query = useQuery({
    queryKey: queryKeys.seguimientos(equipoId),
    queryFn: () => listSeguimientos(equipoId!),
    enabled: equipoId !== null,
  })
  const abierta = query.data?.find((s) => s.estado === 'ABIERTA') ?? null
  return { ...query, abierta }
}

/**
 * Detalle de un seguimiento (GET .../seguimientos/{id}); clave anidada bajo
 * ['seguimientos', equipoId], por lo que cualquier invalidación del equipo lo
 * recarga. Sin pantalla consumidora todavía: disponible para edición/consulta
 * de un seguimiento concreto.
 */
export function useSeguimiento(
  equipoId: number | null,
  seguimientoId: number | null,
) {
  return useQuery({
    queryKey: queryKeys.seguimiento(equipoId, seguimientoId),
    queryFn: () => getSeguimiento(equipoId!, seguimientoId!),
    enabled: equipoId !== null && seguimientoId !== null,
  })
}
