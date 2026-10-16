import { useState } from 'react'
import type { FormEvent } from 'react'
import { cerrarSeguimientoSchema } from '../schemas/seguimiento'
import type { CerrarSeguimientoPayload, SeguimientoItem } from '../types'

// ============================================================================
// FORMULARIO — CIERRE DE SEGUIMIENTO (CONSUMO) (FASE 7)
//
// Una fila por ítem: descripción y cantidad tomada SOLO LECTURA; el único
// campo editable es `cantidad_consumida`: inicia VACÍO y su captura es
// OBLIGATORIA para cada material (rango 0..tomada). El formulario NUNCA
// calcula stock: el descuento es exclusivo del backend (PostgreSQL).
// Captura la intención y la valida con `cerrarSeguimientoSchema`; el
// backend sigue siendo la autoridad.
//
// Contrato de props (wave 2b — página InventarioPorEquipos):
//   { items, materiales, onSubmit, onCancel }
//   `materiales` = mapa material_id → descripción (solo etiquetas).
// ============================================================================

interface SeguimientoCierreFormProps {
  items: SeguimientoItem[]
  materiales: Record<number, string>
  onSubmit: (payload: CerrarSeguimientoPayload) => void
  onCancel: () => void
}

export default function SeguimientoCierreForm({
  items,
  materiales,
  onSubmit,
  onCancel,
}: SeguimientoCierreFormProps) {
  // estado por material_id: string editable del consumido (inicia vacío)
  const [consumidos, setConsumidos] = useState<Record<number, string>>(() => {
    const inicial: Record<number, string> = {}
    for (const item of items) {
      inicial[item.material_id] = ''
    }
    return inicial
  })
  const [observacionesCierre, setObservacionesCierre] = useState('')
  const [errores, setErrores] = useState<string[]>([])

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    // Captura obligatoria: ningún campo puede quedar vacío.
    const faltantes = items.filter(
      (item) => (consumidos[item.material_id] ?? '').trim() === '',
    )
    if (faltantes.length > 0) {
      setErrores(
        faltantes.map(
          (item) =>
            `Indique la cantidad consumida de ${materiales[item.material_id] ?? item.material_id}.`,
        ),
      )
      return
    }

    // Guardia de presentación por fila: 0 <= consumido <= cantidad tomada.
    for (const item of items) {
      const cantidad = Number(consumidos[item.material_id])
      if (Number.isFinite(cantidad) && cantidad > item.cantidad_tomada) {
        setErrores([
          `El consumido no puede exceder la cantidad tomada (${item.cantidad_tomada}).`,
        ])
        return
      }
    }

    const payload: CerrarSeguimientoPayload = {
      consumidos: items.map((item) => ({
        material_id: item.material_id,
        cantidad_consumida: Number(consumidos[item.material_id]),
      })),
    }
    if (observacionesCierre.trim() !== '') {
      payload.observaciones_cierre = observacionesCierre.trim()
    }

    const resultado = cerrarSeguimientoSchema.safeParse(payload)
    if (!resultado.success) {
      const mensajes: string[] = []
      for (const issue of resultado.error.issues) {
        if (issue.message.includes('duplicado')) {
          mensajes.push(issue.message)
        } else if (issue.path[2] === 'cantidad_consumida') {
          mensajes.push(
            'El consumido debe ser un número mayor o igual a 0, con máximo 3 decimales.',
          )
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

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="space-y-2 border-t border-slate-200 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Consumido por material
        </p>
        <p className="text-xs text-slate-500">
          Indique cuánto consumió de cada material. El backend descuenta esa
          cantidad del inventario de la unidad y lo audita al cerrar.
        </p>

        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
          >
            <div className="flex-1">
              <p className="text-sm text-slate-700">
                {materiales[item.material_id] ?? item.material_id}
              </p>
              <p className="text-xs text-slate-500">
                Cantidad tomada:{' '}
                <span className="font-medium text-slate-700">
                  {item.cantidad_tomada.toLocaleString('es-MX')}
                </span>
              </p>
            </div>
            <div className="w-28">
              <label
                htmlFor={`consumido-${item.material_id}`}
                className="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                Consumido
              </label>
              <input
                id={`consumido-${item.material_id}`}
                type="number"
                min={0}
                max={item.cantidad_tomada}
                step={0.001}
                inputMode="decimal"
                required
                value={consumidos[item.material_id] ?? ''}
                onChange={(event) => {
                  setConsumidos({
                    ...consumidos,
                    [item.material_id]: event.target.value,
                  })
                  setErrores([])
                }}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        ))}
      </div>

      <div>
        <label
          htmlFor="cierre-observaciones"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Observaciones del cierre (opcional)
        </label>
        <textarea
          id="cierre-observaciones"
          value={observacionesCierre}
          onChange={(event) => setObservacionesCierre(event.target.value)}
          rows={2}
          placeholder="Ej. Trabajo concluido sin incidencias"
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
          Cerrar Seguimiento
        </button>
      </div>
    </form>
  )
}
