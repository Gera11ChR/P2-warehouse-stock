import api from './api'
import type { InventoryRow } from '../types'

export interface InventoryFilters {
  buscar?: string
  categoria?: string
  um?: string
  almacen?: string
  desde_sku?: string
  hasta_sku?: string
}

export async function listInventory(
  filters?: InventoryFilters,
): Promise<InventoryRow[]> {
  const { data } = await api.get<{ items: InventoryRow[] }>('/inventory', {
    params: filters,
  })
  return data.items
}
