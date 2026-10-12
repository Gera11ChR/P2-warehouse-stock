import type { ReactNode } from 'react'
import ReporteExportButtons from './ReporteExportButtons'
import type { FormatoExportacion } from './ReporteExportButtons'
import ReporteExportFeedback from './ReporteExportFeedback'
import type { ReporteExportStatus, ReporteTipo } from '../utils/reporteExport'

// ============================================================================
// SUBSECCIÓN DE REPORTES — presentacional (Entrega / Consumo)
//
// Compone filtros (equipo / desde / hasta), botones de exportación XLSX y
// un slot (`children`) para la tabla de actas. Todo el estado y los
// handlers llegan por props; sin fetch, sin mutaciones.
// ============================================================================

export interface EquipoOpcion {
  equipo_id: number
  nombre: string
}

export interface ReporteSubseccionProps {
  /** Tipo de acta de la subsección (copy del feedback de exportación). */
  tipo: ReporteTipo
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
          <ReporteExportButtons
            onExportNormal={onExportNormal}
            onExportExtenso={onExportExtenso}
            disabled={exportDisabled}
            loadingFormato={loadingFormato}
            describedBy={
              exportDisabledReason ? `${idPrefix}-export-motivo` : undefined
            }
          />
        </div>
        {exportDisabledReason && (
          <p
            id={`${idPrefix}-export-motivo`}
            className="mt-2 text-xs text-slate-500"
          >
            {exportDisabledReason}
          </p>
        )}
        <ReporteExportFeedback tipo={tipo} status={exportStatus} />
      </div>

      {children}
    </div>
  )
}
