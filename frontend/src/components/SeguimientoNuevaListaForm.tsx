import { useState } from 'react'
import type { FormEvent } from 'react'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { seguimientoCreateSchema } from '../schemas/seguimiento'
import {
  calcularAgregarTodo,
  mensajeAgregarTodo,
} from '../utils/agregarTodo'
import type {
  AgregarTodoResultado,
  SeguimientoLinea,
} from '../utils/agregarTodo'
import type { InventarioEquipoRow, SeguimientoCreatePayload } from '../types'

// ============================================================================
// FORMULARIO — NUEVA LISTA DE SEGUIMIENTO (CONSUMO) (FASE 7, apertura)
//
// Editor de líneas (carrito temporal, SOLO UX): cada línea es
// material_id + cantidad_tomada. El `max` por línea es una GUARDIA DE
// PRESENTACIÓN (stock_actual > 0 del inventario del equipo); la autoridad
// del contrato sigue siendo el backend (validación Pydantic + PostgreSQL).
// El formulario NUNCA descuenta stock: captura la intención y la valida
// con `seguimientoCreateSchema` (mín. 1 línea, positivos, sin duplicados).
//
// "+ Agregar todo" (REQ-P2-CON-003/004) — DECISIÓN DE FLUJO (T4.2):
// la lista se arma ANTES de crear el seguimiento, y el endpoint
// POST /equipos/{id}/seguimientos/{seguimiento_id}/agregar-todo opera sobre
// un seguimiento ABIERTA ya creado. Por eso, en este flujo, "Agregar todo"
// precarga LOCALMENTE el borrador desde el inventario del equipo ya
// disponible en el cliente (prop `materiales`), sin red. Mismo contrato que
// el SP (solo agrega los faltantes, no duplica, no pisa cantidades). El
// borrador se valida y persiste al "Crear Seguimiento" (autoridad: backend).
//
// Contrato de props:
//   { materiales, onSubmit, onCancel,
//     editable?, isLoading?, onAgregarTodo?, titulo? }
//  - editable (def. true): false → "Agregar todo" deshabilitado con motivo.
//  - isLoading: el inventario se está refrescando; bloquea "Agregar todo"
//    para no precargar con stock obsoleto.
//  - onAgregarTodo: callback informativo tras la precarga local (no es
//    requerido para que el flujo funcione).
// El endpoint agregar-todo ya está expuesto en la capa de estado
// (services/seguimientos.agregarTodoSeguimiento + useAgregarTodoSeguimiento)
// pero NO se monta aquí: solo aplicaría a la edición de un seguimiento ABIERTO
// existente (hoy sin pantalla). "Nueva lista" usa la precarga local.
// ============================================================================

interface SeguimientoNuevaListaFormProps {
  materiales: InventarioEquipoRow[]
  onSubmit: (payload: SeguimientoCreatePayload) => void
  onCancel: () => void
  titulo?: string
  editable?: boolean
  isLoading?: boolean
  onAgregarTodo?: (resultado: AgregarTodoResultado) => void
}

