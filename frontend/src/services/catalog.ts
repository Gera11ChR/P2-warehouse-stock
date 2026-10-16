import api from './api'
import type { Categoria, Material, MaterialList, Ums } from '../types'

// ============================================================================
// FILTROS Y PAYLOADS
// ============================================================================

export interface CatalogFilters {
  buscar?: string
  categoria_id?: number
  /** @deprecated La UI dejó de enviar estos filtros legacy (rango por PK).
   *  El backend los conserva por compatibilidad. */
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
   * stock. Ergonomía `justificacion_opcional` (REQ-ERG-003): `motivo` es
   * OPCIONAL — vacío se envía como `null`.
   */
  stock_actual?: number
  /**
   * RF-3/RF-8: Valor Unitario en MXN (decimal ≥ 0, hasta 3 decimales). Su
   * sola PRESENCIA exige rol administrador (403 si no); un `null` explícito
   * es no-op. Solo se envía cuando el administrador lo cambió.
   */
  valor_unitario?: number
  motivo?: string | null
}

export interface CategoriaCreatePayload {
  nombre: string
}

/** PUT /catalogo/categorias/{categoria_id} — renombrar (admin-only). */
export interface CategoriaUpdatePayload {
  nombre: string
}

/** POST /catalogo/um — alta de unidad de medida (admin-only). */
export interface UmCreatePayload {
  nombre: string
}

/** PUT /catalogo/um/{um_id} — renombrar unidad de medida (admin-only). */
export interface UmUpdatePayload {
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

/**
 * PUT /catalogo/categorias/{categoria_id} — renombrar categoría.
 * Admin-only: 403 `{error:{code,message,actor}}` para no-admin
 * (el frontend solo representa el estado; RBAC es backend).
 */
export async function updateCategoria(
  categoria_id: number,
  payload: CategoriaUpdatePayload,
): Promise<Categoria> {
  const { data } = await api.put<Categoria>(
    `/catalogo/categorias/${categoria_id}`,
    payload,
  )
  return data
}

/** DELETE /catalogo/categorias/{categoria_id} — 204 (admin-only). */
export async function deleteCategoria(categoria_id: number): Promise<void> {
  await api.delete(`/catalogo/categorias/${categoria_id}`)
}

// ============================================================================
// UNIDADES DE MEDIDA (U.M.) — contrato real /api/v1/catalogo/um
// ============================================================================

/** GET /catalogo/um — unidades de medida activas/inactivas. */
export async function listUms(): Promise<Ums[]> {
  const { data } = await api.get<Ums[]>('/catalogo/um')
  return data
}

/** POST /catalogo/um — alta (201, admin-only). */
export async function createUm(payload: UmCreatePayload): Promise<Ums> {
  const { data } = await api.post<Ums>('/catalogo/um', payload)
  return data
}

/** PUT /catalogo/um/{um_id} — renombrar (admin-only). */
export async function updateUm(
  um_id: number,
  payload: UmUpdatePayload,
): Promise<Ums> {
  const { data } = await api.put<Ums>(`/catalogo/um/${um_id}`, payload)
  return data
}

/** DELETE /catalogo/um/{um_id} — 204 (admin-only). */
export async function deleteUm(um_id: number): Promise<void> {
  await api.delete(`/catalogo/um/${um_id}`)
}
