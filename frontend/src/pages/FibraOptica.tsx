import { useEffect, useState } from 'react'
import { listInventory } from '../services/inventory'
import { listFiberVariants } from '../services/fiberOptics'
import { getMaterial } from '../services/materials'
import InventoryTable from '../components/InventoryTable'
import MaterialDetailDrawer from '../components/MaterialDetailDrawer'
import type { FiberVariant, InventoryRow, Material } from '../types'

interface FibraOpticaProps {
  sub: string
}

export default function FibraOptica({ sub }: FibraOpticaProps) {
  const [view, setView] = useState<'paquete' | 'en-uso'>(
    sub === 'en-uso' ? 'en-uso' : 'paquete',
  )
  const [fiberRows, setFiberRows] = useState<InventoryRow[]>([])
  const [variants, setVariants] = useState<FiberVariant[]>([])
  const [selectedVariant, setSelectedVariant] = useState<FiberVariant | null>(null)
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null)

  useEffect(() => {
    listInventory().then((items) => {
      setFiberRows(items.filter((row) => row.tipo === 'FIBRA'))
    })
  }, [])

  useEffect(() => {
    listFiberVariants().then(setVariants)
  }, [])

  const handleSelectVariant = async (variant: FiberVariant) => {
    setSelectedVariant(variant)
    try {
      const material = await getMaterial(variant.codigo)
      setSelectedMaterial(material)
    } catch {
      setSelectedMaterial(null)
    }
  }

  const alertaStock = selectedVariant
    ? selectedMaterial?.stock_minimo != null &&
      selectedVariant.stock_actual <= selectedMaterial.stock_minimo
    : false

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setView('paquete')}
          className={`px-4 py-2 text-sm font-medium ${
            view === 'paquete'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Paquete
        </button>
        <button
          type="button"
          onClick={() => setView('en-uso')}
          className={`px-4 py-2 text-sm font-medium ${
            view === 'en-uso'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          En Uso
        </button>
      </div>

      {view === 'paquete' ? (
        <InventoryTable
          rows={fiberRows}
          selectedCodigo={null}
          onSelect={() => undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">Variante</th>
                <th className="px-4 py-3">Metros Restantes</th>
                <th className="px-4 py-3">Stock Actual</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {variants.map((variant) => (
                <tr
                  key={variant.id}
                  onClick={() => handleSelectVariant(variant)}
                  className="cursor-pointer transition-colors hover:bg-blue-50"
                >
                  <td className="px-4 py-3 font-mono text-slate-700">
                    {variant.codigo}
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    {variant.descripcion ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{variant.variante}</td>
                  <td className="px-4 py-3 font-semibold text-blue-600">
                    {variant.metros_restantes.toLocaleString('es-MX')} m
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    {variant.stock_actual.toLocaleString('es-MX')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <MaterialDetailDrawer
        open={selectedVariant !== null}
        onClose={() => {
          setSelectedVariant(null)
          setSelectedMaterial(null)
        }}
        descripcion={selectedVariant?.descripcion ?? null}
        stockActual={selectedVariant?.stock_actual ?? 0}
        stockMinimo={selectedMaterial?.stock_minimo ?? null}
        alertaStock={alertaStock}
        um={selectedMaterial?.um ?? null}
        codigo={selectedVariant?.codigo ?? ''}
        metrosRestantes={selectedVariant?.metros_restantes ?? null}
        onModificar={() => undefined}
        onEliminar={() => undefined}
        onTransferir={() => undefined}
      />
    </div>
  )
}
