// ============================================================================
// CATÁLOGO Y MATERIALES (contrato real /api/v1/catalogo)
// ============================================================================

export interface Categoria {
  id: number
  nombre: string
  is_active: boolean
}

export interface Material {
  id_lista: number
  codigo: string | null
  descripcion: string
  categoria_id: number | null
  categoria: string | null
  u_m: string | null
  stock_minimo: number | null
  is_active: boolean
}

// ============================================================================
// INVENTARIO Y SECCIONES (contrato real /api/v1/inventario)
// ============================================================================

export interface Seccion {
  almacen_id: number
  nombre: string
  tipo: string
  is_active: boolean
}

export interface SeccionStockRow {
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
}

/** Fila de inventario con contexto de sección para la UI */
export interface InventoryRow extends SeccionStockRow {
  almacen_id: number
  almacen: string
}

// ============================================================================
// EQUIPOS (FASE 2 — contrato real /api/v1/equipos)
// ============================================================================

export interface Equipo {
  equipo_id: number
  nombre: string
  descripcion: string | null
  is_active: boolean
  integrantes: string[]
}

/** Fila del inventario sparse por equipo (vista vw_inventario_equipo_completo) */
export interface CatalogoEquipoRow {
  equipo_id: number
  id_lista: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
}

// ============================================================================
// KPIs (sin endpoint /kpis — agregación visual en FASE 1)
// ============================================================================

export interface Kpis {
  total_materiales: number
  stock_total: number
  alertas_stock: number
  transferencias_hoy: number
}

// ============================================================================
// MOVIMIENTOS (FASE 3 — contrato real /api/v1/movimientos)
// ============================================================================

export type TipoMovimiento = 'TEAMS' | 'DEVOL'
export type EstadoMovimiento = 'BORRADOR' | 'CONFIRMADO' | 'CANCELADO'

export interface DetalleMovimiento {
  material_id: number
  cantidad: number
}

export interface Movimiento {
  id: number
  tipo_movimiento: TipoMovimiento
  estado: EstadoMovimiento
  usuario: string
  origen_almacen_id: number | null
  destino_almacen_id: number | null
  origen_equipo_id: number | null
  destino_equipo_id: number | null
  observaciones: string | null
  detalle: DetalleMovimiento[]
}

export const ESTADOS_MOVIMIENTO: Record<EstadoMovimiento, string> = {
  BORRADOR: 'Borrador',
  CONFIRMADO: 'Confirmado',
  CANCELADO: 'Cancelado',
}

export const TIPOS_MOVIMIENTO: Record<TipoMovimiento, string> = {
  TEAMS: 'TEAMS',
  DEVOL: 'DEVOL',
}

/** Línea de carrito temporal (UX). cantidad_transferir/cantidad_devolver
 *  son campos SOLO del carrito; el payload real usa material_id + cantidad. */
export interface CartLine {
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_disponible: number
  cantidad_transferir?: number
  cantidad_devolver?: number
}

// ============================================================================
// AUDITORÍA (contrato real /api/v1/auditoria)
// ============================================================================

export interface EventoAuditoria {
  id: number
  usuario: string | null
  tipo_accion: string
  material_id: number | null
  equipo_origen_id: number | null
  equipo_destino_id: number | null
  almacen_origen_id: number | null
  almacen_destino_id: number | null
  cantidad: number | null
  resultado: string | null
  detalles: Record<string, unknown> | null
  created_at: string
}

export const TIPOS_ACCION_AUDITORIA: Record<string, string> = {
  MATERIAL_MODIFICADO: 'Material modificado',
  TEAMS_TRANSFERENCIA: 'TEAMS — transferencia',
  DEVOL_DEVOLUCION: 'DEVOL — devolución',
  MOVIMIENTO_CANCELADO: 'Movimiento cancelado',
  STOCK_INICIAL: 'Carga inicial de stock',
  AJUSTE_INVENTARIO: 'Ajuste de inventario',
}

// ============================================================================
// CONSTANTES DEL DOMINIO
// ============================================================================

/** Unidades de medida soportadas (FASE 1 — coincide con backend SUPPORTED_UNITS) */
export const UNIDADES = [
  'PZ',
  'LT',
  'CARRETE (1 KM)',
  'METRO (M)',
  'CARRETE (5 KM)',
  'BOLSA (500 PZ)',
  'PAQUETE (100 PZ)',
  'ROLLO',
  'EQUIPO',
  'UNIDAD',
] as const

// ============================================================================
// NAVEGACIÓN (UI)
// ============================================================================

export interface NavigationTarget {
  page: string
  sub?: string
}
