import { useQuery } from '@tanstack/react-query'
import { listFibraStock } from '../services/fibra'
import { stockLevel } from '../utils/stockLevel'
import type { StockLevel } from '../utils/stockLevel'
import type { FibraModulo } from '../types'

interface FibraOpticaProps {
  sub: string
}

const MODULO_POR_SUB: Record<string, FibraModulo> = {
  paquete: 'PAQUETE',
  'en-uso': 'EN_USO',
}

const LEVEL_CLASS: Record<StockLevel, string> = {
  normal: 'bg-green-100 text-green-700',
  low: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

export default function FibraOptica({ sub }: FibraOpticaProps) {
  const esEnUso = sub === 'en-uso'
  const modulo = MODULO_POR_SUB[sub] ?? 'PAQUETE'

  // Inventario FO independiente (REQ-DOMAIN-003/004): raíz autónoma con
  // esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK
  // MÍNIMO, ALERTA STOCK). La métrica de cada fila la gobierna `u_m`
  // (REQ-DOMAIN-005); el legado "carretes/metros" está deprecado.
  const stockQuery = useQuery({
    queryKey: ['fibra', modulo],
    queryFn: () => listFibraStock(modulo),
  })

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-800">
          Fibra Óptica — {esEnUso ? 'En Uso' : 'Paquete'}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {esEnUso
            ? 'Inventario independiente EN USO. La unidad de medida (U.M.) de cada fila define su métrica.'
            : 'Inventario independiente PAQUETE. La unidad de medida (U.M.) de cada fila define su métrica.'}
        </p>
      </div>

      {stockQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando inventario de fibra…</p>
        </div>
      )}

      {stockQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-700">
            No se pudo obtener el inventario de fibra ({modulo}).
          </p>
        </div>
      )}

      {!stockQuery.isLoading && !stockQuery.isError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nº</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">U.M.</th>
                <th className="px-4 py-3">Stock Actual</th>
                <th className="px-4 py-3">Stock Mínimo</th>
                <th className="px-4 py-3">Alerta Stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(stockQuery.data ?? []).map((row, index) => {
                const level = stockLevel(row)
                return (
                  <tr key={row.material_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                      {index + 1}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700">
                      {row.codigo ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.descripcion}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {row.u_m ?? '—'}
                    </td>
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
          {(stockQuery.data ?? []).length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin materiales en el inventario {modulo}.
            </p>
          )}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Lectura directa del contrato real: el inventario{' '}
        <span className="font-mono">{modulo}</span> se consume vía{' '}
        <span className="font-mono">/fibra/&lt;modulo&gt;</span>. Las
        transferencias se realizan en la página Transferencias (TEAMS/DEVOL).
      </p>
    </div>
  )
}
