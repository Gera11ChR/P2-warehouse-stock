import { useId, useRef } from 'react'
import type { FormEvent, ReactNode, RefObject } from 'react'
import { Loader2, X } from 'lucide-react'
import { useDialogA11y } from '../hooks/useDialogA11y'

// ============================================================================
// DIÁLOGO BASE DE OPERADORES RÁPIDOS DE INVENTARIO (+Cantidad / Mover)
//
// Contenedor accesible y presentacional (REQ-P2-INV-001/003/005). Define la
// ESTRUCTURA de la confirmación operativa para una operación de alto riesgo:
//
//   1. RESUMEN (contexto fijo): operación, material, origen, destino,
//      cantidad — responde «¿qué, cuánto, desde dónde, hacia dónde?».
//   2. CUERPO (slot `children`): campos del formulario (@form-agent).
//   3. PROYECCIÓN (slot `proyeccion`): resultado visual estimado, siempre
//      rotulado «Proyección visual»: NO es el saldo confirmado; la
//      autoridad es PostgreSQL (REGLA CONSTITUCIONAL UX).
//   4. ERROR (`error`): texto YA traducido a contexto operativo; se anuncia
//      con role="alert". No se inventa contenido: refleja la respuesta API.
//   5. ACCIONES: Cancelar + Confirmar con etiqueta explícita
//      («Mover 20 PZ a …», nunca «¿Está seguro?»).
//
// Doble envío: mientras `isSubmitting` el confirmar queda bloqueado, Esc no
// cierra y el foco permanece dentro. Cierre/foco/Esc: useDialogA11y.
//
// La clave de idempotencia (REQ-P2-INV-007) NO la conoce este contenedor: la
// genera `useOperadorRapido` al ABRIR el diálogo y la reutiliza en reintentos.
// ============================================================================

export interface ResumenOperacionItem {
  label: string
  value: ReactNode
}

export interface OperadorRapidoDialogProps {
  open: boolean
  titulo: string
  descripcion?: string
  onClose: () => void
  resumen: ResumenOperacionItem[]
  /** Slot: campos del formulario. */
  children: ReactNode
  /** Slot: resultado visual estimado (se rotula como proyección). */
  proyeccion?: ReactNode
  /** Mensaje de error ya traducido a contexto operativo. */
  error?: string | null
  confirmLabel: string
  onConfirm: () => void
  confirmDisabled?: boolean
  /** Motivo visible cuando Confirmar está deshabilitado de forma estructural. */
  confirmDisabledReason?: string
  isSubmitting?: boolean
  /** Control que recibe el foco inicial (por defecto el primer enfocable). */
  initialFocusRef?: RefObject<HTMLElement | null>
}

export default function OperadorRapidoDialog({
  open,
  titulo,
  descripcion,
  onClose,
  resumen,
  children,
  proyeccion,
  error,
  confirmLabel,
  onConfirm,
  confirmDisabled = false,
  confirmDisabledReason,
  isSubmitting = false,
  initialFocusRef,
}: OperadorRapidoDialogProps) {
  const contenedorRef = useRef<HTMLDivElement>(null)
  const tituloId = useId()
  const descripcionId = useId()
  const motivoId = useId()

  useDialogA11y({
    open,
    onClose,
    containerRef: contenedorRef,
    initialFocusRef,
    closeDisabled: isSubmitting,
  })

  if (!open) return null

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!confirmDisabled && !isSubmitting) onConfirm()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40">
      <div
        ref={contenedorRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        aria-describedby={descripcion ? descripcionId : undefined}
        tabIndex={-1}
        className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-lg bg-white shadow-xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <h3 id={tituloId} className="text-lg font-semibold text-slate-800">
              {titulo}
            </h3>
            {descripcion && (
              <p id={descripcionId} className="mt-1 text-sm text-slate-500">
                {descripcion}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Cerrar"
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <dl
              aria-label="Resumen de la operación"
              className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"
            >
              {resumen.map((item) => (
                <div key={item.label} className="contents">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {item.label}
                  </dt>
                  <dd className="text-slate-800">{item.value}</dd>
                </div>
              ))}
            </dl>

            {children}

            {proyeccion && (
              <div
                aria-live="polite"
                className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900"
              >
                <span className="mr-1 inline-flex rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
                  Proyección visual
                </span>
                {proyeccion}
                <p className="mt-1 text-xs text-blue-700">
                  El saldo definitivo lo confirma el servidor.
                </p>
              </div>
            )}

            {error && (
              <p
                role="alert"
                className="rounded-md border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-700"
              >
                {error}
              </p>
            )}
          </div>

          <div className="border-t border-slate-200 px-5 py-3">
            {confirmDisabledReason && (
              <p id={motivoId} className="mb-2 text-xs text-slate-500">
                {confirmDisabledReason}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={confirmDisabled || isSubmitting}
                aria-busy={isSubmitting}
                aria-describedby={confirmDisabledReason ? motivoId : undefined}
                className="flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting && (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                )}
                {isSubmitting ? 'Procesando…' : confirmLabel}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
