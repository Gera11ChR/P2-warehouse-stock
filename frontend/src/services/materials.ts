import api from './api'
import type { Material } from '../types'

export interface MaterialPayload {
  codigo?: string
  descripcion?: string | null
  um?: string | null
  stock_minimo?: number | null
  categoria?: string | null
  tipo?: string
}

export async function listMaterials(params?: {
  buscar?: string
  tipo?: string
}): Promise<Material[]> {
  const { data } = await api.get<{ materiales: Material[] }>('/materials', {
    params,
  })
  return data.materiales
}

export async function getMaterial(codigo: string): Promise<Material> {
  const { data } = await api.get<Material>(`/materials/${codigo}`)
  return data
}

export async function createMaterial(payload: MaterialPayload): Promise<Material> {
  const { data } = await api.post<Material>('/materials', payload)
  return data
}

export async function updateMaterial(
  codigo: string,
  payload: MaterialPayload,
): Promise<Material> {
  const { data } = await api.patch<Material>(`/materials/${codigo}`, payload)
  return data
}

export async function deleteMaterial(codigo: string): Promise<void> {
  await api.delete(`/materials/${codigo}`)
}
