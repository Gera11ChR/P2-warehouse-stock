import { useState } from 'react'
import type { FormEvent } from 'react'
import { Search } from 'lucide-react'
import { listCatalog } from '../services/catalog'
import type { Material } from '../types'

export default function BulkSearch() {
  const [desdeSku, setDesdeSku] = useState('')
  const [hastaSku, setHastaSku] = useState('')
  const [desdeId, setDesdeId] = useState('')
  const [hastaId, setHastaId] = useState('')
  const [rows, setRows] = useState<Material[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault()
    if (!desdeSku && !hastaSku && !desdeId && !hastaId) {
      return
    }
    setLoading(true)
    try {
      const items = await listCatalog({
        desde_sku: desdeSku || undefined,
        hasta_sku: hastaSku || undefined,
        desde_id_lista: desdeId ? Number(desdeId) : undefined,
        hasta_id_lista: hastaId ? Number(hastaId) : undefined,
      })
      setRows(items)
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={handleSearch} className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Desde SKU
          </label>
          <input
            type="text"
            value={desdeSku}
            onChange={(event) => setDesdeSku(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Hasta SKU
          </label>
          <input
            type="text"
            value={hastaSku}
            onChange={(event) => setHastaSku(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Desde ID Lista
          </label>
          <input
            type="number"
            value={desdeId}
            onChange={(event) => setDesdeId(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Hasta ID Lista
          </label>
          <input
            type="number"
            value={hastaId}
            onChange={(event) => setHastaId(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Search className="h-4 w-4" /> Buscar
        </button>
      </form>
      {searched && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">ID Lista</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">Categoría</th>
                <th className="px-4 py-3">U.M.</th>
                <th className="px-4 py-3">Stock Mínimo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id_lista}>
                  <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                    {row.id_lista}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-700">
                    {row.codigo ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{row.descripcion}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {row.categoria ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{row.u_m ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {row.stock_minimo != null ? row.stock_minimo : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="p-3 text-xs text-slate-500">
            Búsqueda a granel sobre el catálogo. Stock actual disponible en vista
            por sección.
          </p>
        </div>
      )}
    </div>
  )
}
