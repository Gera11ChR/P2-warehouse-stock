import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sumarCantidad } from '../services/inventory'
import type { SumarCantidadPayload } from '../utils/operadorPayload'
import { invalidarTrasSumar } from './queryKeys'

/**
 * POST /inventario/sumar-cantidad (REQ-P2-INV-001/007).
 *
 * El stock resultante es el `stock_nuevo` de la RESPUESTA (fuente de verdad);
 * el cliente no suma. Tras CADA intento (éxito o rechazo: el stock pudo cambiar o la pantalla
 * estar desactualizada) se invalidan los stocks del inventario
 * destino (General → ['stock'], FO → ['fibra', módulo]) y auditoría.
 * Errores: error-agnostic; se traducen con `traducirErrorOperador`.
 */
export function useSumarCantidad() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SumarCantidadPayload) => sumarCantidad(payload),
    onSettled: (_data, _error, payload) => invalidarTrasSumar(queryClient, payload),
  })
}
