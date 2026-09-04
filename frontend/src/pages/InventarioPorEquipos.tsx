import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Plus, Trash2, Pencil } from 'lucide-react'
import {
  createTeamInventory,
  deleteTeamInventory,
  listTeamInventory,
  updateTeamInventory,
} from '../services/teamInventory'
import { listMaterials } from '../services/materials'
import { useToast } from '../hooks/useToasts'
import type { Material, TeamInventoryItem } from '../types'

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString('es-MX')
}

export default function InventarioPorEquipos() {
  const { pushToast, pushError } = useToast()
  const [items, setItems] = useState<TeamInventoryItem[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [equipo, setEquipo] = useState('')
  const [usuario, setUsuario] = useState('')
  const [codigo, setCodigo] = useState('')
  const [cantidad, setCantidad] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)

  const refresh = () => {
    listTeamInventory().then(setItems)
  }

  useEffect(() => {
    refresh()
    listMaterials().then(setMaterials)
  }, [])

  const descripcion = useMemo(() => {
    const material = materials.find((m) => m.codigo === codigo)
    return material?.descripcion ?? null
  }, [materials, codigo])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!equipo || !usuario || !codigo || cantidad === '') {
      return
    }
    try {
      if (editingId === null) {
        await createTeamInventory({
          equipo,
          usuario,
          codigo,
          cantidad: Number(cantidad),
        })
        pushToast('Asignación creada')
      } else {
        await updateTeamInventory(editingId, {
          equipo,
          usuario,
          cantidad: Number(cantidad),
        })
        pushToast('Asignación modificada')
      }
      setEquipo('')
      setUsuario('')
      setCodigo('')
      setCantidad('')
      setEditingId(null)
      refresh()
    } catch {
      pushError('No se pudo guardar la asignación')
    }
  }

  const handleEdit = (item: TeamInventoryItem) => {
    setEditingId(item.id)
    setEquipo(item.equipo)
    setUsuario(item.usuario)
    setCodigo(item.codigo)
    setCantidad(String(item.cantidad))
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteTeamInventory(id)
      pushToast('Asignación eliminada')
      refresh()
    } catch {
      pushError('No se pudo eliminar la asignación')
    }
  }

  return (
    <div className="space-y-4">
      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-5"
      >
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Equipo
          </label>
          <input
            type="text"
            value={equipo}
            onChange={(event) => setEquipo(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Usuario
          </label>
          <input
            type="text"
            value={usuario}
            onChange={(event) => setUsuario(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Código SKU
          </label>
          <input
            type="text"
            value={codigo}
            disabled={editingId !== null}
            onChange={(event) => setCodigo(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm disabled:bg-slate-100"
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Descripción
          </label>
          <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">
            {descripcion ?? '—'}
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Cantidad
          </label>
          <input
            type="number"
            min={1}
            value={cantidad}
            onChange={(event) => setCantidad(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          className="col-span-2 mt-1 flex items-center justify-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 md:col-span-5"
        >
          <Plus className="h-4 w-4" />
          {editingId === null ? 'Asignar' : 'Actualizar'}
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Equipo</th>
              <th className="px-4 py-3">Usuario</th>
              <th className="px-4 py-3">Código SKU</th>
              <th className="px-4 py-3">Descripción</th>
              <th className="px-4 py-3">Cantidad</th>
              <th className="px-4 py-3">Última Modificación</th>
              <th className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3 text-slate-700">{item.equipo}</td>
                <td className="px-4 py-3 text-slate-700">{item.usuario}</td>
                <td className="px-4 py-3 font-mono text-slate-700">{item.codigo}</td>
                <td className="px-4 py-3 text-slate-700">
                  {item.descripcion ?? '—'}
                </td>
                <td className="px-4 py-3 text-slate-700">{item.cantidad}</td>
                <td className="px-4 py-3 text-slate-500">
                  {formatTimestamp(item.ultima_modificacion)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleEdit(item)}
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                      aria-label="Modificar"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(item.id)}
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-red-600"
                      aria-label="Eliminar"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
