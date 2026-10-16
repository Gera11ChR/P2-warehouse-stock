import { useMutation, useQueryClient } from '@tanstack/react-query'
import { moverMaterial } from '../services/inventory'
import type { MoverMaterialPayload } from '../utils/operadorPayload'
import { invalidarTrasMover } from './queryKeys'

/**
 * POST /inventario/mover (REQ-P2-INV-003/004/007).
 *
 * Los stocks resultantes son `stock_origen` / `stock_destino` de la RESPUESTA
 * (fuente de verdad). Tras CADA intento (éxito o rechazo: el stock pudo cambiar o la pantalla
 * estar desactualizada) se invalidan los stocks de AMBOS extremos
 * (General → ['stock'], FO → ['fibra']), Valor Total (['inventario', 'resumen-general']) y auditoría.
 * Errores: error-agnostic; se traducen con `traducirErrorOperador`.
 */
export function useMoverMaterial() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: MoverMaterialPayload) => moverMaterial(payload),
    onSettled: (_data, _error, payload) => invalidarTrasMover(queryClient, payload),
  })
}
