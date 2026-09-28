import { useQuery } from '@tanstack/react-query'
import { inventarioEquipo } from '../services/equipos'

/**
 * Inventario autónomo de un equipo (clave ['equipo', equipoId]).
 * `enabled` guard: no dispara hasta que haya equipo seleccionado.
 *
 * FAIL-CLOSED: un error de API se expone tal cual (isError/error);
 * NUNCA se reinterpreta como inventario vacío ni stock = 0.
 */
export function useEquipoInventario(equipoId: number | null) {
  return useQuery({
    queryKey: ['equipo', equipoId],
    queryFn: () => inventarioEquipo(equipoId!),
    enabled: equipoId !== null,
  })
}
