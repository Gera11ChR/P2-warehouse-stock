import { useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { listCatalog } from '../services/catalog'
import { listSecciones, stockSeccion } from '../services/inventory'
import { listMovimientos } from '../services/movimientos'

function exportarCSV(filas: unknown[], nombre: string) {
  if (filas.length === 0) return
  const headers = Object.keys(filas[0] as Record<string, unknown>)
  const csvContent = [
    headers.join(','),
    ...filas.map((row) =>
      headers
        .map((h) => {
          const val = (row as Record<string, unknown>)[h]
          return typeof val === 'string' && val.includes(',')
            ? `"${val}"`
            : String(val ?? '')
        })
        .join(','),
    ),
  ].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${nombre}-${new Date().toISOString().split('T')[0]}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export default function Reportes() {
  const [busqueda, setBusqueda] = useState('')

  const catalogoQuery = useQuery({
    queryKey: ['catalogo'],
    queryFn: () => listCatalog(),
  })

  const seccionesQuery = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
  })

  const movimientosQuery = useQuery({
    queryKey: ['movimientos'],
    queryFn: () => listMovimientos(),
  })

  const seccionesActivas = (seccionesQuery.data ?? []).filter((s) => s.is_active)

  const stockQueries = useQueries({
    queries: seccionesActivas.map((s) => ({
      queryKey: ['stock', s.almacen_id],
      queryFn: () => stockSeccion(s.almacen_id),
    })),
  })

  // KPIs calculados (agregación de presentación desde datos reales)
  const totalSKUs = (catalogoQuery.data ?? []).filter((m) => m.is_active).length
  const seccionesActivasCount = seccionesActivas.length

  const stockEnAlerta = useMemo(() => {
    let count = 0
    stockQueries.forEach((q) => {
      if (q.data) {
        count += q.data.filter((row) => row.alerta_stock).length
      }
    })
    return count
  }, [stockQueries])

  const totalMovimientos = (movimientosQuery.data ?? []).length

  // Tabla de catálogo filtrada
  const catalogoFiltrado = useMemo(() => {
    const catalogo = catalogoQuery.data ?? []
    return catalogo
      .filter((m) => m.is_active)
      .filter(
        (m) =>
          !busqueda ||
          m.descripcion.toLowerCase().includes(busqueda.toLowerCase()) ||
          (m.codigo ?? '').toLowerCase().includes(busqueda.toLowerCase()),
      )
  }, [catalogoQuery.data, busqueda])

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-slate-800">Reportes</h2>

      {/* Tarjetas KPI (agregación visual desde endpoints reales) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Total de SKUs
          </p>
          <p className="mt-1 text-2xl font-bold text-slate-800">
            {catalogoQuery.isLoading ? '—' : totalSKUs.toLocaleString('es-MX')}
          </p>
          <p className="mt-1 text-xs text-slate-400">Materiales activos</p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Stock en Alerta
          </p>
          <p className="mt-1 text-2xl font-bold text-red-600">
            {stockQueries.some((q) => q.isLoading)
              ? '—'
              : stockEnAlerta.toLocaleString('es-MX')}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Materiales con stock ≤ mínimo
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Movimientos
          </p>
          <p className="mt-1 text-2xl font-bold text-blue-600">
            {movimientosQuery.isLoading
              ? '—'
              : totalMovimientos.toLocaleString('es-MX')}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Total histórico (sin timestamp en API)
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Secciones Activas
          </p>
          <p className="mt-1 text-2xl font-bold text-green-600">
            {seccionesQuery.isLoading
              ? '—'
              : seccionesActivasCount.toLocaleString('es-MX')}
          </p>
          <p className="mt-1 text-xs text-slate-400">Almacenes en operación</p>
        </div>
      </div>

      {/* Vista filtrable de catálogo */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800">
            Catálogo de Materiales
          </h3>
          <button
            type="button"
            onClick={() => exportarCSV(catalogoFiltrado, 'catalogo')}
            disabled={catalogoFiltrado.length === 0}
            className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Download className="h-4 w-4" /> Exportar CSV
          </button>
        </div>
        <div className="mt-3 flex gap-3">
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por descripción o código"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {catalogoQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          No se pudo cargar el catálogo. Verifique la conexión con el backend.
        </div>
      )}

      {!catalogoQuery.isLoading && !catalogoQuery.isError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">ID Lista</th>
                <th className="px-4 py-2">Código</th>
                <th className="px-4 py-2">Descripción</th>
                <th className="px-4 py-2">Categoría</th>
                <th className="px-4 py-2">U.M.</th>
                <th className="px-4 py-2">Stock Mínimo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {catalogoFiltrado.map((m) => (
                <tr key={m.id_lista} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono font-semibold text-slate-600">
                    {m.id_lista}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-700">
                    {m.codigo ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{m.descripcion}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {m.categoria ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-500">{m.u_m ?? '—'}</td>
                  <td className="px-4 py-2 text-slate-700">
                    {m.stock_minimo != null ? m.stock_minimo : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {catalogoFiltrado.length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin materiales que coincidan con los filtros.
            </p>
          )}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Métricas calculadas desde endpoints reales (agregación de presentación,
        cero autoridad local). Exportación CSV de la vista filtrada actual.
      </p>
    </div>
  )
}
