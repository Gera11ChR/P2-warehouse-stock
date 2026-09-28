import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createUm, deleteUm, updateUm } from '../services/catalog'
import type { UmCreatePayload, UmUpdatePayload } from '../services/catalog'

/**
 * Mutaciones ADMIN de unidades de medida (crear / renombrar / eliminar).
 *
 * Las U.M. aparecen en filtros y columnas del catálogo y del stock, por
 * eso invalidan ['ums'], ['catalogo'] y ['stock'].
 *
 * RBAC visual: admin-only (403 `{error:{code,message,actor}}` para
 * no-admin); el hook NO traduce errores (error-agnostic).
 */
export function useUmAdmin() {
  const queryClient = useQueryClient()
  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['ums'] })
    queryClient.invalidateQueries({ queryKey: ['catalogo'] })
    queryClient.invalidateQueries({ queryKey: ['stock'] })
  }
  const crear = useMutation({
    mutationFn: (payload: UmCreatePayload) => createUm(payload),
    onSuccess: invalidar,
  })
  const renombrar = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UmUpdatePayload }) =>
      updateUm(id, payload),
    onSuccess: invalidar,
  })
  const eliminar = useMutation({
    mutationFn: deleteUm,
    onSuccess: invalidar,
  })
  return { crear, renombrar, eliminar }
}
