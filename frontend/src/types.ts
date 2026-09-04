export interface Material {
  codigo: string
  descripcion: string | null
  um: string | null
  stock_minimo: number | null
  categoria: string | null
  tipo: string
}

export interface InventoryRow {
  codigo: string
  descripcion: string | null
  um: string | null
  categoria: string | null
  tipo: string
  stock_actual: number
  stock_minimo: number | null
  alerta_stock: boolean
  almacen: string
  almacen_id: string
}

export interface TeamInventoryItem {
  id: number
  equipo: string
  usuario: string
  codigo: string
  descripcion: string | null
  cantidad: number
  ultima_modificacion: string
}

export interface FiberVariant {
  id: number
  codigo: string
  descripcion: string | null
  variante: string
  metros_restantes: number
  stock_actual: number
  almacen: string | null
}

export interface Kpis {
  total_materiales: number
  stock_total: number
  alertas_stock: number
  transferencias_hoy: number
}

export interface TransferLine {
  line_id: number
  sku: string
  dispatched_quantity: number
  received_quantity: number | null
}

export interface Transfer {
  transfer_id: string
  idempotency_key: string
  status: string
  source_warehouse_id: string
  destination_warehouse_id: string
  requested_by: string
  approved_by: string | null
  created_at: string
  dispatched_at: string | null
  received_at: string | null
  lines: TransferLine[]
}

export interface AuditLogItem {
  log_id: number
  action: string
  actor: string
  details: Record<string, unknown> | null
  created_at: string
}

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

export const TIPOS = ['GENERAL', 'FIBRA'] as const

export const ESTADOS_TRANSFERENCIA: Record<string, string> = {
  PENDING_APPROVAL: 'Pendiente de aprobación',
  APPROVED: 'Aprobado',
  IN_TRANSIT: 'En tránsito',
  RECEIVED: 'Recibido',
  REJECTED: 'Rechazado',
  CANCELLED: 'Cancelado',
}

export const ACCIONES_AUDITORIA: Record<string, string> = {
  MATERIAL_CREATE: 'Material creado',
  MATERIAL_UPDATE: 'Material modificado',
  MATERIAL_DELETE: 'Material eliminado',
  TEAM_INVENTORY_CREATE: 'Asignación creada',
  TEAM_INVENTORY_UPDATE: 'Asignación modificada',
  TEAM_INVENTORY_DELETE: 'Asignación eliminada',
  FIBER_VARIANT_CREATE: 'Variante creada',
  TRANSFER_CREATE: 'Transferencia creada',
  TRANSFER_APPROVE: 'Transferencia aprobada',
  TRANSFER_REJECT: 'Transferencia rechazada',
  TRANSFER_DISPATCH: 'Transferencia despachada',
  TRANSFER_RECEIVE: 'Transferencia recibida',
  TRANSFER_CANCEL: 'Transferencia cancelada',
  AUTHZ_DENIED: 'Acceso denegado',
  STOCK_ADJUST: 'Ajuste de stock',
  STOCK_ADJUST_BULK: 'Ajuste de stock masivo',
  FLEET_ALLOCATION: 'Asignación de flota',
}

export interface NavigationTarget {
  page: string
  sub?: string
}
