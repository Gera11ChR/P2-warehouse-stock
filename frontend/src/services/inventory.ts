import api from './api'
import type { Seccion, SeccionStockRow } from '../types'

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
