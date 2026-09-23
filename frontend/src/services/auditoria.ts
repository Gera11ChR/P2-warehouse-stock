import api from './api'
import type { EventoAuditoria } from '../types'

// ============================================================================
// AUDITORÍA — contrato real GET /api/v1/auditoria (ledger append-only)
// ============================================================================

export interface ListEventosParams {
  material_id?: number
  tipo_accion?: string
  usuario?: string
  limit?: number
}

export async function listEventos(
  params?: ListEventosParams,
): Promise<EventoAuditoria[]> {
  const { data } = await api.get<{ eventos: EventoAuditoria[] }>('/auditoria', {
    params,
  })
  return data.eventos
}
