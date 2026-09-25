import { useState } from 'react'
import type { FormEvent } from 'react'
import { Search } from 'lucide-react'
import { listCatalog } from '../services/catalog'
import type { Material } from '../types'

// ============================================================================
// VALIDACIÓN PROACTIVA (REQ-UI-007 / REQ-API-006/007)
// El backend valida: ge=1 por campo numérico, hasta >= desde (ambos → 422),
// y max_length=255 por descripción. La UI replica esas reglas para NO
// disparar 422 del servidor: búsqueda deshabilitada si el rango es inválido.
// ============================================================================

const MAX_DESCRIPCION = 255

/** Número de lista válido: vacío (omite el campo) o entero ≥ 1. */
function esNumeroListaValido(valor: string): boolean {
  if (valor === '') return true
  const n = Number(valor)
  return Number.isInteger(n) && n >= 1
}

export default function BulkSearch() {
  const [desdeNumero, setDesdeNumero] = useState('')
  const [hastaNumero, setHastaNumero] = useState('')
  const [desdeDescripcion, setDesdeDescripcion] = useState('')
  const [hastaDescripcion, setHastaDescripcion] = useState('')
  const [rows, setRows] = useState<Material[]>([])
  const [startIndex, setStartIndex] = useState(1)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const desdeNumeroValido = esNumeroListaValido(desdeNumero)
  const hastaNumeroValido = esNumeroListaValido(hastaNumero)
  const rangoNumericoConsistente =
    desdeNumero === '' || hastaNumero === '' || Number(desdeNumero) <= Number(hastaNumero)
  const rangoNumericoValido =
    desdeNumeroValido && hastaNumeroValido && rangoNumericoConsistente
  const descripcionesValidas =
    desdeDescripcion.length <= MAX_DESCRIPCION &&
    hastaDescripcion.length <= MAX_DESCRIPCION
  const camposVacios =
    !desdeNumero && !hastaNumero && !desdeDescripcion && !hastaDescripcion
  const rangoInvalido = !rangoNumericoValido || !descripcionesValidas
  const puedeBuscar = !rangoInvalido && !camposVacios && !loading

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault()
    if (!puedeBuscar) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      // REQ-API-006/007: rango ordinal (número de lista) y rango por
      // descripción se resuelven 100 % en backend con orden determinista
      // (descripcion ASC, id_lista ASC); `start_index` permite numerar
      // filas continuas 1-indexed sin descargar el catálogo completo.
      const result = await listCatalog({
        desde_numero_lista: desdeNumero ? Number(desdeNumero) : undefined,
        hasta_numero_lista: hastaNumero ? Number(hastaNumero) : undefined,
        desde_descripcion: desdeDescripcion || undefined,
        hasta_descripcion: hastaDescripcion || undefined,
      })
      setRows(result.materiales)
      setStartIndex(result.start_index)
      setSearched(true)
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? `No se pudo ejecutar la búsqueda: ${err.message}`
          : 'No se pudo ejecutar la búsqueda. Verifique la conexión con el backend.',
      )
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  const inputClase = (valido: boolean) =>
    `mt-1 w-40 rounded-md border px-3 py-2 text-sm focus:outline-none ${
      valido
        ? 'border-slate-300 focus:border-blue-500'
        : 'border-red-400 focus:border-red-500'
    }`

  return (
    <div className="space-y-3">
      <form onSubmit={handleSearch} className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Desde número de lista
          </label>
          <input
            type="number"
            min={1}
            step={1}
            value={desdeNumero}
            onChange={(event) => setDesdeNumero(event.target.value)}
            aria-invalid={!desdeNumeroValido}
            className={inputClase(desdeNumeroValido)}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Hasta número de lista
          </label>
          <input
            type="number"
            min={1}
            step={1}
            value={hastaNumero}
            onChange={(event) => setHastaNumero(event.target.value)}
            aria-invalid={!hastaNumeroValido || !rangoNumericoConsistente}
            className={inputClase(hastaNumeroValido && rangoNumericoConsistente)}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Desde descripción
          </label>
          <input
            type="text"
            maxLength={MAX_DESCRIPCION}
            value={desdeDescripcion}
            onChange={(event) => setDesdeDescripcion(event.target.value)}
            className={inputClase(descripcionesValidas)}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Hasta descripción
          </label>
          <input
            type="text"
            maxLength={MAX_DESCRIPCION}
            value={hastaDescripcion}
            onChange={(event) => setHastaDescripcion(event.target.value)}
            className={inputClase(descripcionesValidas)}
          />
        </div>
        <button
          type="submit"
          disabled={!puedeBuscar}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Search className="h-4 w-4" /> Buscar
        </button>
      </form>

      {rangoInvalido && (
        <p className="text-xs font-medium text-amber-600">
          Rango inválido: los números de lista deben ser enteros ≥ 1 y el
          campo "desde" no puede ser mayor que "hasta". Las descripciones
          admiten hasta {MAX_DESCRIPCION} caracteres.
        </p>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {searched && !error && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nº</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">Categoría</th>
                <th className="px-4 py-3">U.M.</th>
                <th className="px-4 py-3">Stock Mínimo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, index) => (
                <tr key={row.id_lista}>
                  <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                    {startIndex + index}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-700">
                    {row.codigo ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{row.descripcion}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {row.categoria ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{row.u_m ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {row.stock_minimo != null ? row.stock_minimo : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin materiales para el rango solicitado.
            </p>
          )}
          <p className="p-3 text-xs text-slate-500">
            Búsqueda a granel sobre el catálogo (numeración continua 1-indexed
            desde {startIndex} según el contrato del servidor). Stock actual
            disponible en vista por sección.
          </p>
        </div>
      )}
    </div>
  )
}
