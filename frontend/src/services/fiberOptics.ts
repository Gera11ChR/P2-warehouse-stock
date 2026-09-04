import api from './api'
import type { FiberVariant } from '../types'

export async function listFiberVariants(): Promise<FiberVariant[]> {
  const { data } = await api.get<{ items: FiberVariant[] }>('/fiber-optics')
  return data.items
}

export async function createFiberVariant(payload: {
  codigo: string
  variante: string
  metros_restantes: number
  cantidad: number
  almacen_id?: string | null
}): Promise<FiberVariant> {
  const { data } = await api.post<FiberVariant>('/fiber-optics', payload)
  return data
}
