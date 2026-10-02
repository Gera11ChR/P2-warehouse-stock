import api from './api'
import type {
  AgregarTodoPayload,
  AgregarTodoResultadoOut,
  CerrarSeguimientoPayload,
  Seguimiento,
  SeguimientoCreatePayload,
  SeguimientoList,
} from '../types'

// ============================================================================
// SEGUIMIENTOS DE CONSUMO DE EQUIPO — contrato certificado
// /api/v1/equipos/{equipo_id}/seguimientos   (openspec.yaml, sin alias legacy)
//
// Ciclo de vida: ABIERTA (apertura, 201) → CERRADA (cierre con sobrantes).
// El backend calcula `cantidad_consumida` (tomada − sobrante), reintegra los
// sobrantes al inventario del equipo y registra el Acta de Consumo en la misma
// transacción PostgreSQL; el frontend NUNCA calcula ni escribe stock.
//
// FAIL-CLOSED: un error de API (404/409/422) se propaga como error —
// NUNCA se reinterpreta como "sin seguimientos" ni como stock = 0.
// ============================================================================

/** GET /equipos/{equipo_id}/seguimientos — lista de seguimientos del equipo. */
export async function listSeguimientos(
  equipoId: number,
): Promise<Seguimiento[]> {
  const { data } = await api.get<SeguimientoList>(
    `/equipos/${equipoId}/seguimientos`,
  )
  return data.seguimientos
}

/** GET /equipos/{equipo_id}/seguimientos/{seguimiento_id} — detalle. */
export async function getSeguimiento(
  equipoId: number,
  seguimientoId: number,
): Promise<Seguimiento> {
  const { data } = await api.get<Seguimiento>(
    `/equipos/${equipoId}/seguimientos/${seguimientoId}`,
  )
  return data
}

/** POST /equipos/{equipo_id}/seguimientos — apertura (201). */
export async function crearSeguimiento(
  equipoId: number,
  payload: SeguimientoCreatePayload,
): Promise<Seguimiento> {
  const { data } = await api.post<Seguimiento>(
    `/equipos/${equipoId}/seguimientos`,
    payload,
  )
  return data
}

/** POST /equipos/{equipo_id}/seguimientos/{seguimiento_id}/cerrar — cierre.
 *  `sobrantes` solo requiere los materiales con devolución; los omitidos se
 *  cierran con sobrante 0 (resolución backend). */
export async function cerrarSeguimiento(
  equipoId: number,
  seguimientoId: number,
  payload: CerrarSeguimientoPayload,
): Promise<Seguimiento> {
  const { data } = await api.post<Seguimiento>(
    `/equipos/${equipoId}/seguimientos/${seguimientoId}/cerrar`,
    payload,
  )
  return data
}

/**
 * POST /equipos/{equipo_id}/seguimientos/{seguimiento_id}/agregar-todo
 * (REQ-P2-CON-003) — carga al seguimiento ABIERTA todo el inventario del
 * equipo con existencias. Atómico e idempotente en PostgreSQL
 * (fn_agregar_todo_seguimiento): una segunda invocación no duplica líneas.
 *
 * El body es OPCIONAL: sin `claveIdempotencia` NO se envía cuerpo. Con clave,
 * un reenvío devuelve el resultado original.
 *
 * NOTA DE USO: este servicio (y `useAgregarTodoSeguimiento`) NO está montado
 * en ninguna pantalla — hoy no existe UI para editar un seguimiento ABIERTO;
 * el botón «Agregar todo» de SeguimientoNuevaListaForm precarga LOCALMENTE el
 * borrador antes de crear el seguimiento (decisión UX T4.2). Queda disponible
 * para cuando se añada edición de un seguimiento abierto.
 *
 * Errores: 404 (no pertenece al equipo), 409 (no está ABIERTA).
 */
export async function agregarTodoSeguimiento(
  equipoId: number,
  seguimientoId: number,
  claveIdempotencia?: string,
): Promise<AgregarTodoResultadoOut> {
  const url = `/equipos/${equipoId}/seguimientos/${seguimientoId}/agregar-todo`
  const { data } =
    claveIdempotencia === undefined
      ? await api.post<AgregarTodoResultadoOut>(url)
      : await api.post<AgregarTodoResultadoOut>(url, {
          clave_idempotencia: claveIdempotencia,
        } satisfies AgregarTodoPayload)
  return data
}
