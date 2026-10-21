import { Fragment, useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import ReporteActividadDetalle from './ReporteActividadDetalle'
import type { Actividad } from '../types'

// ============================================================================
// TABLA DEL REPORTE DE ACTIVIDADES — presentacional (REQ-REP-012/013)
//
// Una fila por folio (snapshot del backend): folio, fecha en hora local,
// Unidad, vehículo, cliente, dirección, número de actividades y de
// materiales, usuario y acciones («Ver detalle» expande el desglose;
// «Descargar XLSX» descarga el libro individual de ese folio). Sin sumas ni
// cálculos: los números de fila cuentan los elementos recibidos.
// ============================================================================

const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-MX')

const BOTON =
  'flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50'

export default function ReporteActividadesTable({
  actividades,
  onDescargarIndividual,
  descargandoIndividualId,
}: {
  actividades: Actividad[]
  onDescargarIndividual: (a: Actividad) => void
  descargandoIndividualId: number | null
}) {
  const [expandidoId, setExpandidoId] = useState<number | null>(null)

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Folio</th>
            <th className="px-4 py-2">Fecha</th>
            <th className="px-4 py-2">Unidad</th>
            <th className="px-4 py-2">Vehículo</th>
            <th className="px-4 py-2">Cliente</th>
            <th className="px-4 py-2">Dirección</th>
            <th className="px-4 py-2">Actividades</th>
            <th className="px-4 py-2">Materiales</th>
            <th className="px-4 py-2">Usuario</th>
            <th className="px-4 py-2">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {actividades.map((a) => {
            const expandida = expandidoId === a.actividad_id
            const detalleId = `reportes-actividades-detalle-${a.actividad_id}`
            const descargando = descargandoIndividualId === a.actividad_id
            return (
              <Fragment key={a.actividad_id}>
                <tr className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-slate-600">
                    {a.folio}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {fechaCorta(a.fecha)}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{a.equipo_nombre}</td>
                  <td className="px-4 py-2 text-slate-700">{a.vehiculo}</td>
                  <td className="px-4 py-2 text-slate-700">{a.clientes}</td>
                  <td className="px-4 py-2 text-slate-700">{a.direcciones}</td>
                  <td className="px-4 py-2 text-slate-700">
                    {a.actividades.length}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {a.materiales.length}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{a.usuario}</td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandidoId(expandida ? null : a.actividad_id)
                        }
                        aria-expanded={expandida}
                        aria-controls={detalleId}
                        className={BOTON}
                      >
                        {expandida ? 'Ocultar detalle' : 'Ver detalle'}
                      </button>
                      <button
                        type="button"
                        onClick={() => onDescargarIndividual(a)}
                        disabled={descargando}
                        aria-busy={descargando}
                        className={BOTON}
                      >
                        {descargando ? (
                          <Loader2
                            className="h-3.5 w-3.5 animate-spin"
                            aria-hidden="true"
                          />
                        ) : (
                          <Download
                            className="h-3.5 w-3.5"
                            aria-hidden="true"
                          />
                        )}
                        Descargar XLSX
                      </button>
                    </div>
                  </td>
                </tr>
                {expandida && (
                  <tr id={detalleId} className="bg-slate-50">
                    <td colSpan={10}>
                      <ReporteActividadDetalle actividad={a} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
      {actividades.length === 0 && (
        <p className="p-6 text-center text-sm text-slate-500">
          Sin actividades para los filtros seleccionados
        </p>
      )}
    </div>
  )
}
