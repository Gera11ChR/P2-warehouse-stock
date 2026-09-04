import type { ReactNode } from 'react'
import { ArrowRightLeft, Pencil, Trash2, X } from 'lucide-react'

interface MaterialDetailDrawerProps {
  open: boolean
  onClose: () => void
  descripcion: string | null
  stockActual: number
  stockMinimo: number | null
  alertaStock: boolean
  um: string | null
  codigo: string
  metrosRestantes?: number | null
  onModificar: () => void
  onEliminar: () => void
  onTransferir: () => void
}

function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="border-b border-slate-100 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <div className="mt-1 text-sm text-slate-800">{children}</div>
    </div>
  )
}

export default function MaterialDetailDrawer({
  open,
  onClose,
  descripcion,
  stockActual,
  stockMinimo,
  alertaStock,
  um,
  codigo,
  metrosRestantes,
  onModificar,
  onEliminar,
  onTransferir,
}: MaterialDetailDrawerProps) {
  if (!open) {
    return null
  }
  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-96 flex-col border-l border-slate-200 bg-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-semibold text-slate-800">Detalle del Material</h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Cerrar"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-2">
        <Field label="Descripción">
          {descripcion ?? <span className="text-slate-400">—</span>}
        </Field>
        <Field label="Stock Actual">{stockActual.toLocaleString('es-MX')}</Field>
        <Field label="Stock Mínimo">
          {stockMinimo != null ? stockMinimo : <span className="text-slate-400">—</span>}
        </Field>
        <Field label="Alerta Stock">
          {alertaStock ? (
            <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
              Alerta Stock
            </span>
          ) : (
            <span className="text-slate-400">Sin alerta</span>
          )}
        </Field>
        <Field label="U.M.">{um ?? <span className="text-slate-400">—</span>}</Field>
        <Field label="Código (SKU)">
          <span className="font-mono">{codigo}</span>
        </Field>

        {metrosRestantes != null && (
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-500">
              Metros Restantes
            </p>
            <p className="mt-1 text-xl font-semibold text-blue-700">
              {metrosRestantes.toLocaleString('es-MX')} m
            </p>
          </div>
        )}
      </div>

      <div className="flex gap-2 border-t border-slate-200 px-5 py-4">
        <button
          type="button"
          onClick={onModificar}
          className="flex flex-1 items-center justify-center gap-1 rounded-md bg-yellow-500 px-3 py-2 text-sm font-medium text-white hover:bg-yellow-600"
        >
          <Pencil className="h-4 w-4" /> Modificar
        </button>
        <button
          type="button"
          onClick={onEliminar}
          className="flex flex-1 items-center justify-center gap-1 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          <Trash2 className="h-4 w-4" /> Eliminar
        </button>
        <button
          type="button"
          onClick={onTransferir}
          className="flex flex-1 items-center justify-center gap-1 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <ArrowRightLeft className="h-4 w-4" /> Transferir Stock
        </button>
      </div>
    </aside>
  )
}
