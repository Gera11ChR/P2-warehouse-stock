import { useQuery } from '@tanstack/react-query'
import { listCategorias } from '../services/catalog'

/**
 * Query de categorías del catálogo. Clave COMPARTIDA ['categorias'] con
 * SeccionGeneral; se invalida al crear/renombrar/eliminar categorías.
 */
export function useCategorias() {
  return useQuery({ queryKey: ['categorias'], queryFn: listCategorias })
}
