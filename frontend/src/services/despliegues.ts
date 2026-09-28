import api from './api'
import type {
  CerrarDesplieguePayload,
  Despliegue,
  DespliegueCreatePayload,
  DespliegueList,
} from '../types'

// ============================================================================
// DESPLIEGUES DE EQUIPO — contrato real
// /api/v1/equipos/{equipo_id}/despliegues
//
// Ciclo de vida: ABIERTA (apertura, 201) → CERRADA (cierre con sobrantes).
// El backend calcula `cantidad_consumida` (tomada − sobrante) y reintegra
// los sobrantes al inventario del equipo en PostgreSQL; el frontend NUNCA
// calcula ni escribe stock.
//
// FAIL-CLOSED: un error de API (404/409/422) se muestra como error —
// NUNCA se reinterpreta como "sin despliegues" ni como stock = 0.
// ============================================================================

/** GET /equipos/{equipo_id}/despliegues — lista de despliegues del equipo. */
export async function listDespliegues(equipoId: number): Promise<Despliegue[]> {
  const { data } = await api.get<DespliegueList>(
    `/equipos/${equipoId}/despliegues`,
  )
  return data.despliegues
}

/** GET /equipos/{equipo_id}/despliegues/{despliegue_id} — detalle. */
export async function getDespliegue(
  equipoId: number,
  despliegueId: number,
): Promise<Despliegue> {
  const { data } = await api.get<Despliegue>(
    `/equipos/${equipoId}/despliegues/${despliegueId}`,
  )
  return data
}

/** POST /equipos/{equipo_id}/despliegues — apertura (201). */
export async function crearDespliegue(
  equipoId: number,
  payload: DespliegueCreatePayload,
): Promise<Despliegue> {
  const { data } = await api.post<Despliegue>(
    `/equipos/${equipoId}/despliegues`,
    payload,
  )
  return data
}

/** POST /equipos/{equipo_id}/despliegues/{despliegue_id}/cerrar — cierre.
 *  `sobrantes` solo requiere los materiales con devolución; los omitidos
 *  se consideran consumidos al 100 % (resolución backend). */
export async function cerrarDespliegue(
  equipoId: number,
  despliegueId: number,
  payload: CerrarDesplieguePayload,
): Promise<Despliegue> {
  const { data } = await api.post<Despliegue>(
    `/equipos/${equipoId}/despliegues/${despliegueId}/cerrar`,
    payload,
  )
  return data
}
