import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Categoria, Material, Seccion } from '../types'
import { UNIDADES } from '../types'
import type {
  MaterialCreatePayload,
  MaterialUpdatePayload,
} from '../services/catalog'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'

interface MaterialFormProps {
  mode: 'create' | 'edit'
  initial?: Material
  stockActual?: number
  alertaStock?: boolean
  categorias: Categoria[]
  secciones?: Seccion[]
  onSubmit: (
    payload: MaterialCreatePayload | MaterialUpdatePayload,
  ) => void | Promise<void>
  onCancel: () => void
}

export default function MaterialForm({
  mode,
  initial,
  stockActual = 0,
  alertaStock = false,
  categorias,
  secciones = [],
  onSubmit,
  onCancel,
}: MaterialFormProps) {
  const [descripcion, setDescripcion] = useState(initial?.descripcion ?? '')
  const [stockMinimo, setStockMinimo] = useState(
    initial?.stock_minimo != null ? String(initial.stock_minimo) : '',
  )
  const [u_m, setUm] = useState(initial?.u_m ?? '')
  const [codigo, setCodigo] = useState(initial?.codigo ?? '')

  // Selector dual: categoria_id XOR nueva_categoria
  const [categoriaMode, setCategoriaMode] = useState<'selector' | 'nueva'>(
    'selector',
  )
  const [categoriaId, setCategoriaId] = useState<number | null>(
    initial?.categoria_id ?? null,
  )
  const [nuevaCategoria, setNuevaCategoria] = useState('')

  // Carga inicial (solo create)
  const [stockInicial, setStockInicial] = useState('')
  const [seccionId, setSeccionId] = useState<number | null>(null)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    if (mode === 'create') {
      const payload: MaterialCreatePayload = {
        descripcion: descripcion || '',
        codigo: codigo || null,
        categoria_id: categoriaMode === 'selector' ? categoriaId : null,
        nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
        u_m: u_m || null,
        stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
        stock_inicial:
          stockInicial === '' ? null : Number(stockInicial),
        seccion_id: stockInicial === '' ? null : seccionId,
      }
      onSubmit(payload)
    } else {
      const payload: MaterialUpdatePayload = {
        descripcion: descripcion || null,
        codigo: codigo || null,
        categoria_id: categoriaMode === 'selector' ? categoriaId : null,
        nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
        u_m: u_m || null,
        stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
      }
      onSubmit(payload)
    }
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
          required
        />
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.stock_actual}
        </label>
        <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {stockActual.toLocaleString('es-MX')}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Solo lectura. Ajustes vía operaciones autorizadas (FASE 3).
        </p>
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
          {MATERIAL_FIELD_LABELS.u_m}
        </label>
        <select
          value={u_m}
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
          <div className="mt-2 flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={categoriaMode === 'selector'}
                onChange={() => setCategoriaMode('selector')}
              />
              <span>Selector</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={categoriaMode === 'nueva'}
                onChange={() => setCategoriaMode('nueva')}
              />
              <span>Nueva categoría</span>
            </label>
          </div>

          {categoriaMode === 'selector' ? (
            <select
              value={categoriaId ?? ''}
              onChange={(event) =>
                setCategoriaId(
                  event.target.value === '' ? null : Number(event.target.value),
                )
              }
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">— Sin categoría —</option>
              {categorias
                .filter((c) => c.is_active)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
            </select>
          ) : (
            <input
              type="text"
              value={nuevaCategoria}
              onChange={(event) => setNuevaCategoria(event.target.value)}
              placeholder="Nombre de la nueva categoría"
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          )}
        </div>
      </div>

      {mode === 'create' && (
        <div className="space-y-3 border-t border-slate-200 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Carga Inicial (opcional)
          </p>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Stock Inicial
            </label>
            <input
              type="number"
              min={0}
              value={stockInicial}
              onChange={(event) => setStockInicial(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          {stockInicial !== '' && Number(stockInicial) > 0 && (
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Sección destino *
              </label>
              <select
                value={seccionId ?? ''}
                onChange={(event) =>
                  setSeccionId(
                    event.target.value === ''
                      ? null
                      : Number(event.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              >
                <option value="">— Seleccione sección —</option>
                {secciones
                  .filter((s) => s.is_active)
                  .map((s) => (
                    <option key={s.almacen_id} value={s.almacen_id}>
                      {s.nombre}
                    </option>
                  ))}
              </select>
            </div>
          )}
        </div>
      )}

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
