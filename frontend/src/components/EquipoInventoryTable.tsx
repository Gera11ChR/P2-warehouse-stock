import type { CatalogoEquipoRow } from '../types'
import { stockLevel } from '../utils/stockLevel'
import type { StockLevel } from '../utils/stockLevel'

const LEVEL_CLASS: Record<StockLevel, string> = {
  normal: 'bg-green-100 text-green-700',
  low: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

interface EquipoInventoryTableProps {
  rows: CatalogoEquipoRow[]
}

export default function EquipoInventoryTable({
  rows,
}: EquipoInventoryTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">ID Lista</th>
            <th className="px-4 py-3">Código</th>
            <th className="px-4 py-3">Descripción</th>
            <th className="px-4 py-3">U.M.</th>
            <th className="px-4 py-3">Stock Actual</th>
            <th className="px-4 py-3">Stock Mínimo</th>
            <th className="px-4 py-3">Alerta Stock</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => {
            const level = stockLevel(row)
            return (
              <tr key={row.id_lista} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                  {row.id_lista}
                </td>
                <td className="px-4 py-3 font-mono text-slate-700">
                  {row.codigo ?? '—'}
                </td>
                <td className="px-4 py-3 text-slate-700">{row.descripcion}</td>
                <td className="px-4 py-3 text-slate-500">{row.u_m ?? '—'}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${LEVEL_CLASS[level]}`}
                  >
                    {row.stock_actual.toLocaleString('es-MX')}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {row.stock_minimo != null ? row.stock_minimo : '—'}
                </td>
                <td className="px-4 py-3">
                  {row.alerta_stock ? (
                    <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                      Alerta Stock
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div className="p-6 text-center text-sm text-slate-500">
          No hay registros de inventario para este equipo.
        </div>
      )}
    </div>
  )
}
