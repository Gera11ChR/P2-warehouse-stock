import { useQuery } from '@tanstack/react-query'
import { listSeccionesTransferibles } from '../services/inventory'

/**
 * Query de secciones candidatas a transferencia
 * (contrato /api/v1/inventario/secciones/transferibles).
 * Clave anidada bajo ['secciones']: invalidar el prefijo 'secciones'
 * refresca también esta lista.
 */
export function useSeccionesTransferibles() {
  return useQuery({
    queryKey: ['secciones', 'transferibles'],
    queryFn: listSeccionesTransferibles,
  })
}
