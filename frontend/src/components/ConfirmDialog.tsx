import { useId, useRef } from 'react'
import { useDialogA11y } from '../hooks/useDialogA11y'

// ============================================================================
// DIÁLOGO DE CONFIRMACIÓN (compartido)
//
// Accesibilidad (REQ-REF-016): `role="dialog"` + `aria-modal="true"` con
// nombre (`aria-labelledby` → título) y descripción (`aria-describedby` →
// mensaje). Gestión de foco con `useDialogA11y`: al abrir el foco pasa a
// «Cancelar» (opción segura ante una acción destructiva; Enter no confirma
// por accidente), Tab/Shift+Tab quedan atrapados dentro, Esc cancela y al
// cerrar el foco vuelve al elemento que abrió el diálogo.
// ============================================================================

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Eliminar',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const contenedorRef = useRef<HTMLDivElement>(null)
  const cancelarRef = useRef<HTMLButtonElement>(null)
  const tituloId = useId()
  const mensajeId = useId()

  // Los hooks van antes del retorno temprano (reglas de hooks).
  useDialogA11y({
    open,
    onClose: onCancel,
    containerRef: contenedorRef,
    initialFocusRef: cancelarRef,
  })

  if (!open) {
    return null
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40">
      <div
        ref={contenedorRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        aria-describedby={mensajeId}
        tabIndex={-1}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h3 id={tituloId} className="text-lg font-semibold text-slate-800">
          {title}
        </h3>
        <p id={mensajeId} className="mt-2 text-sm text-slate-600">
          {message}
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            ref={cancelarRef}
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
