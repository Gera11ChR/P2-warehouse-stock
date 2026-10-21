import type { ReactNode } from 'react'
import ReporteExportButtons from './ReporteExportButtons'
import type { FormatoExportacion } from './ReporteExportButtons'
import ReporteExportFeedback from './ReporteExportFeedback'
import type { ReporteExportStatus, ReporteTipo } from '../utils/reporteExport'

// ============================================================================
// SUBSECCIÓN DE REPORTES — presentacional (Entrega / Consumo / Actividades)
//
// Compone filtros (equipo / desde / hasta / operación), acciones de
// exportación XLSX y un slot (`children`) para la tabla. Todo el estado y los
// handlers llegan por props; sin fetch, sin mutaciones.
//
// Props opcionales RETROCOMPATIBLES (REQ-REP-012/014):
//  - `selectorOperacion`: selector de operación (Acta / Seguimiento /
//    Actividad) renderizado tras «Hasta». Sin él, el comportamiento es el de
//    siempre.
//  - `acciones`: acciones de exportación propias del contenedor; si viene,
//    SUSTITUYEN a los botones Normal/Extenso (p. ej. Actividades solo tiene
//    un formato). `ReporteExportFeedback` se renderiza solo si `tipo` está
//    definido y `acciones` no vino (el contenedor aporta su propio feedback).
// ============================================================================

export interface EquipoOpcion {
  equipo_id: number
  nombre: string
}

/** Selector de operación de la subsección (Acta / Seguimiento / Actividad). */
export interface SelectorOperacion {
  /** Etiqueta visible del control («Acta», «Seguimiento», «Actividad»). */
  etiqueta: string
  /** Operación seleccionada (null = Todas). */
  valor: number | null
  opciones: { valor: number; etiqueta: string }[]
  onChange: (id: number | null) => void
}

export interface ReporteSubseccionProps {
  /** Tipo de acta de la subsección (copy del feedback de exportación).
   *  Opcional: sin él no se renderiza el feedback de actas. */
  tipo?: ReporteTipo
  /** Prefijo único de ids de los controles (evita colisiones entre pestañas). */
  idPrefix: string
  descripcion?: string
  equipos: EquipoOpcion[]
  equipoId: number | null
  desde: string
  hasta: string
  onEquipoChange: (equipoId: number | null) => void
  onDesdeChange: (desde: string) => void
  onHastaChange: (hasta: string) => void
  /** Selector de operación (REQ-REP-005/012/014): filtro por documento. */
  selectorOperacion?: SelectorOperacion
  /** Acciones de exportación propias del contenedor: sustituyen a los
   *  botones Normal/Extenso (que Actividades no usa: solo hay un formato). */
  acciones?: ReactNode
  onExportNormal?: () => void
  onExportExtenso?: () => void
  exportDisabled?: boolean
  exportLoading?: FormatoExportacion | null
  /** Estado de la exportación en curso/última (feedback accesible). */
  exportStatus?: ReporteExportStatus
  /** Motivo visible por el que la exportación está deshabilitada
   *  (p. ej. «No hay actas para los filtros»). Evita botones mudos. */
  exportDisabledReason?: string
  children: ReactNode
}

const LABEL = 'text-xs font-semibold uppercase tracking-wide text-slate-400'

export default function ReporteSubseccion({
  tipo,
  idPrefix,
  descripcion,
  equipos,
  equipoId,
  desde,
  hasta,
  onEquipoChange,
  onDesdeChange,
  onHastaChange,
  selectorOperacion,
  acciones,
  onExportNormal,
  onExportExtenso,
  exportDisabled,
  exportLoading,
  exportStatus = { estado: 'idle' },
  exportDisabledReason,
  children,
}: ReporteSubseccionProps) {
  const loadingFormato =
    exportLoading ??
    (exportStatus.estado === 'loading' ? exportStatus.formato : null)
  return (
    <div className="space-y-4">
      {descripcion && <p className="text-sm text-slate-500">{descripcion}</p>}

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1">
            <label htmlFor={`${idPrefix}-equipo`} className={LABEL}>
              Unidad
            </label>
            <select
              id={`${idPrefix}-equipo`}
              value={equipoId ?? ''}
              onChange={(e) =>
                onEquipoChange(
                  e.target.value === '' ? null : Number(e.target.value),
                )
              }
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Todos</option>
              {equipos.map((e) => (
                <option key={e.equipo_id} value={e.equipo_id}>
                  {e.nombre}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={`${idPrefix}-desde`} className={LABEL}>
              Desde
            </label>
            <input
              id={`${idPrefix}-desde`}
              type="date"
              value={desde}
              onChange={(e) => onDesdeChange(e.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor={`${idPrefix}-hasta`} className={LABEL}>
              Hasta
            </label>
            <input
              id={`${idPrefix}-hasta`}
              type="date"
              value={hasta}
              onChange={(e) => onHastaChange(e.target.value)}
              className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          {selectorOperacion && (
            <div className="min-w-48 flex-1">
              <label htmlFor={`${idPrefix}-operacion`} className={LABEL}>
                {selectorOperacion.etiqueta}
              </label>
              <select
                id={`${idPrefix}-operacion`}
                value={selectorOperacion.valor ?? ''}
                onChange={(e) =>
                  selectorOperacion.onChange(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Todas</option>
                {selectorOperacion.opciones.map((o) => (
                  <option key={o.valor} value={o.valor}>
                    {o.etiqueta}
                  </option>
                ))}
              </select>
            </div>
          )}
          {acciones !== undefined ? (
            acciones
          ) : (
            <ReporteExportButtons
              onExportNormal={onExportNormal}
              onExportExtenso={onExportExtenso}
              disabled={exportDisabled}
              loadingFormato={loadingFormato}
              describedBy={
                exportDisabledReason ? `${idPrefix}-export-motivo` : undefined
              }
            />
          )}
        </div>
        {exportDisabledReason && (
          <p
            id={`${idPrefix}-export-motivo`}
            className="mt-2 text-xs text-slate-500"
          >
            {exportDisabledReason}
          </p>
        )}
        {tipo !== undefined && acciones === undefined && (
          <ReporteExportFeedback tipo={tipo} status={exportStatus} />
        )}
      </div>

      {children}
    </div>
  )
}
