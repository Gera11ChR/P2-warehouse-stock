import api from './api'
import type {
  Actividad,
  ActividadCreatePayload,
  ActividadList,
  ActividadPendiente,
} from '../types'

// ============================================================================
// ACTIVIDADES DE LA UNIDAD — contrato congelado T7 (openapi.snapshot.json)
// /api/v1/equipos/{equipo_id}/actividades   (paquete 2026-10-actividades-unidad)
//
// Folio (R0001…), fecha, materiales y valor unitario los asigna/congela
// PostgreSQL; el frontend solo transporta el payload validado y re-lee el
// estado persistido. FAIL-CLOSED: 404/409/422 se propagan como error.
// ============================================================================

/** GET /equipos/{equipo_id}/actividades/pendiente — seguimiento CERRADA más
 *  reciente sin actividad, con sus materiales consumidos y el valor unitario
 *  vigente. `seguimiento: null` si no hay (RF-3). */
export async function obtenerActividadPendiente(
  equipoId: number,
): Promise<ActividadPendiente> {
  const { data } = await api.get<ActividadPendiente>(
    `/equipos/${equipoId}/actividades/pendiente`,
  )
  return data
}

/** POST /equipos/{equipo_id}/actividades — confirmación (201). El backend
 *  rechaza 404 (seguimiento inexistente para la Unidad), 409 (no cerrado o
 *  duplicado) y 422 (payload inválido). */
export async function crearActividad(
  equipoId: number,
  payload: ActividadCreatePayload,
): Promise<Actividad> {
  const { data } = await api.post<Actividad>(
    `/equipos/${equipoId}/actividades`,
    payload,
  )
  return data
}

/** GET /equipos/{equipo_id}/actividades — historial confirmado, más reciente
 *  primero (RF-16). */
export async function listarActividades(
  equipoId: number,
): Promise<ActividadList> {
  const { data } = await api.get<ActividadList>(
    `/equipos/${equipoId}/actividades`,
  )
  return data
}
