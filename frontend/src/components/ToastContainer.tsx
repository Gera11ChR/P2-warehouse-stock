import type { ToastVariant } from '../hooks/toastContext'

interface ToastContainerProps {
  toasts: { id: number; message: string; variant: ToastVariant }[]
  onDismiss: (id: number) => void
}

const VARIANT_CLASS: Record<ToastVariant, string> = {
  success: 'bg-green-600',
  error: 'bg-red-600',
}

export default function ToastContainer({
  toasts,
  onDismiss,
}: ToastContainerProps) {
  if (toasts.length === 0) {
    return null
  }
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-3 rounded-md px-4 py-3 text-white shadow-lg ${VARIANT_CLASS[toast.variant]}`}
        >
          <span className="text-sm font-medium">{toast.message}</span>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            className="text-white/80 hover:text-white"
            aria-label="Cerrar notificación"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
