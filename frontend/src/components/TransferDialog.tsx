import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import Modal from './Modal'
import type { InventoryRow } from '../types'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'

interface TransferDialogProps {
  open: boolean
  material: InventoryRow
  warehouses: { id: string; name: string }[]
  onSubmit: (destination: string, quantity: number) => void
  onCancel: () => void
}

function SummaryField({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="border-b border-slate-100 py-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <div className="mt-0.5 text-sm text-slate-700">{children}</div>
    </div>
  )
}

export default function TransferDialog({
  open,
  material,
  warehouses,
  onSubmit,
  onCancel,
}: TransferDialogProps) {
  const [destination, setDestination] = useState('')
  const [quantity, setQuantity] = useState('')

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (destination && quantity !== '') {
      onSubmit(destination, Number(quantity))
    }
  }

  const destinations = warehouses.filter((w) => w.id !== material.almacen_id)

  return (
    <Modal open={open} title="Transferir Stock" onClose={onCancel}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <SummaryField label={MATERIAL_FIELD_LABELS.descripcion}>
            {material.descripcion ?? '—'}
          </SummaryField>
          <SummaryField label={MATERIAL_FIELD_LABELS.stock_actual}>
            {material.stock_actual.toLocaleString('es-MX')}
          </SummaryField>
          <SummaryField label={MATERIAL_FIELD_LABELS.stock_minimo}>
            {material.stock_minimo != null ? material.stock_minimo : '—'}
          </SummaryField>
          <SummaryField label={MATERIAL_FIELD_LABELS.alerta_stock}>
            {material.alerta_stock ? (
              <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                Alerta Stock
              </span>
            ) : (
              'Sin alerta'
            )}
          </SummaryField>
          <SummaryField label={MATERIAL_FIELD_LABELS.um}>
            {material.um ?? '—'}
          </SummaryField>
          <SummaryField label={MATERIAL_FIELD_LABELS.codigo}>
            <span className="font-mono">{material.codigo}</span>
          </SummaryField>
        </div>

        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Almacén Origen
          </label>
          <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {material.almacen}
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Almacén Destino
          </label>
          <select
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Seleccionar almacén…</option>
            {destinations.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Cantidad
          </label>
          <input
            type="number"
            min={1}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={!destination || quantity === ''}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Transferir
          </button>
        </div>
      </form>
    </Modal>
  )
}
