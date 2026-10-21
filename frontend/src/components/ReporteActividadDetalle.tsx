import MonedaMxn from './MonedaMxn'
import type { Actividad } from '../types'

// ============================================================================
// DESGLOSE DE UN FOLIO DEL REPORTE DE ACTIVIDADES — presentacional
// (REQ-REP-012)
//
// SOLO LECTURA: muestra el snapshot persistido por PostgreSQL (materiales con
// CANTIDAD, MATERIAL, U.M. y VALOR UNITARIO congelado, actividades realizadas
// y comentarios). Sin sumas ni cálculos: cada valor se renderiza tal cual lo
// entregó el backend.
// ============================================================================

const TITULO = 'text-xs font-semibold uppercase tracking-wide text-slate-400'

export default function ReporteActividadDetalle({
  actividad,
}: {
  actividad: Actividad
}) {
  const comentarios = actividad.comentarios ?? ''
  return (
    <div className="space-y-4 px-4 py-3">
      <div>
        <h4 className={TITULO}>Materiales</h4>
        {actividad.materiales.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">
            Sin materiales registrados.
          </p>
        ) : (
          <table className="mt-2 w-full max-w-2xl text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-2 py-1">Cantidad</th>
                <th className="px-2 py-1">Material</th>
                <th className="px-2 py-1">U.M.</th>
                <th className="px-2 py-1">Valor unitario</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {actividad.materiales.map((m) => (
                <tr key={m.material_id}>
                  <td className="px-2 py-1 font-semibold text-slate-700">
                    {m.cantidad_consumida.toLocaleString('es-MX')}
                  </td>
                  <td className="px-2 py-1 text-slate-700">
                    {m.codigo && (
                      <span className="mr-1 font-mono text-xs text-slate-500">
                        {m.codigo}
                      </span>
                    )}
                    {m.descripcion}
                  </td>
                  <td className="px-2 py-1 text-slate-500">{m.u_m ?? '—'}</td>
                  <td className="px-2 py-1">
                    <MonedaMxn valor={m.valor_unitario} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div>
        <h4 className={TITULO}>Actividades realizadas</h4>
        <ul className="mt-1 list-inside list-disc space-y-1 text-sm text-slate-700">
          {actividad.actividades.map((a, i) => (
            <li key={`${i}-${a}`}>{a}</li>
          ))}
        </ul>
      </div>

      <div>
        <h4 className={TITULO}>Comentarios</h4>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
          {comentarios === '' ? 'Sin comentarios' : comentarios}
        </p>
      </div>
    </div>
  )
}
