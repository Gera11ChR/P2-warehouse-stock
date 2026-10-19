import MonedaMxn from './MonedaMxn'
import type { ActividadMaterial } from '../types'

// ============================================================================
// MATERIALES CONSUMIDOS (solo lectura) — subsección ACTIVIDADES
//
// Muestra CANTIDAD | MATERIAL | U.M. | VALOR UNITARIO del seguimiento cerrado
// (REQ-ACT-002). Los materiales los hereda el backend del consumo registrado
// en CONSUMO; aquí NO se capturan, NO se suman y NO se multiplican (el valor
// unitario es el vigente que entrega PostgreSQL; el que queda en el registro
// lo congela el backend al confirmar).
// ============================================================================

interface Props {
  materiales: ActividadMaterial[]
}

export default function ActividadesMaterialesConsumidos({ materiales }: Props) {
  return (
    <section
      aria-label="Materiales consumidos"
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
        Materiales Consumidos
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        Automatizado: se toma de lo consumido al cerrar el seguimiento en
        CONSUMO y se añade al reporte.
      </p>

      {materiales.length === 0 ? (
        <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-500">
          Sin materiales consumidos en este seguimiento.
        </p>
      ) : (
        <table className="mt-3 w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-2 py-2">Cantidad</th>
              <th className="px-2 py-2">Material</th>
              <th className="px-2 py-2">U.M.</th>
              <th className="px-2 py-2 text-right">Valor unitario</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {materiales.map((m) => (
              <tr key={m.material_id}>
                <td className="px-2 py-2 font-semibold text-slate-700">
                  {m.cantidad_consumida.toLocaleString('es-MX')}
                </td>
                <td className="px-2 py-2 text-slate-700">{m.descripcion}</td>
                <td className="px-2 py-2 text-slate-600">{m.u_m ?? '—'}</td>
                <td className="px-2 py-2 text-right text-slate-700">
                  <MonedaMxn valor={m.valor_unitario} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
