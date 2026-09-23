import api from './api'
import type { Equipo } from '../types'

// ============================================================================
// PAYLOADS — contrato real /api/v1/equipos
// ============================================================================

export interface EquipoCreatePayload {
  nombre: string
  descripcion?: string | null
  integrantes?: string[]
}

export interface EquipoUpdatePayload {
  nombre?: string | null
  descripcion?: string | null
  integrantes?: string[] | null
  is_active?: boolean
}

// ============================================================================
// CRUD DE EQUIPOS
// ============================================================================

export async function listEquipos(): Promise<Equipo[]> {
  const { data } = await api.get<Equipo[]>('/equipos')
  return data
}

export async function getEquipo(equipo_id: number): Promise<Equipo> {
  const { data } = await api.get<Equipo>(`/equipos/${equipo_id}`)
  return data
}

export async function createEquipo(
  payload: EquipoCreatePayload,
): Promise<Equipo> {
  const { data } = await api.post<Equipo>('/equipos', payload)
  return data
}

export async function updateEquipo(
  equipo_id: number,
  payload: EquipoUpdatePayload,
): Promise<Equipo> {
  const { data } = await api.patch<Equipo>(`/equipos/${equipo_id}`, payload)
  return data
}

export async function deleteEquipo(equipo_id: number): Promise<void> {
  await api.delete(`/equipos/${equipo_id}`)
}
