import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listSecciones, stockSeccion } from '../services/inventory'

interface FibraOpticaProps {
  sub: string
}

const TIPO_POR_SUB: Record<string, string> = {
  paquete: 'FO_PAQUETE',
  'en-uso': 'FO_EN_USO',
}

export default function FibraOptica({ sub }: FibraOpticaProps) {
  const esEnUso = sub === 'en-uso'
  const tipoBuscado = TIPO_POR_SUB[sub]

  const seccionesQuery = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
  })

  const seccionFibra = useMemo(
    () =>
      (seccionesQuery.data ?? []).find(
        (s) => s.tipo === tipoBuscado && s.is_active,
      ),
    [seccionesQuery.data, tipoBuscado],
  )

  const stockQuery = useQuery({
    queryKey: ['stock', seccionFibra?.almacen_id],
    queryFn: () => stockSeccion(seccionFibra!.almacen_id),
    enabled: seccionFibra != null,
  })

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-800">
          Fibra Óptica — {esEnUso ? 'En Uso' : 'Paquete'}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {esEnUso
            ? 'Metros lineales de fibra en tendido (bobinas abiertas).'
            : 'Carretes completos de fibra en inventario.'}
        </p>
      </div>

      {seccionesQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando secciones…</p>
        </div>
      )}

      {seccionesQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-700">
            No se pudieron cargar las secciones de inventario.
          </p>
        </div>
      )}

      {!seccionesQuery.isLoading &&
        !seccionesQuery.isError &&
        seccionFibra == null && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
            <p className="text-amber-700">
              No existe una sección activa de tipo{' '}
              <span className="font-mono">{tipoBuscado}</span> en el backend.
            </p>
          </div>
        )}

      {seccionFibra != null && stockQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">
            Cargando inventario de {seccionFibra.nombre}…
          </p>
        </div>
      )}

      {seccionFibra != null && stockQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-700">
            No se pudo obtener el inventario de {seccionFibra.nombre}.
          </p>
        </div>
      )}

      {seccionFibra != null &&
        !stockQuery.isLoading &&
        !stockQuery.isError && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">ID Lista</th>
                  <th className="px-4 py-3">Código</th>
                  <th className="px-4 py-3">Descripción</th>
                  <th className="px-4 py-3">U.M.</th>
                  <th className="px-4 py-3">
                    {esEnUso ? 'Metros Disponibles' : 'Carretes en Stock'}
                  </th>
                  <th className="px-4 py-3">Stock Mínimo</th>
                  <th className="px-4 py-3">Alerta Stock</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(stockQuery.data ?? []).map((row) => (
                  <tr key={row.material_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-semibold text-slate-600">
                      {row.material_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700">
                      {row.codigo ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.descripcion}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {row.u_m ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                          row.alerta_stock
                            ? 'bg-red-100 text-red-700'
                            : row.stock_actual <= 0
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-green-100 text-green-700'
                        }`}
                      >
                        {row.stock_actual.toLocaleString('es-MX')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.stock_minimo != null ? row.stock_minimo : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {row.alerta_stock ? (
                        <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                          Alerta Stock
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(stockQuery.data ?? []).length === 0 && (
              <p className="p-6 text-center text-sm text-slate-500">
                Sin materiales en {seccionFibra.nombre}.
              </p>
            )}
          </div>
        )}

      <p className="text-xs text-slate-400">
        Lectura directa del contrato real: la sección{' '}
        <span className="font-mono">{tipoBuscado}</span> se consume vía{' '}
        <span className="font-mono">/inventario/secciones/&lt;id&gt;</span>. Las
        transferencias se realizan en la página Transferencias (TEAMS/DEVOL).
      </p>
    </div>
  )
}
