import api from './api'
import type { Seccion, SeccionStockRow, CatalogoEquipoRow } from '../types'

/**
 * SECCIONES (almacenes/inventarios) — contrato real /api/v1/inventario
 *
 * FAIL-CLOSED: nunca interpretar error de API como stock = 0.
 * El Frontend NO reconcilia inventario localmente; solo consume DTOs del Backend.
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
 * EQUIPOS — inventario sparse (FASE 2)
 *
 * Vista vw_inventario_equipo_completo: CROSS JOIN del catálogo activo con inventario_equipos.
 * COALESCE(stock_actual, 0) renderiza 0 donde no hay registro físico.
 *
 * FAIL-CLOSED: error de API (404/500) → mostrar error, NUNCA convertir en stock 0.
 */
export async function catalogoEquipo(equipo_id: number): Promise<CatalogoEquipoRow[]> {
  const { data } = await api.get<CatalogoEquipoRow[]>(
    `/inventario/equipos/${equipo_id}`,
  )
  return data
}
