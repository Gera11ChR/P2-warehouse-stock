import { useState } from 'react'
import type { FormEvent } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { despliegueCreateSchema } from '../schemas/despliegue'
import type { DespliegueCreatePayload, InventarioEquipoRow } from '../types'

// ============================================================================
// FORMULARIO — NUEVA LISTA DE DESPLIEGUE (FASE 7, apertura)
//
// Editor de líneas (carrito temporal, SOLO UX): cada línea es
// material_id + cantidad_tomada. El `max` por línea es una GUARDIA DE
// PRESENTACIÓN (stock_actual > 0 del inventario del equipo); la autoridad
// del contrato sigue siendo el backend (validación Pydantic + PostgreSQL).
// El formulario NUNCA descuenta stock: captura la intención y la valida
// con `despliegueCreateSchema` (mín. 1 línea, positivos, sin duplicados).
//
// Contrato de props (wave 2b — página InventarioPorEquipos):
//   { materiales, onSubmit, onCancel }
// ============================================================================

interface DespliegueLinea {
  materialId: number | null
  cantidad: string
}

interface DespliegueNuevaListaFormProps {
  materiales: InventarioEquipoRow[]
  onSubmit: (payload: DespliegueCreatePayload) => void
  onCancel: () => void
}

export default function DespliegueNuevaListaForm({
  materiales,
  onSubmit,
  onCancel,
}: DespliegueNuevaListaFormProps) {
  const [lineas, setLineas] = useState<DespliegueLinea[]>([])
  const [observaciones, setObservaciones] = useState('')
  const [errores, setErrores] = useState<string[]>([])

  // Solo materiales con stock real (REQ-DOMAIN-001/002: sin fantasmas).
  const materialesDisponibles = materiales.filter((m) => m.stock_actual > 0)

  const idsUsados = lineas
    .map((l) => l.materialId)
    .filter((id): id is number => id !== null)

  const stockDe = (materialId: number | null): number => {
    if (materialId === null) return 0
    return (
      materiales.find((m) => m.material_id === materialId)?.stock_actual ?? 0
    )
  }

  const handleAgregarLinea = () => {
    setLineas([...lineas, { materialId: null, cantidad: '1' }])
    setErrores([])
  }

  const handleQuitarLinea = (index: number) => {
    setLineas(lineas.filter((_, i) => i !== index))
    setErrores([])
  }

  const handleCambiarLinea = (
    index: number,
    cambios: Partial<DespliegueLinea>,
  ) => {
    setLineas(
      lineas.map((linea, i) => (i === index ? { ...linea, ...cambios } : linea)),
    )
    setErrores([])
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    // Guardia de presentación por línea: la cantidad nunca excede el stock
    // disponible del material (el backend revalida el contrato).
    for (const linea of lineas) {
      if (linea.materialId === null) continue
      const cantidad = Number(linea.cantidad)
      if (Number.isFinite(cantidad) && cantidad > stockDe(linea.materialId)) {
        setErrores([
          `La cantidad excede el stock disponible del material seleccionado (${stockDe(linea.materialId)}).`,
        ])
        return
      }
    }

    const payload: DespliegueCreatePayload = {
      items: lineas.map((linea) => ({
        material_id: linea.materialId ?? 0,
        cantidad_tomada: Number(linea.cantidad) || 0,
      })),
    }
    if (observaciones.trim() !== '') {
      payload.observaciones = observaciones.trim()
    }

    const resultado = despliegueCreateSchema.safeParse(payload)
    if (!resultado.success) {
      const mensajes: string[] = []
      for (const issue of resultado.error.issues) {
        if (issue.message.includes('duplicado')) {
          mensajes.push(issue.message)
        } else if (
          issue.path.length === 1 &&
          issue.path[0] === 'items' &&
          issue.code === 'too_small'
        ) {
          mensajes.push('Agregue al menos una línea al despliegue.')
        } else if (issue.path[2] === 'material_id') {
          mensajes.push('Seleccione un material válido para cada línea.')
        } else if (issue.path[2] === 'cantidad_tomada') {
          mensajes.push('La cantidad debe ser un entero positivo en cada línea.')
        } else {
          mensajes.push(issue.message)
        }
      }
      setErrores(mensajes)
      return
    }

    setErrores([])
    onSubmit(resultado.data)
  }

  if (materialesDisponibles.length === 0) {
    return (
      <div className="space-y-4">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-center">
          <p className="text-sm text-slate-600">
            El equipo no tiene materiales con stock.
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Cancelar
          </button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="space-y-2 border-t border-slate-200 pt-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Materiales a desplegar
          </label>
          <span className="text-xs text-slate-500">
            Líneas: {lineas.length}
          </span>
        </div>

        {lineas.length === 0 && (
          <p className="text-xs text-slate-500">
            No hay líneas agregadas. Agregue al menos una línea para abrir la
            lista.
          </p>
        )}

        {lineas.map((linea, index) => {
          const cantidadNum = Number(linea.cantidad)
          const stockLinea = stockDe(linea.materialId)
          const excede =
            linea.materialId !== null &&
            Number.isFinite(cantidadNum) &&
            cantidadNum > stockLinea
          return (
            <div
              key={index}
              className="flex items-end gap-2 rounded-md border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex-1">
                <label
                  htmlFor={`despliegue-material-${index}`}
                  className="text-xs font-semibold uppercase tracking-wide text-slate-400"
                >
                  Material
                </label>
                <select
                  id={`despliegue-material-${index}`}
                  value={linea.materialId ?? ''}
                  onChange={(event) =>
                    handleCambiarLinea(index, {
                      materialId:
                        event.target.value === ''
                          ? null
                          : Number(event.target.value),
                    })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">— Seleccione material —</option>
                  {materialesDisponibles.map((m) => (
                    <option
                      key={m.material_id}
                      value={m.material_id}
                      disabled={idsUsados.includes(m.material_id)}
                    >
                      {m.descripcion} ({m.stock_actual})
                    </option>
                  ))}
                </select>
              </div>

              <div className="w-32">
                <label
                  htmlFor={`despliegue-cantidad-${index}`}
                  className="text-xs font-semibold uppercase tracking-wide text-slate-400"
                >
                  Cantidad
                </label>
                <input
                  id={`despliegue-cantidad-${index}`}
                  type="number"
                  min={1}
                  max={stockDe(linea.materialId)}
                  step={1}
                  value={linea.cantidad}
                  onChange={(event) =>
                    handleCambiarLinea(index, { cantidad: event.target.value })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                />
                {excede && (
                  <p className="mt-1 text-xs font-medium text-red-600">
                    Máx. {stockLinea}
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => handleQuitarLinea(index)}
                className="rounded-md border border-slate-300 p-2 text-red-600 hover:bg-red-50 hover:text-red-800"
                title="Quitar línea"
                aria-label={`Quitar línea ${index + 1}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )
        })}

        <button
          type="button"
          onClick={handleAgregarLinea}
          className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
        >
          <Plus className="h-4 w-4" /> Agregar línea
        </button>
      </div>

      <div>
        <label
          htmlFor="despliegue-observaciones"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Observaciones (opcional)
        </label>
        <textarea
          id="despliegue-observaciones"
          value={observaciones}
          onChange={(event) => setObservaciones(event.target.value)}
          maxLength={2000}
          rows={2}
          placeholder="Ej. Despliegue para obra en Zona Norte"
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      {errores.length > 0 && (
        <div className="space-y-1 rounded-md border border-red-200 bg-red-50 p-3">
          {errores.map((mensaje, index) => (
            <p
              key={index}
              className="text-xs font-medium text-red-600"
              role="alert"
            >
              {mensaje}
            </p>
          ))}
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
          Crear Despliegue
        </button>
      </div>
    </form>
  )
}
