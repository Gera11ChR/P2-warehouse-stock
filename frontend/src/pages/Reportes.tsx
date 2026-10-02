import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { listEquipos } from '../services/equipos'
import { useExportarReporte, useReporteActas } from '../hooks/useReportes'
import Tabs from '../components/Tabs'
import ReporteSubseccion from '../components/ReporteSubseccion'
import ReporteConsumoTable from '../components/ReporteConsumoTable'
import ReporteEntregaTable from '../components/ReporteEntregaTable'
import type { ReporteParams } from '../types'

// ============================================================================
// REPORTES — subsecciones ENTREGA y CONSUMO (REQ-P2-REP-005)
//
// Contenedor de la vista: gestiona pestaña activa y filtros (estado de UX) y
// consume la capa de estado:
//  - useReporteActas(tipo, filtros)  → GET /reportes/{entrega|consumo}
//    ?formato=json: las actas persistidas por PostgreSQL (trigger al confirmar
//    TEAMS / cierre de seguimiento) se recargan al invalidarse sus queries.
//  - useExportarReporte(tipo)        → descarga XLSX (Normal / Extenso) y su
//    `exportStatus` (idle|loading|success|error con httpStatus y detalle).
// El frontend no agrega ni transforma datos del reporte.
// ============================================================================

const SUBSECCIONES = [
  { value: 'entrega', label: 'Entrega' },
  { value: 'consumo', label: 'Consumo' },
] as const

type Subseccion = (typeof SUBSECCIONES)[number]['value']

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

/** Props de navegación (opcionales): permiten llegar desde el aviso de acta
 *  generada (Transferencias / Seguimiento) directo a la subsección correcta,
 *  pre-filtrada por el equipo implicado. */
interface ReportesProps {
  initialSub?: string
  initialEquipoId?: number
}

function subseccionInicial(sub?: string): Subseccion {
  return sub === 'consumo' ? 'consumo' : 'entrega'
}

export default function Reportes({
  initialSub,
  initialEquipoId,
}: ReportesProps = {}) {
  const [subseccion, setSubseccion] = useState<Subseccion>(
    subseccionInicial(initialSub),
  )
  const [equipoId, setEquipoId] = useState<number | null>(
    initialEquipoId ?? null,
  )
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')

  const { data: equipos = [] } = useQuery({
    queryKey: ['equipos'],
    queryFn: listEquipos,
  })

  // Filtros opcionales (equipo / rango de fechas). El contrato no exige
  // ninguno: sin filtros el reporte es global. El formato lo fija el servicio.
  const params: ReporteParams = useMemo(() => {
    const p: ReporteParams = {}
    if (equipoId !== null) p.equipo_id = equipoId
    if (desde !== '') p.desde = desde
    if (hasta !== '') p.hasta = hasta
    return p
  }, [equipoId, desde, hasta])

  const {
    data: actas = [],
    isLoading,
    isError,
    error,
  } = useReporteActas(subseccion, params)

  const exportEntrega = useExportarReporte('entrega')
  const exportConsumo = useExportarReporte('consumo')
  const exportActivo = subseccion === 'entrega' ? exportEntrega : exportConsumo

  // Un resultado de exportación (éxito/error) pertenece a los filtros con los
  // que se pidió: al cambiarlos se limpia para no inducir a error.
  const reiniciarExportaciones = () => {
    exportEntrega.reiniciar()
    exportConsumo.reiniciar()
  }

  const equiposActivos = equipos.filter((e) => e.is_active)
  const filtrosProps = {
    equipos: equiposActivos,
    equipoId,
    desde,
    hasta,
    onEquipoChange: (id: number | null) => {
      setEquipoId(id)
      reiniciarExportaciones()
    },
    onDesdeChange: (valor: string) => {
      setDesde(valor)
      reiniciarExportaciones()
    },
    onHastaChange: (valor: string) => {
      setHasta(valor)
      reiniciarExportaciones()
    },
  }

  // Exportar solo tiene sentido con un listado cargado y no vacío; en los demás
  // casos el botón queda deshabilitado CON motivo visible (sin botones mudos).
  const motivoSinExportar = isLoading
    ? 'Cargando actas…'
    : isError
      ? 'No se pudo cargar el listado de actas, por lo que no es posible exportar.'
      : actas.length === 0
        ? 'No hay actas para los filtros seleccionados; no hay nada que exportar.'
        : undefined

  const exportProps = {
    onExportNormal: () => exportActivo.exportar('normal', params),
    onExportExtenso: () => exportActivo.exportar('extenso', params),
    exportDisabled: motivoSinExportar !== undefined,
    exportDisabledReason: motivoSinExportar,
    exportStatus: exportActivo.status,
  }

  const contenido = (
    <>
      {isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando reporte...</p>
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">
            No se pudo cargar el reporte de {subseccion}.
          </p>
          <p className="mt-1 text-sm text-red-600">{errorMessage(error)}</p>
        </div>
      )}

      {!isLoading &&
        !isError &&
        (subseccion === 'entrega' ? (
          <ReporteEntregaTable actas={actas} />
        ) : (
          <ReporteConsumoTable actas={actas} />
        ))}
    </>
  )

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-slate-800">Reportes</h2>

      <Tabs
        tabs={SUBSECCIONES}
        value={subseccion}
        onChange={setSubseccion}
        idPrefix="reportes"
        ariaLabel="Subsecciones de reportes"
      >
        {subseccion === 'entrega' && (
          <ReporteSubseccion
            tipo="entrega"
            idPrefix="reportes-entrega"
            descripcion="Actas de Entrega: se generan al confirmar un movimiento TEAMS."
            {...filtrosProps}
            {...exportProps}
          >
            {contenido}
          </ReporteSubseccion>
        )}

        {subseccion === 'consumo' && (
          <ReporteSubseccion
            tipo="consumo"
            idPrefix="reportes-consumo"
            descripcion="Actas de Consumo: se generan al cerrar un seguimiento."
            {...filtrosProps}
            {...exportProps}
          >
            {contenido}
          </ReporteSubseccion>
        )}
      </Tabs>
    </div>
  )
}
