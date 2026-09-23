import { useState } from 'react'
import type { FormEvent } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { Equipo } from '../types'
import type {
  EquipoCreatePayload,
  EquipoUpdatePayload,
} from '../services/equipos'

interface EquipoFormProps {
  mode: 'create' | 'edit'
  initial?: Equipo
  onSubmit: (payload: EquipoCreatePayload | EquipoUpdatePayload) => void | Promise<void>
  onCancel: () => void
}

export default function EquipoForm({
  mode,
  initial,
  onSubmit,
  onCancel,
}: EquipoFormProps) {
  const [nombre, setNombre] = useState(initial?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(initial?.descripcion ?? '')
  const [integrantes, setIntegrantes] = useState<string[]>(
    initial?.integrantes ?? [],
  )
  const [nuevoIntegrante, setNuevoIntegrante] = useState('')

  const handleAgregarIntegrante = () => {
    const trimmed = nuevoIntegrante.trim()
    if (trimmed && !integrantes.includes(trimmed)) {
      setIntegrantes([...integrantes, trimmed])
      setNuevoIntegrante('')
    }
  }

  const handleQuitarIntegrante = (index: number) => {
    setIntegrantes(integrantes.filter((_, i) => i !== index))
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (mode === 'create') {
      const payload: EquipoCreatePayload = {
        nombre: nombre.trim(),
        descripcion: descripcion.trim() || null,
        integrantes,
      }
      onSubmit(payload)
    } else {
      const payload: EquipoUpdatePayload = {
        nombre: nombre.trim() || null,
        descripcion: descripcion.trim() || null,
        integrantes,
      }
      onSubmit(payload)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700">
          Nombre de Cuadrilla *
        </label>
        <input
          type="text"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          required
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">
          Descripción
        </label>
        <textarea
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>

      <div className="space-y-2 border-t border-slate-200 pt-4">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-slate-700">
            Integrantes
          </label>
          <span className="text-xs text-slate-500">
            Cantidad: {integrantes.length}
          </span>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={nuevoIntegrante}
            onChange={(e) => setNuevoIntegrante(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleAgregarIntegrante()
              }
            }}
            placeholder="Nombre del integrante"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={handleAgregarIntegrante}
            className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            <Plus className="h-4 w-4" /> Agregar
          </button>
        </div>

        {integrantes.length > 0 && (
          <div className="mt-2 space-y-1 rounded-md border border-slate-200 bg-slate-50 p-2">
            {integrantes.map((integrante, index) => (
              <div
                key={index}
                className="flex items-center justify-between rounded bg-white px-3 py-2 text-sm"
              >
                <span className="text-slate-700">{integrante}</span>
                <button
                  type="button"
                  onClick={() => handleQuitarIntegrante(index)}
                  className="text-red-600 hover:text-red-800"
                  title="Quitar integrante"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {integrantes.length === 0 && (
          <p className="text-xs text-slate-500">
            No hay integrantes agregados. Use el campo arriba para agregar.
          </p>
        )}
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
          {mode === 'create' ? 'Crear Equipo' : 'Guardar Cambios'}
        </button>
      </div>
    </form>
  )
}
