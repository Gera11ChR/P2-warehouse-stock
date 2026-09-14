import api from './api'

export interface WarehouseOption {
  id: string
  name: string
  is_active: boolean
}

interface WarehouseListResponse {
  warehouses: Array<{
    warehouse_id: string
    name: string
    is_active: boolean
  }>
}

export async function listWarehouses(): Promise<WarehouseOption[]> {
  const { data } = await api.get<WarehouseListResponse>('/warehouses')
  return data.warehouses.map((w) => ({
    id: w.warehouse_id,
    name: w.name,
    is_active: w.is_active,
  }))
}
