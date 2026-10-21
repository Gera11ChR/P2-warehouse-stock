import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import {
  useCrearReferencia,
  useOpcionesOrigenReferencia,
} from '../hooks/useReferencia'
import { queryKeys } from '../hooks/queryKeys'
import { mensajeErrorApi } from '../utils/errorMensaje'
import { extraerRespuestaError } from '../utils/operadorErrores'
import { mensajeCantidadInvalida, validarCantidad } from '../utils/cantidad'
import MaterialSelect from './MaterialSelect'
import {
  ORIGEN_ETIQUETA,
  claveOpcion,
} from '../utils/referenciaOrigen'
import type {
  OpcionMaterial,
  OrigenReferencia,
} from '../utils/referenciaOrigen'
import type { ReferenciaCreatePayload } from '../types'

// ============================================================================
// FORMULARIO «+ AGREGAR» DE LA REFERENCIA (REQ-REF-006/007/013, T9)
//
// Cada línea elige SU origen («Inventario General» / «Inventario FO»; Q3),
// luego el material de ese origen y la «Cantidad». Cambiar el origen reinicia
// el material de la línea. Confirmar envía TODAS las líneas en una sola
// petición (todo o nada, 1..50). El origen NO forma parte del contrato; la
// cantidad es visual: no afecta el inventario (RN-5).
//
// Guardias de presentación (la autoridad es el backend): al menos una línea,
// material elegido, cantidad > 0 con ≤ 3 decimales y sin materiales repetidos
// ni ya presentes en la Referencia. Ante un rechazo del backend se CONSERVAN
// los datos capturados; ante 409 `REFERENCIA_DUPLICADA` además se refresca el
// listado de la Referencia.
// ============================================================================

const MAX_LINEAS = 50

interface LineaForm {
  key: number
  origen: OrigenReferencia
  material: OpcionMaterial | null
  cantidad: string
}

interface ErroresLinea {
  material?: string
  cantidad?: string
}

interface ReferenciaAgregarFormProps {
  equipoId: number
  /** Materiales que ya forman parte de la Referencia (no se ofrecen). */
  existentes: ReadonlySet<number>
  onCerrar: () => void
}

/** `cuerpo.error.code` de un error HTTP (o undefined). */
function codigoDeError(error: unknown): string | undefined {
  const { cuerpo } = extraerRespuestaError(error)
  if (typeof cuerpo === 'object' && cuerpo !== null && 'error' in cuerpo) {
    const interno = (cuerpo as { error?: unknown }).error
    if (typeof interno === 'object' && interno !== null && 'code' in interno) {
      const code = (interno as { code?: unknown }).code
      return typeof code === 'string' ? code : undefined
    }
  }
  return undefined
}

