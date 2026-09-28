import { useMemo, useState } from 'react'
import axios from 'axios'
import { useDespliegues } from '../hooks/useDespliegues'
import { useEquipoInventario } from '../hooks/useEquipoInventario'
import { useCrearDespliegue } from '../hooks/useCrearDespliegue'
import { useCerrarDespliegue } from '../hooks/useCerrarDespliegue'
import { useToast } from '../hooks/useToasts'
import DespliegueNuevaListaForm from './DespliegueNuevaListaForm'
import DespliegueCierreForm from './DespliegueCierreForm'
import ConfirmDialog from './ConfirmDialog'
import type { CerrarDesplieguePayload } from '../types'

// ============================================================================
// PANEL — DESPLIEGUES DE EQUIPO (FASE 7, wave 2b)
//
// Consume el estado persistido vía hooks (wave 1) y delega la captura de
// intención a los formularios (wave 2a). NUNCA calcula stock ni consumos:
// apertura y cierre se delegan al backend; la UI solo inicia y representa.
//
// Contrato de props: { equipoId }
// ============================================================================

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

export default function DesplieguePanel({ equipoId }: { equipoId: number }) {
  const { pushToast, pushError } = useToast()

  const {
    isLoading: desplieguesLoading,
    isError: desplieguesError,
    error: desplieguesErrorObj,
    abierta,
  } = useDespliegues(equipoId)

  const inventarioQuery = useEquipoInventario(equipoId)

  const crearMut = useCrearDespliegue(equipoId)
  const cerrarMut = useCerrarDespliegue(equipoId)

  // Payload de cierre pendiente de confirmación (estado temporal UX).
  const [cierrePendiente, setCierrePendiente] =
    useState<CerrarDesplieguePayload | null>(null)
  const [cierreConfirmOpen, setCierreConfirmOpen] = useState(false)

  // Mapa de PRESENTACIÓN material_id → descripción (solo etiquetas para el
  // formulario de cierre; el stock lo resuelve el backend).
  const descripcionPorMaterial = useMemo(() => {
    const mapa: Record<number, string> = {}
    for (const fila of inventarioQuery.data ?? []) {
      mapa[fila.material_id] = fila.descripcion
    }
    return mapa
  }, [inventarioQuery.data])

  // ── Estados FAIL-CLOSED (loading / error) ─────────────────────────────────

  if (desplieguesLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
        <p className="text-slate-500">Cargando despliegues...</p>
      </div>
    )
  }

  if (desplieguesError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-red-700">
          No se pudieron cargar los despliegues del equipo.
        </p>
        <p className="mt-1 text-sm text-red-600">
          {errorMessage(desplieguesErrorObj)}
        </p>
      </div>
    )
  }

  // ── Despliegue ABIERTO: resumen + cierre con sobrantes ────────────────────

  if (abierta) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-slate-800">
              Despliegue abierto — {abierta.fecha}
            </h3>
            <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
              ABIERTA
            </span>
          </div>
          {abierta.observaciones && (
            <p className="mt-2 text-sm text-slate-600">{abierta.observaciones}</p>
          )}
          <table className="mt-3 w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Material</th>
                <th className="px-3 py-2">Cantidad tomada</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {abierta.items.map((item) => (
                <tr key={item.id}>
                  <td className="px-3 py-2 text-slate-700">
                    {descripcionPorMaterial[item.material_id] ?? item.material_id}
                  </td>
                  <td className="px-3 py-2 font-semibold text-slate-700">
                    {item.cantidad_tomada.toLocaleString('es-MX')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-slate-800">
            Cierre del despliegue
          </h4>
          <DespliegueCierreForm
            items={abierta.items}
            materiales={descripcionPorMaterial}
            onSubmit={(payload) => {
              setCierrePendiente(payload)
              setCierreConfirmOpen(true)
            }}
            onCancel={() => undefined}
          />
        </div>

        <ConfirmDialog
          open={cierreConfirmOpen}
          title="Cerrar despliegue"
          message="Se registrarán los sobrantes y el consumo se descontará del inventario del equipo. ¿Confirmar?"
          confirmLabel="Confirmar"
          onConfirm={() => {
            if (cierrePendiente) {
              cerrarMut.mutate(
                { despliegueId: abierta.id, payload: cierrePendiente },
                {
                  onSuccess: () => {
                    pushToast('Despliegue cerrado correctamente')
                    setCierreConfirmOpen(false)
                    setCierrePendiente(null)
                  },
                  onError: (err) => pushError(errorMessage(err)),
                },
              )
            }
          }}
          onCancel={() => {
            setCierreConfirmOpen(false)
            setCierrePendiente(null)
          }}
        />
      </div>
    )
  }

  // ── Sin despliegue abierto: apertura de nueva lista ───────────────────────

  return (
    <div className="space-y-4">
      {inventarioQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando inventario del equipo...</p>
        </div>
      )}

      {inventarioQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="text-red-700">
            No se pudo obtener el inventario del equipo.
          </p>
          <p className="mt-1 text-sm text-red-600">
            {errorMessage(inventarioQuery.error)}
          </p>
        </div>
      )}

      {!inventarioQuery.isLoading && !inventarioQuery.isError && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-base font-semibold text-slate-800">
            Nueva lista de despliegue
          </h3>
          <DespliegueNuevaListaForm
            materiales={inventarioQuery.data ?? []}
            onSubmit={(payload) =>
              crearMut.mutate(payload, {
                onSuccess: () => pushToast('Despliegue creado'),
                onError: (err) => pushError(errorMessage(err)),
              })
            }
            onCancel={() => undefined}
          />
        </div>
      )}
    </div>
  )
}
