import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Material } from '../types'
import { TIPOS, UNIDADES } from '../types'
import type { MaterialPayload } from '../services/materials'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'

interface MaterialFormProps {
  mode: 'create' | 'edit'
  initial?: Material
  stockActual?: number
  alertaStock?: boolean
  onSubmit: (payload: MaterialPayload) => void
  onCancel: () => void
}

export default function MaterialForm({
  mode,
  initial,
  stockActual = 0,
  alertaStock = false,
  onSubmit,
  onCancel,
}: MaterialFormProps) {
  const [descripcion, setDescripcion] = useState(initial?.descripcion ?? '')
  const [stockMinimo, setStockMinimo] = useState(
    initial?.stock_minimo != null ? String(initial.stock_minimo) : '',
  )
  const [um, setUm] = useState(initial?.um ?? '')
  const [codigo, setCodigo] = useState(initial?.codigo ?? '')
  const [categoria, setCategoria] = useState(initial?.categoria ?? '')
  const [tipo, setTipo] = useState(initial?.tipo ?? 'GENERAL')

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const payload: MaterialPayload = {
      descripcion: descripcion || null,
      stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
      um: um || null,
      categoria: categoria || null,
      tipo,
    }
    if (mode === 'create') {
      payload.codigo = codigo
    }
    onSubmit(payload)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.descripcion}
        </label>
        <input
          type="text"
          value={descripcion}
          onChange={(event) => setDescripcion(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.stock_actual}
        </label>
        <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">
          {stockActual.toLocaleString('es-MX')}
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.stock_minimo}
        </label>
        <input
          type="number"
          min={0}
          value={stockMinimo}
          onChange={(event) => setStockMinimo(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.alerta_stock}
        </label>
        <div className="mt-1">
          {alertaStock ? (
            <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
              Alerta Stock
            </span>
          ) : (
            <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
              Sin alerta
            </span>
          )}
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.um}
        </label>
        <select
          value={um}
          onChange={(event) => setUm(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">—</option>
          {UNIDADES.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.codigo}
        </label>
        <input
          type="text"
          value={codigo}
          disabled={mode === 'edit'}
          onChange={(event) => setCodigo(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm disabled:bg-slate-100"
        />
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Clasificación
        </p>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Categoría
          </label>
          <input
            type="text"
            value={categoria}
            onChange={(event) => setCategoria(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Tipo
          </label>
          <select
            value={tipo}
            onChange={(event) => setTipo(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {t === 'FIBRA' ? 'Fibra Óptica' : 'General'}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          Cancelar
        </button>
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {mode === 'create' ? 'Agregar' : 'Guardar'}
        </button>
      </div>
    </form>
  )
}
