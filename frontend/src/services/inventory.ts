import api from './api'
import type {
  MoverMaterialOut,
  Seccion,
  SeccionStockRow,
  SeccionTransferible,
  SumarCantidadOut,
} from '../types'
import type {
  MoverMaterialPayload,
  SumarCantidadPayload,
} from '../utils/operadorPayload'

/**
 * SECCIONES (almacenes/inventarios) — contrato real /api/v1/inventario
 *
 * FAIL-CLOSED: nunca interpretar error de API como stock = 0.
 * El Frontend NO reconcilia inventario localmente; solo consume DTOs del Backend.
 *
 * NOTA (REQ-DOMAIN-001/002): el inventario de Equipos ya NO se sirve desde
 * este router. El endpoint sparse `/inventario/equipos/{id}` fue ELIMINADO
 * junto con la vista `vw_inventario_equipo_completo`. El inventario autónomo
 * de equipos se consume vía GET /api/v1/equipos/{equipo_id}/inventario
 * (ver services/equipos.ts → `inventarioEquipo`).
 */

export async function listSecciones(): Promise<Seccion[]> {
  const { data } = await api.get<Seccion[]>('/inventario/secciones')
  return data
}

export async function stockSeccion(almacen_id: number): Promise<SeccionStockRow[]> {
  const { data } = await api.get<SeccionStockRow[]>(
    `/inventario/secciones/${almacen_id}`,
  )
  return data
}

/**
 * GET /inventario/secciones/transferibles — secciones candidatas a ser
 * extremo de una transferencia. `transferible=false` las excluye en la UI;
 * la validación final sigue siendo del backend (RBAC/dominio).
 */
export async function listSeccionesTransferibles(): Promise<
  SeccionTransferible[]
> {
  const { data } = await api.get<SeccionTransferible[]>(
    '/inventario/secciones/transferibles',
  )
  return data
}

// ============================================================================
// OPERADORES RÁPIDOS — «+Cantidad» y «Mover» (REQ-P2-INV-001/003/007)
// Contrato certificado: POST /api/v1/inventario/sumar-cantidad y /mover.
//
// El servicio solo TRANSPORTA el payload construido por
// `construirPayloadSumar/Mover` (utils/operadorPayload.ts). La suma, el
// descuento/acreditación, la auditoría inmutable y la idempotencia viven en
// PostgreSQL (fn_sumar_cantidad / fn_mover_material): el stock resultante
// llega en la RESPUESTA (stock_nuevo / stock_origen / stock_destino) y es la
// única fuente de verdad — el cliente no calcula stock.
//
// Errores 400/403/404/409/422: se propagan tal cual; los traduce
// `traducirErrorOperador` (utils/operadorErrores.ts).
// ============================================================================

/** POST /inventario/sumar-cantidad (200). */
export async function sumarCantidad(
  payload: SumarCantidadPayload,
): Promise<SumarCantidadOut> {
  const { data } = await api.post<SumarCantidadOut>(
    '/inventario/sumar-cantidad',
    payload,
  )
  return data
}

/** POST /inventario/mover (200). */
export async function moverMaterial(
  payload: MoverMaterialPayload,
): Promise<MoverMaterialOut> {
  const { data } = await api.post<MoverMaterialOut>(
    '/inventario/mover',
    payload,
  )
  return data
}
