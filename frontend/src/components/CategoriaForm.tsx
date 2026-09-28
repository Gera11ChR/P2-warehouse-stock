import { useState } from 'react'
import type { FormEvent } from 'react'
import { nombreSchema } from '../schemas/catalogo'

// ============================================================================
// FORMULARIO — RENOMBRAR CATEGORÍA / UNIDAD DE MEDIDA (FASE 7)
//
// Form genérico de un solo campo (nombre 1–100 caracteres). Se reutiliza
// para categorías y unidades de medida: el título y la etiqueta los decide
// la página; el payload SIEMPRE es { nombre }. Validación UX con
// `nombreSchema`; la autoridad del contrato sigue siendo el backend.
//
// Contrato de props (wave 2b — páginas de administración de catálogo):
//   { titulo, labelNombre, initial, onSubmit, onCancel }
// ============================================================================

interface CategoriaFormProps {
  titulo: string
  labelNombre: string
  initial: { id: number; nombre: string }
  onSubmit: (payload: { nombre: string }) => void
  onCancel: () => void
}

export default function CategoriaForm({
  titulo,
  labelNombre,
  initial,
  onSubmit,
  onCancel,
}: CategoriaFormProps) {
  const [nombre, setNombre] = useState(initial.nombre)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    const resultado = nombreSchema.safeParse({ nombre: nombre.trim() })
    if (!resultado.success) {
      const primerIssue = resultado.error.issues[0]
      if (primerIssue?.code === 'too_small') {
        setError('El nombre es obligatorio.')
      } else if (primerIssue?.code === 'too_big') {
        setError('El nombre no puede exceder 100 caracteres.')
      } else {
        setError(primerIssue?.message ?? 'Nombre inválido.')
      }
      return
    }

    setError(null)
    onSubmit(resultado.data)
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {titulo !== '' && (
        <h3 className="text-sm font-semibold text-slate-800">{titulo}</h3>
      )}

      <div>
        <label
          htmlFor="categoria-form-nombre"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          {labelNombre}
        </label>
        <input
          id="categoria-form-nombre"
          type="text"
          value={nombre}
          onChange={(event) => {
            setNombre(event.target.value)
            if (error) setError(null)
          }}
          maxLength={100}
          className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
            error ? 'border-red-400' : 'border-slate-300'
          }`}
        />
        {error && (
          <p className="mt-1 text-xs font-medium text-red-600" role="alert">
            {error}
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
          Guardar
        </button>
      </div>
    </form>
  )
}
