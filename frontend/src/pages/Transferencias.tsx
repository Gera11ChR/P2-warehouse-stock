import { useEffect, useState } from 'react'
import { listTransfers } from '../services/transfers'
import { listInventory } from '../services/inventory'
import { ESTADOS_TRANSFERENCIA } from '../types'
import type { Transfer } from '../types'

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString('es-MX') : '—'
}

export default function Transferencias() {
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [warehouseNames, setWarehouseNames] = useState<Record<string, string>>({})

  useEffect(() => {
    listTransfers().then(setTransfers)
    listInventory().then((rows) => {
      const map: Record<string, string> = {}
      rows.forEach((row) => {
        map[row.almacen_id] = row.almacen
      })
      setWarehouseNames(map)
    })
  }, [])

  const name = (id: string) => warehouseNames[id] ?? id

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Fecha</th>
            <th className="px-4 py-3">Origen</th>
            <th className="px-4 py-3">Destino</th>
            <th className="px-4 py-3">Líneas</th>
            <th className="px-4 py-3">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {transfers.map((transfer) => (
            <tr key={transfer.transfer_id}>
              <td className="px-4 py-3 text-slate-700">
                {formatDate(transfer.created_at)}
              </td>
              <td className="px-4 py-3 text-slate-700">
                {name(transfer.source_warehouse_id)}
              </td>
              <td className="px-4 py-3 text-slate-700">
                {name(transfer.destination_warehouse_id)}
              </td>
              <td className="px-4 py-3 text-slate-700">{transfer.lines.length}</td>
              <td className="px-4 py-3">
                <span className="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">
                  {ESTADOS_TRANSFERENCIA[transfer.status] ?? transfer.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
