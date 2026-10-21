import { useMemo, useState } from 'react'
import axios from 'axios'
import { Download, Loader2 } from 'lucide-react'
import {
  useExportarReporteActividades,
  useReporteActividades,
} from '../hooks/useReportes'
import ReporteSubseccion from './ReporteSubseccion'
import type { EquipoOpcion } from './ReporteSubseccion'
import ReporteActividadesTable from './ReporteActividadesTable'
import ReporteActividadesExportFeedback from './ReporteActividadesExportFeedback'
import type { Actividad, ReporteActividadesParams } from '../types'

// ============================================================================
// SUBSECCIÓN REPORTES › ACTIVIDADES — contenedor (REQ-REP-001/012/013)
//
// Gestiona los filtros compartidos, el selector de operación (folio) y la
// descarga del libro XLSX (consolidado o individual). El listado y la
// exportación los sirve el backend congelado; aquí NUNCA se agrega ni se
// recalcula: se renderiza lo que devuelve el servidor.
//
// Selector de operación (REQ-REP-005/012): las opciones salen del listado
// SIN el filtro de operación; con una operación elegida se hace una segunda
// consulta filtrada por el servidor (`actividad_id`). Cambiar Unidad o
// fechas reinicia la selección y el resultado de descarga (REQ-REP-013).
// ============================================================================

const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-MX')

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detalle = error.response?.data as
      | { error?: { message?: string } }
      | undefined
    if (detalle?.error?.message) {
      return detalle.error.message
    }
  }
  return 'Ocurrió un error'
}

export default function ReporteActividadesSeccion({
  equipos,
  equipoId,
  desde,
  hasta,
  initialActividadId,
  onEquipoChange,
  onDesdeChange,
  onHastaChange,
}: {
  equipos: EquipoOpcion[]
  equipoId: number | null
  desde: string
  hasta: string
  initialActividadId?: number
  onEquipoChange: (id: number | null) => void
  onDesdeChange: (valor: string) => void
  onHastaChange: (valor: string) => void
}) {
  const [actividadSelId, setActividadSelId] = useState<number | null>(
    initialActividadId ?? null,
  )
  // Folio cuya descarga individual está en curso (spinner en su botón).
  // El valor solo se usa mientras la mutación está pendiente; al terminar,
  // la condición `isPending` lo ignora (sin efecto de sincronización).
  const [individualEnCurso, setIndividualEnCurso] = useState<number | null>(
    null,
  )
  const exportar = useExportarReporteActividades()

  const params: ReporteActividadesParams = useMemo(() => {
    const p: ReporteActividadesParams = {}
    if (equipoId !== null) p.equipo_id = equipoId
    if (desde !== '') p.desde = desde
    if (hasta !== '') p.hasta = hasta
    return p
  }, [equipoId, desde, hasta])

  // Listado base (sin operación) alimenta la tabla Y las opciones del
  // selector; con operación elegida se consulta la versión filtrada.
  const listaCompleta = useReporteActividades(params)
  const listaFiltrada = useReporteActividades(
    actividadSelId !== null ? { ...params, actividad_id: actividadSelId } : {},
    actividadSelId !== null,
  )
  const visible = actividadSelId !== null ? listaFiltrada : listaCompleta
  const actividades = visible.data ?? []

  const opciones = (listaCompleta.data ?? []).map((a: Actividad) => ({
    valor: a.actividad_id,
    etiqueta: `${a.folio} · ${fechaCorta(a.fecha)} · ${a.equipo_nombre}`,
  }))

  // La descarga solo tiene sentido con un listado cargado y no vacío.
  const motivoSinExportar = visible.isLoading
    ? 'Cargando actividades…'
    : visible.isError
      ? 'No se pudo cargar el listado de actividades, por lo que no es posible exportar.'
      : actividades.length === 0
        ? 'No hay actividades para los filtros seleccionados; no hay nada que exportar.'
        : undefined

  const paramsConOperacion =
    actividadSelId !== null ? { ...params, actividad_id: actividadSelId } : params

  const reiniciarSeleccion = () => {
    setActividadSelId(null)
    exportar.reiniciar()
  }

  return (
    <ReporteSubseccion
      idPrefix="reportes-actividades"
      descripcion="Actividades de la jornada confirmadas en la subsección ACTIVIDADES de Inventario por Unidad. El XLSX se llena sobre la plantilla oficial, una hoja por folio."
      equipos={equipos}
      equipoId={equipoId}
      desde={desde}
      hasta={hasta}
      onEquipoChange={(id) => {
        reiniciarSeleccion()
        onEquipoChange(id)
      }}
      onDesdeChange={(valor) => {
        reiniciarSeleccion()
        onDesdeChange(valor)
      }}
      onHastaChange={(valor) => {
        reiniciarSeleccion()
        onHastaChange(valor)
      }}
      selectorOperacion={{
        etiqueta: 'Actividad',
        valor: actividadSelId,
        opciones,
        onChange: (id) => {
          setActividadSelId(id)
          exportar.reiniciar()
        },
      }}
      acciones={
        <button
          type="button"
          onClick={() => exportar.exportar('consolidado', paramsConOperacion)}
          disabled={motivoSinExportar !== undefined || exportar.isPending}
          aria-busy={exportar.isPending}
          className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exportar.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Download className="h-4 w-4" aria-hidden="true" />
          )}
          Descargar libro (XLSX)
        </button>
      }
      exportDisabledReason={motivoSinExportar}
    >
      {visible.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando reporte...</p>
        </div>
      )}

      {visible.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">
            No se pudo cargar el reporte de actividades.
          </p>
          <p className="mt-1 text-sm text-red-600">
            {errorMessage(visible.error)}
          </p>
        </div>
      )}

      {!visible.isLoading && !visible.isError && (
        <ReporteActividadesTable
          actividades={actividades}
          onDescargarIndividual={(a) => {
            setIndividualEnCurso(a.actividad_id)
            exportar.exportar('individual', {
              ...params,
              actividad_id: a.actividad_id,
            })
          }}
          descargandoIndividualId={
            exportar.isPending && exportar.status.estado === 'loading'
              ? individualEnCurso
              : null
          }
        />
      )}

      <ReporteActividadesExportFeedback status={exportar.status} />
    </ReporteSubseccion>
  )
}
