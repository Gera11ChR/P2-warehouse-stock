import api from './api'
import type {
  DetalleMovimiento,
  EstadoMovimiento,
  Movimiento,
  TipoMovimiento,
} from '../types'

// ============================================================================
// PAYLOADS — contrato real /api/v1/movimientos
// ============================================================================

export interface MovimientoBorradorCreatePayload {
  tipo_movimiento: TipoMovimiento
  origen_almacen_id?: number | null
  destino_almacen_id?: number | null
  origen_equipo_id?: number | null
  destino_equipo_id?: number | null
  observaciones?: string | null
  detalle: DetalleMovimiento[]
}

// ============================================================================
// CRUD DE MOVIMIENTOS (BORRADOR → PROCESAR)
// ============================================================================

export async function listMovimientos(params?: {
  estado?: EstadoMovimiento
  tipo_movimiento?: TipoMovimiento
}): Promise<Movimiento[]> {
  const { data } = await api.get<{ movimientos: Movimiento[] }>('/movimientos', {
    params,
  })
  return data.movimientos
}

export async function getMovimiento(movimiento_id: number): Promise<Movimiento> {
  const { data } = await api.get<Movimiento>(`/movimientos/${movimiento_id}`)
  return data
}

export async function crearBorrador(
  payload: MovimientoBorradorCreatePayload,
): Promise<Movimiento> {
  const { data } = await api.post<Movimiento>('/movimientos', payload)
  return data
}

export async function eliminarBorrador(movimiento_id: number): Promise<void> {
  await api.delete(`/movimientos/${movimiento_id}`)
}

export async function procesarMovimiento(movimiento_id: number): Promise<void> {
  await api.post('/movimientos/procesar', { movimiento_id })
}

export interface CanceladoOut {
  movimiento_id: number
  estado: 'CANCELADO'
}

export async function cancelarMovimiento(
  movimiento_id: number,
  motivo?: string | null,
): Promise<CanceladoOut> {
  const { data } = await api.post<CanceladoOut>(
    `/movimientos/${movimiento_id}/cancelar`,
    { motivo: motivo ?? null },
  )
  return data
}
