import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { listEventos } from '../services/auditoria'
import { listCatalog } from '../services/catalog'
import { listSecciones } from '../services/inventory'
import { listEquipos } from '../services/equipos'
import { TIPOS_ACCION_AUDITORIA } from '../types'

function formatFecha(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'medium' })
}

export default function Auditoria() {
  const [materialId, setMaterialId] = useState('')
  const [tipoAccion, setTipoAccion] = useState('')
  const [usuario, setUsuario] = useState('')
  const [fechaDesde, setFechaDesde] = useState('')
  const [expandidos, setExpandidos] = useState<Set<number>>(new Set())

  const eventosQuery = useQuery({
    queryKey: ['auditoria', materialId, tipoAccion, usuario],
    queryFn: () =>
      listEventos({
        material_id: materialId ? Number(materialId) : undefined,
        tipo_accion: tipoAccion || undefined,
        usuario: usuario.trim() || undefined,
        limit: 500,
      }),
  })

  const { data: catalogo = [] } = useQuery({
    queryKey: ['catalogo'],
    queryFn: () => listCatalog(),
  })

  const { data: secciones = [] } = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
  })

  const { data: equipos = [] } = useQuery({
    queryKey: ['equipos'],
    queryFn: listEquipos,
  })

  const nombreMaterial = useMemo(() => {
    const map = new Map<number, { codigo: string | null; descripcion: string }>()
    catalogo.forEach((m) =>
      map.set(m.id_lista, { codigo: m.codigo, descripcion: m.descripcion }),
    )
    return (id: number | null): string => {
      if (id == null) return '—'
      const m = map.get(id)
      return m ? `${m.descripcion} (${m.codigo ?? id})` : `ID LISTA ${id}`
    }
  }, [catalogo])

  const nombreSeccion = (id: number | null): string =>
    secciones.find((s) => s.almacen_id === id)?.nombre ?? `Sección ${id}`
  const nombreEquipo = (id: number | null): string =>
    equipos.find((e) => e.equipo_id === id)?.nombre ?? `Equipo ${id}`

  const eventos = (eventosQuery.data ?? []).filter((e) => {
    if (!fechaDesde) return true
    return new Date(e.created_at) >= new Date(fechaDesde)
  })

  const toggleDetalles = (id: number) => {
    setExpandidos((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-slate-800">Auditoría</h2>

      {/* Filtros */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div>
          <label className="block text-xs font-medium text-slate-500">
            Tipo de acción
          </label>
          <select
            value={tipoAccion}
            onChange={(e) => setTipoAccion(e.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Todos</option>
            {Object.entries(TIPOS_ACCION_AUDITORIA).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500">
            Material (ID LISTA)
          </label>
          <input
            type="number"
            value={materialId}
            onChange={(e) => setMaterialId(e.target.value)}
            placeholder="Ej. 12"
            className="mt-1 w-32 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            placeholder="Usuario / operador"
            className="w-48 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500">
            Fecha desde (local)
          </label>
          <input
            type="date"
            value={fechaDesde}
            onChange={(e) => setFechaDesde(e.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <p className="text-xs text-slate-400">
          Filtro de fecha aplicado en el cliente sobre la respuesta del
          servidor.
        </p>
      </div>

      {eventosQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando auditoría…</p>
        </div>
      )}

      {eventosQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-700">
            No se pudo obtener el registro de auditoría. Verifique la conexión
            con el backend y sus permisos.
          </p>
        </div>
      )}

      {!eventosQuery.isLoading && !eventosQuery.isError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">Fecha y Hora</th>
                <th className="px-4 py-2">Usuario</th>
                <th className="px-4 py-2">Acción</th>
                <th className="px-4 py-2">Material Afectado</th>
                <th className="px-4 py-2">Origen → Destino</th>
                <th className="px-4 py-2">Cantidad</th>
                <th className="px-4 py-2">Resultado</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {eventos.map((e) => (
                <>
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-2 text-slate-600">
                      {formatFecha(e.created_at)}
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {e.usuario ?? '—'}
                    </td>
                    <td className="px-4 py-2">
                      <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                        {TIPOS_ACCION_AUDITORIA[e.tipo_accion] ?? e.tipo_accion}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {nombreMaterial(e.material_id)}
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {e.almacen_origen_id != null ||
                      e.equipo_origen_id != null ? (
                        <>
                          {e.almacen_origen_id != null
                            ? nombreSeccion(e.almacen_origen_id)
                            : e.equipo_origen_id != null
                              ? nombreEquipo(e.equipo_origen_id)
                              : '—'}{' '}
                          →{' '}
                          {e.almacen_destino_id != null
                            ? nombreSeccion(e.almacen_destino_id)
                            : e.equipo_destino_id != null
                              ? nombreEquipo(e.equipo_destino_id)
                              : '—'}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {e.cantidad != null ? e.cantidad : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                          e.resultado === 'EXITO'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {e.resultado ?? '—'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {e.detalles && (
                        <button
                          type="button"
                          onClick={() => toggleDetalles(e.id)}
                          className="text-xs font-medium text-blue-600 hover:text-blue-800"
                        >
                          {expandidos.has(e.id) ? 'Ocultar' : 'Detalles'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expandidos.has(e.id) && e.detalles && (
                    <tr key={`${e.id}-detalles`} className="bg-slate-50">
                      <td colSpan={8} className="px-4 py-2">
                        <pre className="overflow-x-auto rounded-md bg-slate-800 p-3 text-xs text-slate-100">
                          {JSON.stringify(e.detalles, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
          {eventos.length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin eventos de auditoría para los filtros seleccionados.
            </p>
          )}
        </div>
      )}

      <p className="text-xs text-slate-400">
        Ledger append-only: los eventos provienen estrictamente del servidor
        (sin cálculo ni reconciliación local).
      </p>
    </div>
  )
}
