import { useQuery } from '@tanstack/react-query'
import { listUms } from '../services/catalog'

/**
 * Query de unidades de medida (contrato /api/v1/catalogo/um).
 * Se invalida al crear/renombrar/eliminar U.M. (useUmAdmin).
 */
export function useUms() {
  return useQuery({ queryKey: ['ums'], queryFn: listUms })
}
