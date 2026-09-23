import { useMemo } from 'react'
import {
  AlertTriangle,
  ArrowRightLeft,
  Boxes,
  Layers,
} from 'lucide-react'
import type { SeccionStockRow } from '../types'

interface KpiCardsProps {
  stock: SeccionStockRow[]
}

interface CardDef {
  key: string
  label: string
  value: number
  icon: typeof Boxes
  iconClass: string
  note?: string
}

export default function KpiCards({
  stock,
}: KpiCardsProps) {
  // ============================================================================
  // AGREGACIÓN VISUAL (permitida por prompt maestro como proyección visual)
  // ============================================================================

  const cards: CardDef[] = useMemo(() => {
    // Total Materiales: unique material_id in stock (conteo de filas únicas)
    const totalMateriales = new Set(stock.map((r) => r.material_id)).size

    // Stock Total: suma de stock_actual
    const stockTotal = stock.reduce((acc, row) => acc + row.stock_actual, 0)

    // Alertas Stock: cantidad de filas con alerta_stock = true
    const alertasStock = stock.filter((row) => row.alerta_stock).length

    // Transferencias Hoy: sin endpoint /kpis ni movimientos (FASE 3) → 0
    const transferenciasHoy = 0

    return [
      {
        key: 'total_materiales',
        label: 'Total Materiales',
        value: totalMateriales,
        icon: Boxes,
        iconClass: 'bg-blue-500',
      },
      {
        key: 'stock_total',
        label: 'Stock Total',
        value: stockTotal,
        icon: Layers,
        iconClass: 'bg-green-500',
      },
      {
        key: 'alertas_stock',
        label: 'Alertas Stock',
        value: alertasStock,
        icon: AlertTriangle,
        iconClass: 'bg-amber-500',
      },
      {
        key: 'transferencias_hoy',
        label: 'Transferencias Hoy',
        value: transferenciasHoy,
        icon: ArrowRightLeft,
        iconClass: 'bg-purple-500',
        note: 'Disponible en FASE 3',
      },
    ]
  }, [stock])

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.key}
            className="flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-lg ${card.iconClass}`}
            >
              <Icon className="h-6 w-6 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-slate-500">{card.label}</p>
              <p className="text-2xl font-semibold text-slate-800">
                {card.value.toLocaleString('es-MX')}
              </p>
              {card.note && (
                <p className="text-xs text-slate-400">{card.note}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
