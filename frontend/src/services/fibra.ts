import api from './api'
import type {
  FibraAjustePayload,
  FibraCargaInicialPayload,
  FibraMaterialOut,
  FibraMaterialUpdatePayload,
  FibraModulo,
  FibraOperacionOut,
  FibraStockRow,
} from '../types'

// ============================================================================
// FIBRA ÓPTICA — inventarios independientes PAQUETE / EN_USO
// (contrato real /api/v1/fibra; REQ-DOMAIN-003/004/005)
//
// Las raíces FO dejaron de ser secciones del Inventario General. Toda
// mutación de stock se delega en el backend a las stored functions
// fn_cargar_stock_inicial_fibra / fn_ajustar_stock_fibra (PostgreSQL):
// el frontend NUNCA calcula ni escribe stock.
//
// FAIL-CLOSED: un error de API (404/422/500) se muestra como error —
// NUNCA se reinterpreta como stock = 0 ni como inventario vacío.
// ============================================================================

/** GET /fibra/{modulo} — stock del inventario FO con esquema estándar.
 *  Solo filas físicas de `inventario_fibra` (cero fantasmas); la métrica
 *  la gobierna `u_m`. */
export async function listFibraStock(
  modulo: FibraModulo,
): Promise<FibraStockRow[]> {
  const { data } = await api.get<FibraStockRow[]>(`/fibra/${modulo}`)
  return data
}

/** POST /fibra/carga-inicial — alta única e idempotente (rechaza si la fila
 *  (modulo, material_id) ya existe). Audita 'STOCK_INICIAL_FO' en PostgreSQL. */
export async function cargarStockInicialFibra(
  payload: FibraCargaInicialPayload,
): Promise<FibraOperacionOut> {
  const { data } = await api.post<FibraOperacionOut>(
    '/fibra/carga-inicial',
    payload,
  )
  return data
}

/** POST /fibra/ajuste — ajuste administrativo con `motivo` OBLIGATORIO.
 *  El diferencial, el bloqueo FOR UPDATE y la auditoría
 *  ('AJUSTE_INVENTARIO_FO') se calculan en PostgreSQL. */
export async function ajustarStockFibra(
  payload: FibraAjustePayload,
): Promise<FibraOperacionOut> {
  const { data } = await api.post<FibraOperacionOut>('/fibra/ajuste', payload)
  return data
}

/** PATCH /fibra/{modulo}/materiales/{id} — edición de material desde una
 *  sección FO (REQ-CATFO-001). Si `stock_actual` viene en el payload, el
 *  backend exige `motivo` no vacío (422) y enruta el ajuste a
 *  `fn_ajustar_stock_fibra` dentro del MISMO session.begin() con auditoría
 *  'AJUSTE_INVENTARIO_FO' (REQ-STOCK-002/003): el frontend envía SOLO
 *  stock_actual + motivo, NUNCA el diferencial. */
export async function updateFibraMaterial(
  modulo: FibraModulo,
  id: number,
  payload: FibraMaterialUpdatePayload,
): Promise<FibraMaterialOut> {
  const { data } = await api.patch<FibraMaterialOut>(
    `/fibra/${modulo}/materiales/${id}`,
    payload,
  )
  return data
}

/** DELETE /fibra/{modulo}/materiales/{id} — eliminación FÍSICA de la fila
 *  (modulo, material_id) de `inventario_fibra` (REQ-DEL-001/002/003).
 *  `motivo` viaja como query param SOLO si viene (204 sin body); es
 *  OBLIGATORIO si la fila tiene stock_actual > 0 — la validación
 *  autoritativa vive en PostgreSQL (RAISE → 422, REQ-DEL-004). Audita
 *  'ELIMINACION_FO' con snapshot jsonb completo en la stored function. */
export async function eliminarFibraMaterial(
  modulo: FibraModulo,
  id: number,
  motivo?: string,
): Promise<void> {
  await api.delete(`/fibra/${modulo}/materiales/${id}`, {
    params: motivo ? { motivo } : undefined,
  })
}
