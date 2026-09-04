import api from './api'
import type { Transfer } from '../types'

export async function listTransfers(): Promise<Transfer[]> {
  const { data } = await api.get<{ transfers: Transfer[] }>('/stock-transfers')
  return data.transfers
}

export async function createTransfer(payload: {
  source: string
  destination: string
  sku: string
  quantity: number
}): Promise<Transfer> {
  const { data } = await api.post<Transfer>(
    '/stock-transfers',
    {
      source_warehouse_id: payload.source,
      destination_warehouse_id: payload.destination,
      lines: [{ sku: payload.sku, quantity: payload.quantity }],
    },
    { headers: { 'Idempotency-Key': crypto.randomUUID() } },
  )
  return data
}
