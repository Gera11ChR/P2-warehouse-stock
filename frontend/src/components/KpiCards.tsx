import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRightLeft,
  Boxes,
  Layers,
} from 'lucide-react'
import { getKpis } from '../services/kpis'
import type { Kpis } from '../types'

interface KpiCardsProps {
  refreshToken: number
}

interface CardDef {
  key: keyof Kpis
  label: string
  icon: typeof Boxes
  iconClass: string
}

const CARDS: CardDef[] = [
  {
    key: 'total_materiales',
    label: 'Total Materiales',
    icon: Boxes,
    iconClass: 'bg-blue-500',
  },
  {
    key: 'stock_total',
    label: 'Stock Total',
    icon: Layers,
    iconClass: 'bg-green-500',
  },
  {
    key: 'alertas_stock',
    label: 'Alertas Stock',
    icon: AlertTriangle,
    iconClass: 'bg-amber-500',
  },
  {
    key: 'transferencias_hoy',
    label: 'Transferencias Hoy',
    icon: ArrowRightLeft,
    iconClass: 'bg-purple-500',
  },
]

export default function KpiCards({ refreshToken }: KpiCardsProps) {
  const [kpis, setKpis] = useState<Kpis | null>(null)

  useEffect(() => {
    let active = true
    getKpis().then((data) => {
      if (active) setKpis(data)
    })
    return () => {
      active = false
    }
  }, [refreshToken])

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {CARDS.map((card) => {
        const Icon = card.icon
        const value = kpis ? kpis[card.key] : 0
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
            <div>
              <p className="text-sm text-slate-500">{card.label}</p>
              <p className="text-2xl font-semibold text-slate-800">
                {value.toLocaleString('es-MX')}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
