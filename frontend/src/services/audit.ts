import api from './api'
import type { AuditLogItem } from '../types'

export async function listAudit(limit = 200): Promise<AuditLogItem[]> {
  const { data } = await api.get<{ items: AuditLogItem[] }>('/audit', {
    params: { limit },
  })
  return data.items
}
