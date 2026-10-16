import { useQuery } from '@tanstack/react-query'
import { getResumenGeneral } from '../services/inventory'
import { queryKeys } from './queryKeys'

/**
 * Valor Total del inventario (RF-4/RF-5; contrato GET
 * /api/v1/inventario/resumen-general). El valor es el persistido por
 * PostgreSQL: sin caché de larga duración ni cálculo en el cliente. Toda
 * mutación que cambie existencias o Valor Unitario invalida esta clave
 * (`invalidarResumenGeneral` en queryKeys.ts).
 */
export function useResumenGeneral() {
  return useQuery({
    queryKey: queryKeys.resumenGeneral(),
    queryFn: getResumenGeneral,
    staleTime: 0,
    // Sin reintentos automáticos: el error debe verse (estado explícito).
    retry: false,
  })
}
