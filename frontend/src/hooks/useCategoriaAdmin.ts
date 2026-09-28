import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteCategoria, updateCategoria } from '../services/catalog'
import type { CategoriaUpdatePayload } from '../services/catalog'

/**
 * Mutaciones ADMIN de categorías (renombrar / eliminar).
 *
 * Las categorías se muestran en filtros del catálogo y en el stock, por
 * eso invalidan ['categorias'], ['catalogo'] y ['stock'].
 *
 * RBAC visual: las mutaciones son admin-only (403 `{error:{code,message,
 * actor}}` para no-admin); el hook NO traduce errores — la página decide
 * qué mostrar (error-agnostic).
 */
export function useCategoriaAdmin() {
  const queryClient = useQueryClient()
  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['categorias'] })
    queryClient.invalidateQueries({ queryKey: ['catalogo'] })
    queryClient.invalidateQueries({ queryKey: ['stock'] })
  }
  const renombrar = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number
      payload: CategoriaUpdatePayload
    }) => updateCategoria(id, payload),
    onSuccess: invalidar,
  })
  const eliminar = useMutation({
    mutationFn: deleteCategoria,
    onSuccess: invalidar,
  })
  return { renombrar, eliminar }
}
