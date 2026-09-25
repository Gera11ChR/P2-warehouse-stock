import type { InventoryRow } from '../types'
import { stockLevel } from '../utils/stockLevel'
import type { StockLevel } from '../utils/stockLevel'

const LEVEL_CLASS: Record<StockLevel, string> = {
  normal: 'bg-green-100 text-green-700',
  low: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

interface InventoryTableProps {
  rows: InventoryRow[]
  selectedCodigo: string | null
  onSelect: (row: InventoryRow) => void
  /**
   * REQ-UI-005: join de PRESENTACIÓN material_id → nombre de categoría.
   * Resuelto desde el endpoint oficial /catalogo (la fila de stock por
   * sección no incluye categoría); el frontend solo proyecta, nunca
   * es fuente de verdad.
   */
  categoriaPorMaterial?: Record<number, string>
}

export default function InventoryTable({
  rows,
  selectedCodigo,
  onSelect,
  categoriaPorMaterial,
}: InventoryTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Nº</th>
            <th className="px-4 py-3">Código</th>
            <th className="px-4 py-3">Descripción</th>
            <th className="px-4 py-3">Categoría</th>
            <th className="px-4 py-3">U.M.</th>
            <th className="px-4 py-3">Stock Actual</th>
            <th className="px-4 py-3">Stock Mínimo</th>
            <th className="px-4 py-3">Alerta Stock</th>
            <th className="px-4 py-3">Almacén</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, index) => {
            const level = stockLevel(row)
            const selected = selectedCodigo === row.codigo
            return (
              <tr
                key={`${row.material_id}-${row.almacen_id}`}
                onClick={() => onSelect(row)}
                className={`cursor-pointer transition-colors hover:bg-blue-50 ${
                  selected ? 'bg-blue-50' : ''
                }`}
              >
                <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                  {index + 1}
                </td>
                <td className="px-4 py-3 font-mono text-slate-700">{row.codigo ?? '—'}</td>
                <td className="px-4 py-3 text-slate-700">{row.descripcion ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600">
                  {categoriaPorMaterial?.[row.material_id] ?? '—'}
                </td>
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
                <td className="px-4 py-3 text-slate-700">{row.almacen}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
