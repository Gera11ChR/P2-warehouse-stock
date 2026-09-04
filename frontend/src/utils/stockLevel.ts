import type { InventoryRow } from '../types'

export type StockLevel = 'normal' | 'low' | 'critical'

export function stockLevel(row: InventoryRow): StockLevel {
  if (row.alerta_stock || row.stock_actual <= 0) {
    return 'critical'
  }
  if (row.stock_minimo != null && row.stock_actual <= row.stock_minimo * 1.5) {
    return 'low'
  }
  return 'normal'
}
