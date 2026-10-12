import type { Acta, ActaItem } from '../types'

// ============================================================================
// TABLA DE ACTAS DE ENTREGA — presentacional
//
// Una fila por ítem entregado (acta sin ítems → fila con "—"). Las actas son
// snapshots persistidos por PostgreSQL al confirmar TEAMS; la UI solo las
// representa (sin agregar ni recalcular cantidades).
// ============================================================================

const num = (valor: number | null | undefined) =>
  valor != null ? valor.toLocaleString('es-MX') : '—'

export default function ReporteEntregaTable({ actas }: { actas: Acta[] }) {
  const filas = actas.flatMap((acta): { acta: Acta; item: ActaItem | null }[] =>
    acta.items.length === 0
      ? [{ acta, item: null }]
      : acta.items.map((item) => ({ acta, item })),
  )

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Acta</th>
            <th className="px-4 py-2">Fecha</th>
            <th className="px-4 py-2">Unidad</th>
            <th className="px-4 py-2">Material</th>
            <th className="px-4 py-2">Categoría</th>
            <th className="px-4 py-2">U.M.</th>
            <th className="px-4 py-2">Cantidad</th>
            <th className="px-4 py-2">Usuario</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {filas.map(({ acta, item }) => (
            <tr
              key={`${acta.acta_id}-${item?.material_id ?? 'sin-items'}`}
              className="hover:bg-slate-50"
            >
              <td className="px-4 py-2 font-mono text-slate-600">
                #{acta.acta_id}
              </td>
              <td className="px-4 py-2 text-slate-700">
                {acta.fecha.slice(0, 10)}
              </td>
              <td className="px-4 py-2 text-slate-700">
                {acta.equipo_nombre ?? '—'}
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
              <td className="px-4 py-2 text-slate-500">{item?.u_m ?? '—'}</td>
              <td className="px-4 py-2 font-semibold text-slate-700">
                {num(item?.cantidad)}
              </td>
              <td className="px-4 py-2 text-slate-700">{acta.usuario ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {filas.length === 0 && (
        <p className="p-6 text-center text-sm text-slate-500">
          Sin actas de entrega
        </p>
      )}
    </div>
  )
}
