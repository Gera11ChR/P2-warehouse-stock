import api from './api'
import type {
  ReferenciaCreatePayload,
  ReferenciaLinea,
  ReferenciaList,
  ReferenciaUpdatePayload,
} from '../types'

// ============================================================================
// REFERENCIA DE MATERIALES POR UNIDAD — contrato CONGELADO en T7
// (openapi.snapshot.json, sha256
// 93eb4b0050b75892a6ca8c55c78e483458517d3d87f9c1a7a64abd7d0b966259;
// paquete 2026-10-referencia-materiales-unidades)
//
//   GET    /api/v1/equipos/{equipo_id}/referencia               → 200 ReferenciaListOut {items, total}
//   POST   /api/v1/equipos/{equipo_id}/referencia               → 201 ReferenciaListOut (1..50 líneas, todo o nada)
//   PATCH  /api/v1/equipos/{equipo_id}/referencia/{material_id} → 200 ReferenciaLineaOut (solo cantidad_semanal)
//   DELETE /api/v1/equipos/{equipo_id}/referencia/{material_id} → 204
//
// Errores (REQ-REF-015): 400 (ruta fuera de INT4), 403 (autorización por
// Unidad; escrituras además con la regla de Configuración), 404 (Unidad
// inexistente o inactiva; MATERIAL_NO_ENCONTRADO en el alta;
// REFERENCIA_NO_ENCONTRADA en PATCH/DELETE), 409 (REFERENCIA_DUPLICADA),
// 422 (validación {detail:[…]} o regla de negocio
// {error:{code,message,coordinates}}). La Referencia es SOLO visual: jamás
// escribe inventarios ni catálogo (REQ-REF-011).
//
// Errores: se propagan TAL CUAL (patrón dominante del repo); los traduce
// `mensajeErrorApi` en los hooks (useReferencia.ts). FAIL-CLOSED: un error
// de lectura jamás se reinterpreta como Referencia vacía (REQ-REF-005).
// ============================================================================

/** GET /equipos/{equipoId}/referencia — líneas de la Unidad (REQ-REF-005).
 *  El backend las entrega ordenadas (descripcion, material_id) con la U.M.
 *  efectiva; el frontend NO agrega ni recalcula nada. */
export async function listarReferencia(
  equipoId: number,
): Promise<ReferenciaLinea[]> {
  const { data } = await api.get<ReferenciaList>(
    `/equipos/${equipoId}/referencia`,
  )
  return data.items
}

/** POST /equipos/{equipoId}/referencia — alta masiva todo-o-nada (201).
 *  `payload.lineas`: 1..50 líneas; el backend valida todo antes de insertar.
 *  Responde con las líneas creadas y `total` = creadas. */
export async function crearReferencia(
  equipoId: number,
  payload: ReferenciaCreatePayload,
): Promise<ReferenciaList> {
  const { data } = await api.post<ReferenciaList>(
    `/equipos/${equipoId}/referencia`,
    payload,
  )
  return data
}

/** PATCH /equipos/{equipoId}/referencia/{materialId} — cambia SOLO la
 *  Cantidad Semanal de la línea (200). Con la misma cantidad es un no-op
 *  idempotente. */
export async function modificarReferencia(
  equipoId: number,
  materialId: number,
  payload: ReferenciaUpdatePayload,
): Promise<ReferenciaLinea> {
  const { data } = await api.patch<ReferenciaLinea>(
    `/equipos/${equipoId}/referencia/${materialId}`,
    payload,
  )
  return data
}

/** DELETE /equipos/{equipoId}/referencia/{materialId} — borrado físico de la
 *  línea (204, sin cuerpo); el trigger de auditoría conserva los valores
 *  previos (REQ-REF-009). */
export async function eliminarReferencia(
  equipoId: number,
  materialId: number,
): Promise<void> {
  await api.delete(`/equipos/${equipoId}/referencia/${materialId}`)
}
