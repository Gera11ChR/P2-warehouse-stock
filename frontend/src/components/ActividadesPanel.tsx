import { useState } from 'react'
import { CheckCircle2, Info, X } from 'lucide-react'
import { mensajeErrorApi as errorMessage } from '../utils/errorMensaje'
import { useActividadPendiente, useCrearActividad } from '../hooks/useActividades'
import { useAppNavigation } from '../hooks/useAppNavigation'
import { useToast } from '../hooks/useToasts'
import ActividadesFormulario from './ActividadesFormulario'
import ActividadesMaterialesConsumidos from './ActividadesMaterialesConsumidos'
import ConfirmDialog from './ConfirmDialog'
import type { Actividad, ActividadCreatePayload } from '../types'

// ============================================================================
// PANEL — ACTIVIDADES DE LA UNIDAD (Etapa 1, REQ-ACT-001..017)
//
// Consume el estado persistido vía hooks y delega la captura al formulario.
// NUNCA decide folio, fecha, materiales ni valor unitario: los asigna
// PostgreSQL y aquí solo se representan.
//
// Workflow (form-agent): inicio (carga del pendiente) → captura →
// revisión/confirmación (ConfirmDialog) → resultado (pendiente / exitosa /
// rechazada, RF-17) → recuperación ante error (los datos escritos se
// conservan: el formulario no se desmonta al fallar).
//
// Contrato de props: { equipoId, equipoNombre? }
// ============================================================================

function fechaLocal(iso: string): string {
  // Hora local del navegador del usuario (supuesto aprobado, REQ-ACT-009).
  return new Date(iso).toLocaleString('es-MX')
}

export default function ActividadesPanel({
  equipoId,
  equipoNombre,
}: {
  equipoId: number
  equipoNombre?: string | null
}) {
  const { pushToast, pushError } = useToast()
  const navigate = useAppNavigation()
  const pendienteQuery = useActividadPendiente(equipoId)
  const crearMut = useCrearActividad(equipoId)

  const [payloadPendiente, setPayloadPendiente] =
    useState<ActividadCreatePayload | null>(null)
  // Última actividad confirmada en ESTA unidad (el aviso solo aplica a ella).
  const [confirmada, setConfirmada] = useState<Actividad | null>(null)
  const avisoConfirmada =
    confirmada !== null && confirmada.equipo_id === equipoId ? confirmada : null

  if (pendienteQuery.isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
        <p className="text-slate-500">Cargando actividades...</p>
      </div>
    )
  }

  if (pendienteQuery.isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-red-700">
          No se pudo consultar el seguimiento pendiente de actividad.
        </p>
        <p className="mt-1 text-sm text-red-600">
          {errorMessage(pendienteQuery.error)}
        </p>
      </div>
    )
  }

  const pendiente = pendienteQuery.data?.seguimiento ?? null

  return (
    <div className="space-y-4">
      {avisoConfirmada && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4"
        >
          <CheckCircle2
            className="mt-0.5 h-5 w-5 shrink-0 text-green-700"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-green-900">
              Actividad confirmada — Folio {avisoConfirmada.folio}
            </p>
            <p className="mt-1 text-sm text-green-800">
              Registrada
              {equipoNombre ? ` para la unidad ${equipoNombre}` : ''} el{' '}
              {fechaLocal(avisoConfirmada.fecha)}. El reporte se emite desde la
              sección Reportes.
            </p>
            {navigate && (
              <button
                type="button"
                onClick={() =>
                  navigate({
                    page: 'reportes',
                    sub: 'actividades',
                    equipoId,
                    actividadId: avisoConfirmada.actividad_id,
                  })
                }
                className="mt-2 rounded-md border border-green-300 px-3 py-1.5 text-sm font-medium text-green-800 hover:bg-green-100"
              >
                Ir a Reportes › Actividades
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => setConfirmada(null)}
            aria-label="Cerrar aviso de actividad confirmada"
            className="rounded p-1 text-green-700 hover:bg-green-100"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {pendiente === null && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4"
        >
          <Info
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-700"
            aria-hidden="true"
          />
          <p className="text-sm text-amber-900">
            No hay un seguimiento cerrado pendiente de actividad. Cierre un
            seguimiento en la subsección CONSUMO para poder registrar la
            actividad.
          </p>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-2">
          <ActividadesMaterialesConsumidos materiales={pendiente?.materiales ?? []} />
          {pendiente && (
            <p className="text-xs text-slate-500">
              Seguimiento #{pendiente.seguimiento_id} cerrado el{' '}
              {fechaLocal(pendiente.fecha_cierre)}.
            </p>
          )}
        </div>

        <ActividadesFormulario
          key={pendiente?.seguimiento_id ?? 'sin-pendiente'}
          seguimientoId={pendiente?.seguimiento_id ?? null}
          enviando={crearMut.isPending}
          onSubmit={setPayloadPendiente}
        />
      </div>

      <ConfirmDialog
        open={payloadPendiente !== null}
        title="Confirmar actividades"
        message="Se registrará la actividad con folio y fecha automáticos y los materiales consumidos del seguimiento. El registro no podrá editarse después. ¿Confirmar?"
        confirmLabel="Confirmar"
        onConfirm={() => {
          if (!payloadPendiente) return
          crearMut.mutate(payloadPendiente, {
            onSuccess: (actividad) => {
              pushToast(`Actividad ${actividad.folio} confirmada`)
              setConfirmada(actividad)
              setPayloadPendiente(null)
            },
            onError: (err) => {
              // Rechazada: se informa el motivo del backend y los datos
              // escritos se conservan para reintentar.
              pushError(errorMessage(err))
              setPayloadPendiente(null)
            },
          })
        }}
        onCancel={() => setPayloadPendiente(null)}
      />
    </div>
  )
}
