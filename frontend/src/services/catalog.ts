import api from './api'
import type { Categoria, Material } from '../types'

// ============================================================================
// FILTROS Y PAYLOADS
// ============================================================================

export interface CatalogFilters {
  buscar?: string
  categoria_id?: number
  desde_id_lista?: number
  hasta_id_lista?: number
  desde_sku?: string
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
}

export interface CategoriaCreatePayload {
  nombre: string
}

// ============================================================================
// CATÁLOGO DE MATERIALES
// ============================================================================

export async function listCatalog(filters?: CatalogFilters): Promise<Material[]> {
  const { data } = await api.get<{ materiales: Material[] }>('/catalogo', {
    params: filters,
  })
  return data.materiales
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
