import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { listEquipos } from '../services/equipos'
import { useExportarReporte, useReporteActas } from '../hooks/useReportes'
import Tabs from '../components/Tabs'
import ReporteSubseccion from '../components/ReporteSubseccion'
import type { EquipoOpcion } from '../components/ReporteSubseccion'
import ReporteConsumoTable from '../components/ReporteConsumoTable'
import ReporteEntregaTable from '../components/ReporteEntregaTable'
import ReporteActividadesSeccion from '../components/ReporteActividadesSeccion'
import type { Acta, ReporteParams } from '../types'

// ============================================================================
// REPORTES — subsecciones ENTREGA, CONSUMO y ACTIVIDADES (REQ-P2-REP-005,
// REQ-REP-001/012/013/014)
//
// Contenedor de la vista: gestiona la pestaña activa y los filtros
// compartidos (Unidad / Desde / Hasta) y delega cada subsección a su
// contenedor, que posee SUS propias consultas y su exportación:
//  - ReporteActasSeccion (Entrega / Consumo): useReporteActas +
//    useExportarReporte + selector de operación (Acta / Seguimiento,
//    REQ-REP-014). El backend ya acepta acta_id; aquí solo se envía.
//  - ReporteActividadesSeccion: useReporteActividades +
//    useExportarReporteActividades + selector de operación (Actividad).
// El frontend no agrega ni transforma datos del reporte.
// ============================================================================

const SUBSECCIONES = [
  { value: 'entrega', label: 'Entrega' },
  { value: 'consumo', label: 'Consumo' },
  { value: 'actividades', label: 'Actividades' },
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

const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-MX')

/** Props de navegación (opcionales): permiten llegar desde los avisos de
 *  acta generada (Transferencias / Seguimiento) y del aviso de actividad
 *  confirmada (Inventario por Unidad) directo a la subsección correcta,
 *  pre-filtrada por Unidad y, para Actividades, por folio. */
interface ReportesProps {
  initialSub?: string
  initialEquipoId?: number
  initialActividadId?: number
}

function subseccionInicial(sub?: string): Subseccion {
  if (sub === 'consumo') return 'consumo'
  if (sub === 'actividades') return 'actividades'
  return 'entrega'
}

interface FiltrosCompartidosProps {
  equipos: EquipoOpcion[]
  equipoId: number | null
  desde: string
  hasta: string
  onEquipoChange: (id: number | null) => void
  onDesdeChange: (valor: string) => void
  onHastaChange: (valor: string) => void
}

function ReporteActasSeccion({
  tipo,
  equipos,
  equipoId,
  desde,
  hasta,
  onEquipoChange,
  onDesdeChange,
  onHastaChange,
}: FiltrosCompartidosProps & { tipo: 'entrega' | 'consumo' }) {
  const [operacionSelId, setOperacionSelId] = useState<number | null>(null)
  const exportar = useExportarReporte(tipo)

  const params: ReporteParams = useMemo(() => {
    const p: ReporteParams = {}
    if (equipoId !== null) p.equipo_id = equipoId
    if (desde !== '') p.desde = desde
    if (hasta !== '') p.hasta = hasta
    return p
  }, [equipoId, desde, hasta])

  // Listado base alimenta la tabla y las opciones del selector de operación
  // (Acta / Seguimiento); con operación elegida se consulta la versión
  // filtrada por el servidor (REQ-REP-014).
  const listaCompleta = useReporteActas(tipo, params)
  const listaFiltrada = useReporteActas(
    tipo,
    operacionSelId !== null ? { ...params, acta_id: operacionSelId } : {},
    operacionSelId !== null,
  )
  const visible = operacionSelId !== null ? listaFiltrada : listaCompleta
  const actas: Acta[] = visible.data ?? []

  const opciones = (listaCompleta.data ?? []).map((acta: Acta) => ({
    valor: acta.acta_id,
    etiqueta:
      tipo === 'entrega'
        ? `Acta #${acta.acta_id} · ${fechaCorta(acta.fecha)} · ${acta.equipo_nombre ?? '—'}`
        : `Seguimiento #${acta.seguimiento_id ?? '—'} · Acta #${acta.acta_id} · ${fechaCorta(acta.fecha)} · ${acta.equipo_nombre ?? '—'}`,
  }))

  const motivoSinExportar = visible.isLoading
    ? 'Cargando actas…'
    : visible.isError
      ? 'No se pudo cargar el listado de actas, por lo que no es posible exportar.'
      : actas.length === 0
        ? 'No hay actas para los filtros seleccionados; no hay nada que exportar.'
        : undefined

  const paramsConOperacion =
    operacionSelId !== null ? { ...params, acta_id: operacionSelId } : params

  const reiniciarSeleccion = () => {
    setOperacionSelId(null)
    exportar.reiniciar()
  }

  const contenido = (
    <>
      {visible.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando reporte...</p>
        </div>
      )}

      {visible.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-red-700">
            No se pudo cargar el reporte de {tipo}.
          </p>
          <p className="mt-1 text-sm text-red-600">
            {errorMessage(visible.error)}
          </p>
        </div>
      )}

      {!visible.isLoading &&
        !visible.isError &&
        (tipo === 'entrega' ? (
          <ReporteEntregaTable actas={actas} />
        ) : (
          <ReporteConsumoTable actas={actas} />
        ))}
    </>
  )

  return (
    <ReporteSubseccion
      tipo={tipo}
      idPrefix={`reportes-${tipo}`}
      descripcion={
        tipo === 'entrega'
          ? 'Actas de Entrega: se generan al confirmar una transferencia (TRANSF).'
          : 'Actas de Consumo: se generan al cerrar un seguimiento.'
      }
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
        etiqueta: tipo === 'entrega' ? 'Acta' : 'Seguimiento',
        valor: operacionSelId,
        opciones,
        onChange: (id) => {
          setOperacionSelId(id)
          exportar.reiniciar()
        },
      }}
      onExportNormal={() => exportar.exportar('normal', paramsConOperacion)}
      onExportExtenso={() => exportar.exportar('extenso', paramsConOperacion)}
      exportDisabled={motivoSinExportar !== undefined}
      exportDisabledReason={motivoSinExportar}
      exportStatus={exportar.status}
    >
      {contenido}
    </ReporteSubseccion>
  )
}

export default function Reportes({
  initialSub,
  initialEquipoId,
  initialActividadId,
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

  const equiposActivos = equipos.filter((e) => e.is_active)
  const filtrosProps: FiltrosCompartidosProps = {
    equipos: equiposActivos,
    equipoId,
    desde,
    hasta,
    onEquipoChange: setEquipoId,
    onDesdeChange: setDesde,
    onHastaChange: setHasta,
  }

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
          <ReporteActasSeccion tipo="entrega" {...filtrosProps} />
        )}

        {subseccion === 'consumo' && (
          <ReporteActasSeccion tipo="consumo" {...filtrosProps} />
        )}

        {subseccion === 'actividades' && (
          <ReporteActividadesSeccion
            {...filtrosProps}
            initialActividadId={initialActividadId}
          />
        )}
      </Tabs>
    </div>
  )
}
