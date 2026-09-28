import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { Download } from 'lucide-react'
import { listEquipos } from '../services/equipos'
import { descargarReporteCsv } from '../services/reportes'
import { useReporteDespliegues } from '../hooks/useReporteDespliegues'
import { useToast } from '../hooks/useToasts'
import type { ReporteParams } from '../types'

// ============================================================================
// REPORTES — actividad de DESPLIEGUES (REQ-REPORT-001, FASE 7)
//
// Contrato real GET /api/v1/reportes/despliegues. La vista consume el
// reporte TAL CUAL lo sirve el backend (format=json para la tabla y
// format=csv vía servicio de descarga); el frontend no agrega ni transforma
// datos.
// ============================================================================

const BADGE_ESTADO: Record<string, string> = {
  ABIERTA: 'bg-amber-100 text-amber-700',
  CERRADA: 'bg-green-100 text-green-700',
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data as
      | { error?: { message?: string } }
      | undefined
    if (detail?.error?.message) {
      return detail.error.message
    }
  }
  return 'Ocurrió un error'
}

export default function Reportes() {
  const { pushToast, pushError } = useToast()

  const [equipoId, setEquipoId] = useState<number | null>(null)
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [csvLoading, setCsvLoading] = useState(false)

  const { data: equipos = [] } = useQuery({
    queryKey: ['equipos'],
    queryFn: listEquipos,
  })

  // Filtros opcionales (equipo / rango de fechas). El contrato no exige
  // ninguno: sin filtros el reporte es global.
  const filtros = useMemo(() => {
    const p: { equipo_id?: number; desde?: string; hasta?: string } = {}
    if (equipoId !== null) p.equipo_id = equipoId
    if (desde !== '') p.desde = desde
    if (hasta !== '') p.hasta = hasta
    return p
  }, [equipoId, desde, hasta])

  const params: ReporteParams = useMemo(
    () => ({ ...filtros, format: 'json' }),
    [filtros],
  )

  const {
    data: despliegues = [],
    isLoading,
    isError,
    error,
  } = useReporteDespliegues(params)

  const handleExportar = async () => {
    setCsvLoading(true)
    try {
      await descargarReporteCsv(filtros)
      pushToast('Reporte CSV descargado')
    } catch (err) {
      pushError(errorMessage(err))
    } finally {
      setCsvLoading(false)
    }
  }

  // Una fila por ítem reportado; despliegue sin ítems → fila con "—".
  const filas = useMemo(() => {
    const resultado: {
      despliegue: (typeof despliegues)[number]
      item: (typeof despliegues)[number]['items'][number] | null
    }[] = []
    for (const d of despliegues) {
      if (d.items.length === 0) {
        resultado.push({ despliegue: d, item: null })
      } else {
        for (const item of d.items) {
          resultado.push({ despliegue: d, item })
        }
      }
    }
    return resultado
  }, [despliegues])

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-slate-800">
        Reportes — Actividad de Despliegues
      </h2>

      {/* Filtros + exportación */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1">
            <label
              htmlFor="reportes-equipo"
              className="text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              Equipo
            </label>
            <select
              id="reportes-equipo"
              value={equipoId ?? ''}
              onChange={(e) =>
                setEquipoId(e.target.value === '' ? null : Number(e.target.value))
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              {equipos
                .filter((e) => e.is_active)
                .map((e) => (
                  <option key={e.equipo_id} value={e.equipo_id}>
                    {e.nombre}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="reportes-desde"
              className="text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              Desde
            </label>
            <input
              id="reportes-desde"
              type="date"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label
              htmlFor="reportes-hasta"
              className="text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              Hasta
            </label>
            <input
              id="reportes-hasta"
              type="date"
              value={hasta}
              onChange={(e) => setHasta(e.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="button"
            onClick={handleExportar}
            disabled={isLoading || csvLoading}
            className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Download className="h-4 w-4" /> Exportar CSV
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando reporte...</p>
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">
            No se pudo cargar el reporte de despliegues.
          </p>
          <p className="mt-1 text-sm text-red-600">{errorMessage(error)}</p>
        </div>
      )}

      {!isLoading && !isError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Despliegue</th>
                <th className="px-4 py-2">Fecha</th>
                <th className="px-4 py-2">Equipo</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2">Material</th>
                <th className="px-4 py-2">Categoría</th>
                <th className="px-4 py-2">U.M.</th>
                <th className="px-4 py-2">Tomada</th>
                <th className="px-4 py-2">Sobrante</th>
                <th className="px-4 py-2">Consumida</th>
                <th className="px-4 py-2">Usuario</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filas.map(({ despliegue: d, item }) => (
                <tr
                  key={`${d.despliegue_id}-${item?.material_id ?? 'sin-items'}`}
                  className="hover:bg-slate-50"
                >
                  <td className="px-4 py-2 font-mono text-slate-600">
                    #{d.despliegue_id}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {d.fecha.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{d.equipo_nombre}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                        BADGE_ESTADO[d.estado] ?? 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {d.estado}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {item ? (
                      <div>
                        <p className="font-mono text-xs text-slate-500">
                          {item.codigo ?? '—'}
                        </p>
                        <p className="text-slate-700">{item.descripcion}</p>
                      </div>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {item?.categoria ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {item?.um ?? '—'}
                  </td>
                  <td className="px-4 py-2 font-semibold text-slate-700">
                    {item ? item.cantidad_tomada.toLocaleString('es-MX') : '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {item
                      ? item.cantidad_sobrante != null
                        ? item.cantidad_sobrante.toLocaleString('es-MX')
                        : '—'
                      : '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {item
                      ? item.cantidad_consumida != null
                        ? item.cantidad_consumida.toLocaleString('es-MX')
                        : '—'
                      : '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{d.usuario}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filas.length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin actividad de despliegues
            </p>
          )}
        </div>
      )}
    </div>
  )
}
