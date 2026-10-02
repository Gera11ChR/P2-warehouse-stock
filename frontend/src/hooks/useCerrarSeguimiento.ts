import { useMutation, useQueryClient } from '@tanstack/react-query'
import { cerrarSeguimiento } from '../services/seguimientos'
import type { CerrarSeguimientoPayload } from '../types'
import {
  invalidarActas,
  invalidarAuditoria,
  invalidarSeguimientoEquipo,
} from './queryKeys'

/**
 * POST /equipos/{equipoId}/seguimientos/{seguimientoId}/cerrar — cierre con
 * sobrantes. El backend calcula consumos, reintegra sobrantes y registra el
 * Acta de Consumo en PostgreSQL (misma transacción). Tras success se
 * invalidan: seguimientos del equipo, inventario del equipo, actas de CONSUMO
 * (Reportes > Consumo) y auditoría; React re-renderiza estado PERSISTIDO,
 * nunca stock local. El aviso «Acta de Consumo generada» lo dispara el
 * `onSuccess` del consumidor (SeguimientoPanel).
 * Errores: el hook NO traduce (error-agnostic).
 */
export function useCerrarSeguimiento(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      seguimientoId,
      payload,
    }: {
      seguimientoId: number
      payload: CerrarSeguimientoPayload
    }) => cerrarSeguimiento(equipoId, seguimientoId, payload),
    onSuccess: () =>
      Promise.all([
        invalidarSeguimientoEquipo(queryClient, equipoId),
        invalidarActas(queryClient, 'consumo'),
        invalidarAuditoria(queryClient),
      ]),
  })
}
