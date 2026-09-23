export type StockLevel = 'normal' | 'low' | 'critical'

interface StockRow {
  stock_actual: number
  stock_minimo: number | null
  alerta_stock: boolean
}

export function stockLevel(row: StockRow): StockLevel {
  if (row.alerta_stock || row.stock_actual <= 0) {
    return 'critical'
  }
  if (row.stock_minimo != null && row.stock_actual <= row.stock_minimo * 1.5) {
    return 'low'
  }
  return 'normal'
}
