import { useState } from 'react'
import type {
  EstadoOrigenOpciones,
  OpcionOrigenFo,
  OpcionOrigenGeneral,
} from '../hooks/useReferencia'
import { formatearCantidad } from '../utils/cantidad'
import {
  ORIGEN_ETIQUETA,
  claveOpcion,
} from '../utils/referenciaOrigen'
import type { OpcionMaterial, OrigenReferencia } from '../utils/referenciaOrigen'

// ============================================================================
// SELECTOR DE MATERIAL DEPENDIENTE DEL ORIGEN (REQ-REF-013, T9)
//
// Filtro de texto + <select> nativo (P-7: accesible y robusto en móvil). Las
// opciones llegan de `useOpcionesOrigenReferencia` y se muestran como
// «DESCRIPCIÓN (stock)». «Inventario General» ofrece UNA OPCIÓN POR SECCIÓN
// con el nombre de la sección como sufijo (todas mapean al mismo
// `material_id`); el stock es ayuda visual de solo lectura copiada de la fila:
// NUNCA se suma ni se deduce (Q5, RN-5).
//
// FAIL-CLOSED (C-10): si el origen no cargó se muestra un error con
// «Reintentar»; jamás un origen vacío ni un stock 0 como válidos.
// ============================================================================

function etiquetaOpcion(opcion: OpcionMaterial): string {
  const base = `${opcion.descripcion} (${formatearCantidad(opcion.stock_actual)})`
  return opcion.origen === 'general'
    ? `${base} · ${opcion.nombre_seccion}`
    : base
}

interface MaterialSelectProps {
  id: string
  origen: OrigenReferencia
  estado:
    | EstadoOrigenOpciones<OpcionOrigenGeneral>
    | EstadoOrigenOpciones<OpcionOrigenFo>
  /** Materiales que no se ofrecen (ya en la Referencia o en otra línea). */
  excluidos: ReadonlySet<number>
  /** Clave de la opción elegida ('' = ninguna). */
  value: string
  onChange: (opcion: OpcionMaterial | null) => void
  error?: string | null
}

export default function MaterialSelect({
  id,
  origen,
  estado,
  excluidos,
  value,
  onChange,
  error = null,
}: MaterialSelectProps) {
  const [filtro, setFiltro] = useState('')
  const errorId = `${id}-error`
  const etiquetaOrigen = ORIGEN_ETIQUETA[origen]

  if (estado.isError) {
    return (
      <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <p>No se pudo cargar el {etiquetaOrigen}.</p>
        <button
          type="button"
          onClick={estado.refetch}
          className="mt-2 rounded-md border border-red-300 bg-white px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          Reintentar
        </button>
      </div>
    )
  }

  const opciones: OpcionMaterial[] | undefined = estado.options
  if (opciones === undefined) {
    return (
      <p role="status" className="text-sm text-slate-500">
        Cargando materiales del {etiquetaOrigen}…
      </p>
    )
  }

  const texto = filtro.trim().toLowerCase()
  const visibles = opciones.filter((opcion) => {
    const esActual = claveOpcion(opcion) === value
    if (esActual) return true
    if (excluidos.has(opcion.material_id)) return false
    return texto === '' || etiquetaOpcion(opcion).toLowerCase().includes(texto)
  })

  return (
    <div>
      <label
        htmlFor={id}
        className="text-xs font-semibold uppercase tracking-wide text-slate-500"
      >
        Material
      </label>
      <input
        type="search"
        aria-label={`Filtrar materiales del ${etiquetaOrigen}`}
        placeholder="Filtrar por nombre…"
        value={filtro}
        onChange={(event) => setFiltro(event.target.value)}
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
      <select
        id={id}
        value={value}
        aria-invalid={error !== null}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => {
          const elegida =
            visibles.find((opcion) => claveOpcion(opcion) === event.target.value) ??
            null
          onChange(elegida)
        }}
        className={`mt-2 w-full rounded-md border px-3 py-2 text-sm ${
          error ? 'border-red-400' : 'border-slate-300'
        }`}
      >
        <option value="">— Seleccione material —</option>
        {visibles.map((opcion) => (
          <option key={claveOpcion(opcion)} value={claveOpcion(opcion)}>
            {etiquetaOpcion(opcion)}
          </option>
        ))}
      </select>
      {visibles.length === 0 && (
        <p className="mt-1 text-xs text-slate-500">
          No hay materiales disponibles en el {etiquetaOrigen}
          {texto !== '' ? ' con ese filtro' : ''}.
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1 text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
