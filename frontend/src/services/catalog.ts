import api from './api'
import type { Categoria, Material, MaterialList } from '../types'

// ============================================================================
// FILTROS Y PAYLOADS
// ============================================================================

export interface CatalogFilters {
  buscar?: string
  categoria_id?: number
  /**
   * Rango ordinal 1-indexed del Buscador a granel (REQ-API-006).
   * El posicionamiento determinista (ORDER BY descripcion ASC, id_lista ASC,
   * OFFSET/LIMIT) y el `start_index` de la respuesta se resuelven 100 % en
   * backend.
   */
  desde_numero_lista?: number
  hasta_numero_lista?: number
  /** Rango determinista por descripción (REQ-API-007). */
  desde_descripcion?: string
  hasta_descripcion?: string
  /** @deprecated La UI dejó de enviar estos filtros legacy (rango por PK).
   *  El backend los conserva por compatibilidad; el frontend usa los rangos
   *  ordinales/textuales nuevos. */
  desde_id_lista?: number
  /** @deprecated (ver desde_id_lista) */
  hasta_id_lista?: number
  /** @deprecated (ver desde_id_lista) */
  desde_sku?: string
  /** @deprecated (ver desde_id_lista) */
  hasta_sku?: string
}

export interface MaterialCreatePayload {
  descripcion: string
  codigo?: string | null
  categoria_id?: number | null
  nueva_categoria?: string | null
  u_m?: string | null
  stock_minimo?: number | null
  stock_inicial?: number | null
  seccion_id?: number | null
}

export interface MaterialUpdatePayload {
  descripcion?: string | null
  codigo?: string | null
  categoria_id?: number | null
  nueva_categoria?: string | null
  u_m?: string | null
  stock_minimo?: number | null
  is_active?: boolean
  /**
   * REQ-API-002/003 (alcance Inventario General, REQ-UI-004): si se envía
   * `stock_actual`, el backend calcula el delta y lo enruta a
   * `fn_ajustar_stock_almacen` con auditoría; NUNCA hay UPDATE directo de
   * stock. `motivo` es OBLIGATORIO y no vacío cuando viene `stock_actual`
   * (el backend responde 422 si falta).
   */
  stock_actual?: number
  motivo?: string
}

export interface CategoriaCreatePayload {
  nombre: string
}

// ============================================================================
// CATÁLOGO DE MATERIALES
// ============================================================================

export async function listCatalog(
  filters?: CatalogFilters,
): Promise<MaterialList> {
  const { data } = await api.get<MaterialList>('/catalogo', {
    params: filters,
  })
  return data
}

export async function getMaterial(id_lista: number): Promise<Material> {
  const { data } = await api.get<Material>(`/catalogo/${id_lista}`)
  return data
}

export async function createMaterial(
  payload: MaterialCreatePayload,
): Promise<Material> {
  const { data } = await api.post<Material>('/catalogo', payload)
  return data
}

export async function updateMaterial(
  id_lista: number,
  payload: MaterialUpdatePayload,
): Promise<Material> {
  const { data } = await api.patch<Material>(`/catalogo/${id_lista}`, payload)
  return data
}

export async function deleteMaterial(id_lista: number): Promise<void> {
  await api.delete(`/catalogo/${id_lista}`)
}

// ============================================================================
// CATEGORÍAS
// ============================================================================

export async function listCategorias(): Promise<Categoria[]> {
  const { data } = await api.get<Categoria[]>('/catalogo/categorias')
  return data
}

export async function createCategoria(
  payload: CategoriaCreatePayload,
): Promise<Categoria> {
  const { data } = await api.post<Categoria>('/catalogo/categorias', payload)
  return data
}