export default function SeguimientoNuevaListaForm({
  materiales,
  onSubmit,
  onCancel,
  titulo = 'Nueva lista de seguimiento',
  editable = true,
  isLoading = false,
  onAgregarTodo,
}: SeguimientoNuevaListaFormProps) {
  const [lineas, setLineas] = useState<SeguimientoLinea[]>([])
  const [observaciones, setObservaciones] = useState('')
  const [errores, setErrores] = useState<string[]>([])
  const [aviso, setAviso] = useState<string | null>(null)

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

  const sinStock = materialesDisponibles.length === 0
  const agregarTodoBloqueo: string | null = !editable
    ? 'La lista ya no admite cambios.'
    : sinStock
      ? 'El equipo no tiene materiales con stock.'
      : isLoading
        ? 'Actualizando el inventario del equipo…'
        : null

  const handleAgregarTodo = () => {
    if (agregarTodoBloqueo !== null) return
    const resultado = calcularAgregarTodo(lineas, materiales)
    setLineas(resultado.lineas)
    setErrores([])
    setAviso(mensajeAgregarTodo(resultado))
    onAgregarTodo?.(resultado)
  }

  const handleAgregarLinea = () => {
    setLineas([...lineas, { materialId: null, cantidad: '1' }])
    setErrores([])
    setAviso(null)
  }

  const handleQuitarLinea = (index: number) => {
    setLineas(lineas.filter((_, i) => i !== index))
    setErrores([])
    setAviso(null)
  }

  const handleCambiarLinea = (
    index: number,
    cambios: Partial<SeguimientoLinea>,
  ) => {
    setLineas(
      lineas.map((linea, i) => (i === index ? { ...linea, ...cambios } : linea)),
    )
    setErrores([])
    setAviso(null)
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

    const payload: SeguimientoCreatePayload = {
      items: lineas.map((linea) => ({
        material_id: linea.materialId ?? 0,
        cantidad_tomada: Number(linea.cantidad) || 0,
      })),
    }
    if (observaciones.trim() !== '') {
      payload.observaciones = observaciones.trim()
    }

    const resultado = seguimientoCreateSchema.safeParse(payload)
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
          mensajes.push('Agregue al menos una línea al seguimiento.')
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

  const cabecera = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-base font-semibold text-slate-800">{titulo}</h3>
      <button
        type="button"
        onClick={handleAgregarTodo}
        disabled={agregarTodoBloqueo !== null}
        aria-busy={isLoading}
        aria-describedby="seguimiento-agregar-todo-ayuda"
        title={agregarTodoBloqueo ?? undefined}
        className="flex items-center gap-1 rounded-md border border-green-600 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Plus className="h-4 w-4" aria-hidden="true" />
        )}{' '}
        Agregar todo
      </button>
      <span id="seguimiento-agregar-todo-ayuda" className="sr-only">
        {agregarTodoBloqueo
          ? `Agregar todo no está disponible. ${agregarTodoBloqueo}`
          : 'Carga en la lista todos los materiales con stock del equipo sin duplicar los ya agregados.'}
      </span>
    </div>
  )

  if (sinStock) {
    return (
      <div className="space-y-4">
        {cabecera}
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
    <form onSubmit={handleSubmit} noValidate>
      <fieldset
        disabled={!editable}
        className="m-0 min-w-0 space-y-4 border-0 p-0"
      >
        {cabecera}
        {!editable && agregarTodoBloqueo && (
          <p className="text-xs text-slate-500">{agregarTodoBloqueo}</p>
        )}
        <div className="space-y-2 border-t border-slate-200 pt-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Materiales del seguimiento
            </label>
            <span className="text-xs text-slate-500">
              Líneas: {lineas.length}
            </span>
          </div>

          {lineas.length === 0 && (
            <p className="text-xs text-slate-500">
              No hay líneas agregadas. Agregue líneas una a una o use «Agregar
              todo» para cargar todo el stock del equipo.
            </p>
          )}

          {/* Región viva: anuncia el resultado de "Agregar todo" (idempotente). */}
          <div role="status" aria-live="polite">
            {aviso && (
              <p className="rounded-md border border-green-200 bg-green-50 p-2 text-xs font-medium text-green-800">
                {aviso}
              </p>
            )}
          </div>

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
                    htmlFor={`seguimiento-material-${index}`}
                    className="text-xs font-semibold uppercase tracking-wide text-slate-400"
                  >
                    Material
                  </label>
                  <select
                    id={`seguimiento-material-${index}`}
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
                    htmlFor={`seguimiento-cantidad-${index}`}
                    className="text-xs font-semibold uppercase tracking-wide text-slate-400"
                  >
                    Cantidad
                  </label>
                  <input
                    id={`seguimiento-cantidad-${index}`}
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
            htmlFor="seguimiento-observaciones"
            className="text-xs font-semibold uppercase tracking-wide text-slate-400"
          >
            Observaciones (opcional)
          </label>
          <textarea
            id="seguimiento-observaciones"
            value={observaciones}
            onChange={(event) => setObservaciones(event.target.value)}
            maxLength={2000}
            rows={2}
            placeholder="Ej. Seguimiento de consumo para obra en Zona Norte"
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
            Crear Seguimiento
          </button>
        </div>
      </fieldset>
    </form>
  )
}
