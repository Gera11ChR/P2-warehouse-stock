import { Plus, Pencil, Trash2, ArrowRightLeft } from 'lucide-react'

export interface FilterState {
  buscar: string
  categoria: string
  um: string
  almacen: string
}

interface FilterToolbarProps {
  filters: FilterState
  onChange: (filters: FilterState) => void
  categorias: string[]
  unidades: string[]
  almacenes: { id: string; name: string }[]
  onAgregar: () => void
  onModificar: () => void
  onEliminar: () => void
  onTransferir: () => void
}

export default function FilterToolbar({
  filters,
  onChange,
  categorias,
  unidades,
  almacenes,
  onAgregar,
  onModificar,
  onEliminar,
  onTransferir,
}: FilterToolbarProps) {
  const set = (key: keyof FilterState, value: string) =>
    onChange({ ...filters, [key]: value })

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <input
        type="text"
        value={filters.buscar}
        onChange={(event) => set('buscar', event.target.value)}
        placeholder="Buscar"
        className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
      />
      <select
        value={filters.categoria}
        onChange={(event) => set('categoria', event.target.value)}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="">Categoría</option>
        {categorias.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <select
        value={filters.um}
        onChange={(event) => set('um', event.target.value)}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="">U.M.</option>
        {unidades.map((u) => (
          <option key={u} value={u}>
            {u}
          </option>
        ))}
      </select>
      <select
        value={filters.almacen}
        onChange={(event) => set('almacen', event.target.value)}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="">Almacén</option>
        {almacenes.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onAgregar}
          className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
        >
          <Plus className="h-4 w-4" /> Agregar
        </button>
        <button
          type="button"
          onClick={onModificar}
          className="flex items-center gap-1 rounded-md bg-yellow-500 px-3 py-2 text-sm font-medium text-white hover:bg-yellow-600"
        >
          <Pencil className="h-4 w-4" /> Modificar
        </button>
        <button
          type="button"
          onClick={onEliminar}
          className="flex items-center gap-1 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          <Trash2 className="h-4 w-4" /> Eliminar
        </button>
        <button
          type="button"
          onClick={onTransferir}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <ArrowRightLeft className="h-4 w-4" /> Transferir Stock
        </button>
      </div>
    </div>
  )
}
