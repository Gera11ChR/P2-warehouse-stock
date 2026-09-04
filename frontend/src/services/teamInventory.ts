import api from './api'
import type { TeamInventoryItem } from '../types'

export async function listTeamInventory(): Promise<TeamInventoryItem[]> {
  const { data } = await api.get<{ items: TeamInventoryItem[] }>('/team-inventory')
  return data.items
}

export async function createTeamInventory(payload: {
  equipo: string
  usuario: string
  codigo: string
  cantidad: number
}): Promise<TeamInventoryItem> {
  const { data } = await api.post<TeamInventoryItem>('/team-inventory', payload)
  return data
}

export async function updateTeamInventory(
  id: number,
  payload: { equipo?: string; usuario?: string; cantidad?: number },
): Promise<TeamInventoryItem> {
  const { data } = await api.patch<TeamInventoryItem>(
    `/team-inventory/${id}`,
    payload,
  )
  return data
}

export async function deleteTeamInventory(id: number): Promise<void> {
  await api.delete(`/team-inventory/${id}`)
}
