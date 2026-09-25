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

/**
 * Respuesta de GET /api/v1/catalogo (contrato real MaterialListOut).
 * `start_index` es el ordinal 1-indexed de la primera fila del rango
 * (REQ-API-006): el frontend numera filas continuas SIN descargar el
 * catálogo completo.
 */
export interface MaterialList {
  start_index: number
  materiales: Material[]
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

/**
 * Fila del inventario AUTÓNOMO del equipo (contrato real
 * GET /api/v1/equipos/{equipo_id}/inventario, InventarioEquipoOut;
 * REQ-DOMAIN-001/002). Reemplaza al modelo sparse deprecado
 * (vw_inventario_equipo_completo, CatalogoEquipoRow): SOLO filas físicas
 * con stock real originado en movimientos TEAMS/DEVOL auditados
 * (cero fantasmas de stock 0). `ultimo_movimiento_id` traza el movimiento
 * de origen. Equipo nuevo → [] (200); 404 solo si el equipo no existe.
 */
export interface InventarioEquipoRow {
  equipo_id: number
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
  ultimo_movimiento_id: number | null
}

// ============================================================================
// FIBRA ÓPTICA — inventarios independientes PAQUETE / EN_USO
// (contrato real /api/v1/fibra; REQ-DOMAIN-003/004/005)
// ============================================================================

export type FibraModulo = 'PAQUETE' | 'EN_USO'

/** Fila de stock FO con esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M.,
 *  STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK). La métrica la gobierna `u_m`
 *  (el legado carretes/metros de fiber_variants está deprecado). */
export interface FibraStockRow {
  modulo: FibraModulo
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
}

/** POST /api/v1/fibra/carga-inicial — alta única e idempotente.
 *  `cantidad` >= 0; `motivo` opcional. */
export interface FibraCargaInicialPayload {
  modulo: FibraModulo
  material_id: number
  cantidad: number
  motivo?: string
}

/** POST /api/v1/fibra/ajuste — ajuste administrativo.
 *  `nuevo_stock` >= 0; `motivo` OBLIGATORIO y no vacío (422 si falta). */
export interface FibraAjustePayload {
  modulo: FibraModulo
  material_id: number
  nuevo_stock: number
  motivo: string
}

/** Eco mínimo de una operación FO (FibraOperacionOut). */
export interface FibraOperacionOut {
  modulo: FibraModulo
  material_id: number
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
  /** LEFT JOIN al catálogo SIN filtro is_active (REQ-API-008):
   *  el historial queda íntegro aunque el material esté inactivo. */
  descripcion: string | null
  codigo: string | null
  categoria: string | null
  estado_activo: boolean | null
}

export const TIPOS_ACCION_AUDITORIA: Record<string, string> = {
  MATERIAL_MODIFICADO: 'Material modificado',
  TEAMS_TRANSFERENCIA: 'TEAMS — transferencia',
  DEVOL_DEVOLUCION: 'DEVOL — devolución',
  MOVIMIENTO_CANCELADO: 'Movimiento cancelado',
  STOCK_INICIAL: 'Carga inicial de stock',
  AJUSTE_INVENTARIO: 'Ajuste de inventario',
  STOCK_INICIAL_FO: 'Carga inicial FO',
  AJUSTE_INVENTARIO_FO: 'Ajuste de inventario FO',
  MIGRACION_FO: 'Migración FO',
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
