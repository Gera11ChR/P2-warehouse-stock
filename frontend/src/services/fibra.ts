import api from './api'
import type {
  FibraAjustePayload,
  FibraCargaInicialPayload,
  FibraMaterialOut,
  FibraMaterialUpdatePayload,
  FibraOperacionOut,
  FibraStockRow,
} from '../types'

// ============================================================================
// INVENTARIO FO — inventario único por material
// (contrato real /api/v1/fibra; RF-1, RF-3, RF-6)
//
// Sin módulos ni subapartados: una sola fila por material. Toda mutación de
// stock se delega en el backend a las stored functions
// fn_cargar_stock_inicial_fibra / fn_ajustar_stock_fibra (PostgreSQL): el
// frontend NUNCA calcula ni escribe stock. Enviar `modulo` es 422 (RF-1).
//
// FAIL-CLOSED: un error de API (404/422/500) se muestra como error —
// NUNCA se reinterpreta como stock = 0 ni como inventario vacío.
// ============================================================================

/** GET /fibra — Inventario FO con esquema estándar y `valor_unitario`.
 *  Solo filas físicas (cero fantasmas); la métrica la gobierna `u_m`. */
export async function listFibraStock(): Promise<FibraStockRow[]> {
  const { data } = await api.get<FibraStockRow[]>('/fibra')
  return data
}

/** POST /fibra/carga-inicial — alta única e idempotente (rechaza si la fila
 *  del material ya existe). Audita 'STOCK_INICIAL_FO' en PostgreSQL. */
export async function cargarStockInicialFibra(
  payload: FibraCargaInicialPayload,
): Promise<FibraOperacionOut> {
  const { data } = await api.post<FibraOperacionOut>(
    '/fibra/carga-inicial',
    payload,
  )
  return data
}

/** POST /fibra/ajuste — ajuste administrativo con `motivo` OPCIONAL
 *  (ergonomía `justificacion_opcional`, REQ-ERG-005). El diferencial, el
 *  bloqueo FOR UPDATE y la auditoría ('AJUSTE_INVENTARIO_FO') se calculan
 *  en PostgreSQL. */
export async function ajustarStockFibra(
  payload: FibraAjustePayload,
): Promise<FibraOperacionOut> {
  const { data } = await api.post<FibraOperacionOut>('/fibra/ajuste', payload)
  return data
}

/** PATCH /fibra/materiales/{id} — edición de material del Inventario FO.
 *  Si `stock_actual` viene en el payload, el backend enruta el ajuste a
 *  `fn_ajustar_stock_fibra` dentro de la MISMA transacción con auditoría
 *  'AJUSTE_INVENTARIO_FO'. `valor_unitario` solo lo puede enviar un
 *  administrador (403 por presencia del campo; RF-8). `motivo` es OPCIONAL —
 *  vacío se envía como `null`. El frontend NUNCA envía el diferencial. */
export async function updateFibraMaterial(
  id: number,
  payload: FibraMaterialUpdatePayload,
): Promise<FibraMaterialOut> {
  const { data } = await api.patch<FibraMaterialOut>(
    `/fibra/materiales/${id}`,
    payload,
  )
  return data
}

/** DELETE /fibra/materiales/{id} — eliminación FÍSICA de la fila del
 *  Inventario FO (REQ-DEL-001/002/003; E12). `motivo` viaja como query param
 *  SOLO si viene (204 sin body); es OBLIGATORIO si la fila tiene
 *  stock_actual > 0 — la validación autoritativa vive en PostgreSQL
 *  (RAISE → 422). Audita 'ELIMINACION_FO' con snapshot jsonb. */
export async function eliminarFibraMaterial(
  id: number,
  motivo?: string,
): Promise<void> {
  await api.delete(`/fibra/materiales/${id}`, {
    params: motivo ? { motivo } : undefined,
  })
}