export default function ReferenciaAgregarForm({
  equipoId,
  existentes,
  onCerrar,
}: ReferenciaAgregarFormProps) {
  const queryClient = useQueryClient()
  const crear = useCrearReferencia(equipoId)
  const origenes = useOpcionesOrigenReferencia(true)

  const siguienteKey = useRef(1)
  const [lineas, setLineas] = useState<LineaForm[]>([
    { key: 0, origen: 'general', material: null, cantidad: '' },
  ])
  const [errores, setErrores] = useState<Record<number, ErroresLinea>>({})
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)

  const primerOrigenRef = useRef<HTMLSelectElement>(null)
  useEffect(() => {
    primerOrigenRef.current?.focus()
  }, [])

  const actualizar = (key: number, cambios: Partial<LineaForm>) => {
    setLineas((actuales) =>
      actuales.map((linea) =>
        linea.key === key ? { ...linea, ...cambios } : linea,
      ),
    )
  }

  const limpiarError = (key: number, campo: keyof ErroresLinea) => {
    setErrores((actuales) => {
      if (!actuales[key]?.[campo]) return actuales
      return { ...actuales, [key]: { ...actuales[key], [campo]: undefined } }
    })
  }

  const agregarLinea = () => {
    // La clave se toma FUERA del actualizador: en StrictMode los
    // actualizadores se ejecutan dos veces y mutar la referencia dentro de
    // uno de ellos consumiría dos claves por línea.
    const key = siguienteKey.current++
    setLineas((actuales) =>
      actuales.length >= MAX_LINEAS
        ? actuales
        : [...actuales, { key, origen: 'general', material: null, cantidad: '' }],
    )
  }

  const quitarLinea = (key: number) => {
    setLineas((actuales) =>
      actuales.length <= 1
        ? actuales
        : actuales.filter((linea) => linea.key !== key),
    )
    setErrores((actuales) => {
      const { [key]: _omitida, ...resto } = actuales
      void _omitida
      return resto
    })
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    setErrorGeneral(null)

    const nuevos: Record<number, ErroresLinea> = {}
    const payload: ReferenciaCreatePayload = { lineas: [] }
    const vistos = new Set<number>()
    for (const linea of lineas) {
      const errorLinea: ErroresLinea = {}
      const materialId = linea.material?.material_id
      if (materialId === undefined) {
        errorLinea.material = 'Seleccione un material.'
      } else if (existentes.has(materialId)) {
        errorLinea.material = 'Ese material ya está en la Referencia.'
      } else if (vistos.has(materialId)) {
        errorLinea.material = 'Ese material está repetido en otra línea.'
      } else {
        vistos.add(materialId)
      }
      const cantidad = validarCantidad(linea.cantidad)
      if (!cantidad.ok) {
        errorLinea.cantidad = mensajeCantidadInvalida(cantidad.motivo)
      }
      if (errorLinea.material || errorLinea.cantidad) {
        nuevos[linea.key] = errorLinea
      } else if (materialId !== undefined && cantidad.ok) {
        payload.lineas.push({
          material_id: materialId,
          cantidad_semanal: cantidad.cantidad,
        })
      }
    }
    setErrores(nuevos)
    if (Object.keys(nuevos).length > 0) {
      setErrorGeneral('Revisa las líneas marcadas antes de confirmar.')
      return
    }

    crear.mutate(payload, {
      onSuccess: onCerrar,
      onError: (error) => {
        // Se conservan los datos capturados (REQ-REF-013).
        if (codigoDeError(error) === 'REFERENCIA_DUPLICADA') {
          void queryClient.invalidateQueries({
            queryKey: queryKeys.referencia(equipoId),
          })
          setErrorGeneral(
            'Alguno de los materiales ya está en la Referencia; se actualizó la lista. Quita o cambia esa línea.',
          )
          return
        }
        setErrorGeneral(
          mensajeErrorApi(error, 'No se pudo agregar a la Referencia de la Unidad'),
        )
      },
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Agregar materiales a la Referencia"
      noValidate
      className="mt-4 space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4"
    >
      <p className="text-sm text-slate-600">
        La cantidad es solo una referencia visual y no afecta el inventario.
      </p>

      {lineas.map((linea, indice) => {
        const prefijo = `ref-linea-${linea.key}`
        const exclusion = new Set<number>(existentes)
        for (const otra of lineas) {
          if (otra.key !== linea.key && otra.material) {
            exclusion.add(otra.material.material_id)
          }
        }
        const errorLinea = errores[linea.key] ?? {}
        return (
          <div
            key={linea.key}
            role="group"
            aria-label={`Línea ${indice + 1}`}
            className="space-y-3 rounded-md border border-slate-200 bg-white p-3"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Línea {indice + 1}
              </p>
              <button
                type="button"
                onClick={() => quitarLinea(linea.key)}
                disabled={lineas.length <= 1}
                aria-label={`Quitar línea ${indice + 1}`}
                className="rounded-md p-1 text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div>
              <label
                htmlFor={`${prefijo}-origen`}
                className="text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                Origen
              </label>
              <select
                id={`${prefijo}-origen`}
                ref={indice === 0 ? primerOrigenRef : undefined}
                value={linea.origen}
                onChange={(event) =>
                  // Cambiar el origen reinicia el material (REQ-REF-013).
                  actualizar(linea.key, {
                    origen: event.target.value as OrigenReferencia,
                    material: null,
                  })
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="general">{ORIGEN_ETIQUETA.general}</option>
                <option value="fo">{ORIGEN_ETIQUETA.fo}</option>
              </select>
            </div>

            <MaterialSelect
              id={`${prefijo}-material`}
              origen={linea.origen}
              estado={linea.origen === 'general' ? origenes.general : origenes.fo}
              excluidos={exclusion}
              value={linea.material ? claveOpcion(linea.material) : ''}
              onChange={(opcion) => {
                actualizar(linea.key, { material: opcion })
                limpiarError(linea.key, 'material')
              }}
              error={errorLinea.material ?? null}
            />

            <div>
              <label
                htmlFor={`${prefijo}-cantidad`}
                className="text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                Cantidad
              </label>
              <input
                id={`${prefijo}-cantidad`}
                type="text"
                inputMode="decimal"
                autoComplete="off"
                spellCheck={false}
                value={linea.cantidad}
                aria-invalid={Boolean(errorLinea.cantidad)}
                aria-describedby={`${prefijo}-cantidad-ayuda`}
                onChange={(event) => {
                  actualizar(linea.key, { cantidad: event.target.value })
                  limpiarError(linea.key, 'cantidad')
                }}
                className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
                  errorLinea.cantidad ? 'border-red-400' : 'border-slate-300'
                }`}
              />
              <p
                id={`${prefijo}-cantidad-ayuda`}
                className={`mt-1 text-xs ${
                  errorLinea.cantidad
                    ? 'font-medium text-red-600'
                    : 'text-slate-500'
                }`}
              >
                {errorLinea.cantidad ??
                  'Número mayor que 0, hasta 3 decimales (por ejemplo 2.5).'}
              </p>
            </div>
          </div>
        )
      })}

      <button
        type="button"
        onClick={agregarLinea}
        disabled={lineas.length >= MAX_LINEAS}
        className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Plus className="h-4 w-4" aria-hidden="true" /> Agregar línea
      </button>

      {errorGeneral && (
        <p role="alert" className="text-sm font-medium text-red-600">
          {errorGeneral}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={onCerrar}
          disabled={crear.isPending}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-white"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={crear.isPending}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {crear.isPending && (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          )}
          Confirmar
        </button>
      </div>
    </form>
  )
}
