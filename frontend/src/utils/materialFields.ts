export const MATERIAL_FIELD_ORDER = [
  'descripcion',
  'stock_actual',
  'stock_minimo',
  'alerta_stock',
  'um',
  'codigo',
] as const

export type MaterialFieldKey = (typeof MATERIAL_FIELD_ORDER)[number]

export const MATERIAL_FIELD_LABELS: Record<MaterialFieldKey, string> = {
  descripcion: 'Descripción',
  stock_actual: 'Stock Actual',
  stock_minimo: 'Stock Mínimo',
  alerta_stock: 'Alerta Stock',
  um: 'U.M.',
  codigo: 'Código (SKU)',
}
