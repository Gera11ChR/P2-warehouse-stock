import api from './api'
import type {
  Equipo,
  EquipoConfigLocal,
  EquipoConfigLocalPayload,
  InventarioEquipoRow,
} from '../types'

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

// ============================================================================
// INVENTARIO AUTÓNOMO DEL EQUIPO (REQ-DOMAIN-001/002)
// ============================================================================

/**
 * GET /equipos/{equipo_id}/inventario — contrato canónico del inventario
 * autónomo (InventarioEquipoOut). Reemplaza al sparse deprecado.
 *
 * Solo filas físicas con stock real (stock_actual > 0) originadas en
 * movimientos TEAMS/DEVOL auditados; cero fantasmas. Un equipo nuevo
 * devuelve [] (200). 404 SOLO si el equipo no existe.
 *
 * FAIL-CLOSED: un error de API (404/500) se muestra como error —
 * NUNCA se reinterpreta como inventario vacío ni stock = 0.
 */
export async function inventarioEquipo(
  equipo_id: number,
): Promise<InventarioEquipoRow[]> {
  const { data } = await api.get<InventarioEquipoRow[]>(
    `/equipos/${equipo_id}/inventario`,
  )
  return data
}

// ============================================================================
// CONFIGURACIÓN LOCAL DEL INVENTARIO DE EQUIPO (FASE 7)
// ============================================================================

/**
 * PATCH /equipos/{equipo_id}/inventario/{material_id} — configuración local
 * (stock mínimo local / categoría local / U.M. local). Requiere AL MENOS un
 * campo (422 si vacío). Los campos omitidos conservan su valor previo; la
 * resolución de valores EFECTIVOS (local o heredado del catálogo) es del
 * backend. El frontend solo refleja el eco del contrato.
 */
export async function patchInventarioLocal(
  equipo_id: number,
  material_id: number,
  payload: EquipoConfigLocalPayload,
): Promise<EquipoConfigLocal> {
  const { data } = await api.patch<EquipoConfigLocal>(
    `/equipos/${equipo_id}/inventario/${material_id}`,
    payload,
  )
  return data
}
