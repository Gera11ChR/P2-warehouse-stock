import { useMemo, useState } from 'react'
import { mensajeErrorApi as errorMessage } from '../utils/errorMensaje'
import { useSeguimientos } from '../hooks/useSeguimientos'
import { useEquipoInventario } from '../hooks/useEquipoInventario'
import { useCrearSeguimiento } from '../hooks/useCrearSeguimiento'
import { useCerrarSeguimiento } from '../hooks/useCerrarSeguimiento'
import { useToast } from '../hooks/useToasts'
import SeguimientoNuevaListaForm from './SeguimientoNuevaListaForm'
import SeguimientoCierreForm from './SeguimientoCierreForm'
import ConfirmDialog from './ConfirmDialog'
import ActaGeneradaAviso from './ActaGeneradaAviso'
import { useAppNavigation } from '../hooks/useAppNavigation'
import type { CerrarSeguimientoPayload } from '../types'

// ============================================================================
// PANEL — SEGUIMIENTOS DE CONSUMO DE EQUIPO (FASE 7, wave 2b)
//
// Consume el estado persistido vía hooks (wave 1) y delega la captura de
// intención a los formularios (wave 2a). NUNCA calcula stock ni consumos:
// apertura y cierre se delegan al backend; la UI solo inicia y representa.
//
// Contrato de props: { equipoId, equipoNombre? }
//
// Flujo de cierre (REQ-P2-CON-005): el aviso «Acta de Consumo generada» solo
// se muestra en el `onSuccess` del cierre (el servidor ya aceptó el cierre y
// registró el acta en la misma transacción). Ofrece ir a Reportes > Consumo
// pre-filtrado por esta unidad (si hay navegación disponible).
// ============================================================================

export default function SeguimientoPanel({
  equipoId,
  equipoNombre,
}: {
  equipoId: number
  equipoNombre?: string | null
}) {
  const { pushToast, pushError } = useToast()
  const navigate = useAppNavigation()

  // Equipo del último cierre aceptado (el aviso solo aplica a ESE equipo:
  // evita mostrar un acta ajena si el operador cambia de equipo).
  const [actaConsumoEquipoId, setActaConsumoEquipoId] = useState<number | null>(
    null,
  )
  const avisoActa =
    actaConsumoEquipoId === equipoId ? (
      <ActaGeneradaAviso
        tipo="CONSUMO"
        equipoNombre={equipoNombre}
        onVerActa={
          navigate
            ? () =>
                navigate({
                  page: 'reportes',
                  sub: 'consumo',
                  equipoId,
                })
            : undefined
        }
        onDismiss={() => setActaConsumoEquipoId(null)}
      />
    ) : null

  const {
    isLoading: seguimientosLoading,
    isError: seguimientosError,
    error: seguimientosErrorObj,
    abierta,
  } = useSeguimientos(equipoId)

  const inventarioQuery = useEquipoInventario(equipoId)

  const crearMut = useCrearSeguimiento(equipoId)
  const cerrarMut = useCerrarSeguimiento(equipoId)

  // Payload de cierre pendiente de confirmación (estado temporal UX).
  const [cierrePendiente, setCierrePendiente] =
    useState<CerrarSeguimientoPayload | null>(null)
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

  if (seguimientosLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
        <p className="text-slate-500">Cargando seguimientos...</p>
      </div>
    )
  }

  if (seguimientosError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-red-700">
          No se pudieron cargar los seguimientos de consumo de la unidad.
        </p>
        <p className="mt-1 text-sm text-red-600">
          {errorMessage(seguimientosErrorObj)}
        </p>
      </div>
    )
  }

  // ── Seguimiento ABIERTO: resumen + cierre con consumidos ────────────────────

  if (abierta) {
    return (
      <div className="space-y-4">
        {avisoActa}
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-slate-800">
              Seguimiento abierto — {abierta.fecha}
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
            Cierre del seguimiento
          </h4>
          <SeguimientoCierreForm
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
          title="Cerrar seguimiento"
          message="Se registrará lo consumido y se descontará del inventario de la unidad. ¿Confirmar?"
          confirmLabel="Confirmar"
          onConfirm={() => {
            if (cierrePendiente) {
              cerrarMut.mutate(
                { seguimientoId: abierta.id, payload: cierrePendiente },
                {
                  onSuccess: () => {
                    pushToast('Seguimiento cerrado correctamente')
                    setActaConsumoEquipoId(equipoId)
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

  // ── Sin seguimiento abierto: apertura de nueva lista ───────────────────────

  return (
    <div className="space-y-4">
      {avisoActa}
      {inventarioQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando inventario de la unidad...</p>
        </div>
      )}

      {inventarioQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="text-red-700">
            No se pudo obtener el inventario de la unidad.
          </p>
          <p className="mt-1 text-sm text-red-600">
            {errorMessage(inventarioQuery.error)}
          </p>
        </div>
      )}

      {!inventarioQuery.isLoading && !inventarioQuery.isError && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SeguimientoNuevaListaForm
            materiales={inventarioQuery.data ?? []}
            isLoading={inventarioQuery.isFetching}
            editable={!crearMut.isPending}
            onSubmit={(payload) =>
              crearMut.mutate(payload, {
                onSuccess: () => pushToast('Seguimiento creado'),
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
