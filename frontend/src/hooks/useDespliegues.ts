import { useQuery } from '@tanstack/react-query'
import { listDespliegues } from '../services/despliegues'

/**
 * Despliegues de un equipo (clave ['despliegues', equipoId]) + conveniencia
 * `abierta`: el despliegue en estado ABIERTA vigente (el backend garantiza
 * a lo sumo UNA abierta por equipo) o `null`.
 *
 * `enabled` guard: no dispara hasta que haya equipo seleccionado.
 * FAIL-CLOSED: errores se exponen tal cual (isError/error).
 */
export function useDespliegues(equipoId: number | null) {
  const query = useQuery({
    queryKey: ['despliegues', equipoId],
    queryFn: () => listDespliegues(equipoId!),
    enabled: equipoId !== null,
  })
  const abierta = query.data?.find((d) => d.estado === 'ABIERTA') ?? null
  return { ...query, abierta }
}
