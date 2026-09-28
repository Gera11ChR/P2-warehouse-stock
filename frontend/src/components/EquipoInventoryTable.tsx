import type { InventarioEquipoRow } from '../types'
import { stockLevel } from '../utils/stockLevel'
import type { StockLevel } from '../utils/stockLevel'

const LEVEL_CLASS: Record<StockLevel, string> = {
  normal: 'bg-green-100 text-green-700',
  low: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

interface EquipoInventoryTableProps {
  rows: InventarioEquipoRow[]
  /**
   * Solo en la pestaña Configuración: habilita la columna de acciones que
   * abre el formulario de configuración local (FASE 7). En Consulta la
   * tabla permanece de solo lectura (sin acciones).
   */
  onConfigurar?: (row: InventarioEquipoRow) => void
}

/** ¿La fila tiene configuración LOCAL definida para este equipo? */
function tieneConfigLocal(row: InventarioEquipoRow): boolean {
  return (
    row.stock_minimo_local != null ||
    row.categoria_local_id != null ||
    row.um_local_id != null
  )
}

export default function EquipoInventoryTable({
  rows,
  onConfigurar,
}: EquipoInventoryTableProps) {
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
            {onConfigurar && <th className="px-4 py-3" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, index) => {
            const level = stockLevel(row)
            return (
              <tr key={row.material_id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                  {index + 1}
                </td>
                <td className="px-4 py-3 font-mono text-slate-700">
                  {row.codigo ?? '—'}
                </td>
                <td className="px-4 py-3 text-slate-700">{row.descripcion}</td>
                <td className="px-4 py-3 text-slate-600">
                  {row.categoria_efectiva ?? '—'}
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {row.um_efectivo ?? '—'}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${LEVEL_CLASS[level]}`}
                  >
                    {row.stock_actual.toLocaleString('es-MX')}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {row.stock_minimo_efectivo != null
                    ? row.stock_minimo_efectivo
                    : '—'}
                  {tieneConfigLocal(row) && (
                    <span className="ml-1 inline-flex rounded bg-blue-100 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
                      local
                    </span>
                  )}
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
                {onConfigurar && (
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onConfigurar(row)}
                      className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
                    >
                      Configurar
                    </button>
                  </td>
                )}
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
