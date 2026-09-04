import { useState } from 'react'
import type { FormEvent } from 'react'
import { Search } from 'lucide-react'
import { listInventory } from '../services/inventory'
import type { InventoryRow } from '../types'
import InventoryTable from './InventoryTable'

export default function BulkSearch() {
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault()
    if (!desde && !hasta) {
      return
    }
    setLoading(true)
    try {
      const items = await listInventory({ desde_sku: desde || undefined, hasta_sku: hasta || undefined })
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
            value={desde}
            onChange={(event) => setDesde(event.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Hasta SKU
          </label>
          <input
            type="text"
            value={hasta}
            onChange={(event) => setHasta(event.target.value)}
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
        <InventoryTable
          rows={rows}
          selectedCodigo={null}
          onSelect={() => undefined}
        />
      )}
    </div>
  )
}
