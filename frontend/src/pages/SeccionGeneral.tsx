import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import KpiCards from '../components/KpiCards'
import FilterToolbar from '../components/FilterToolbar'
import type { FilterState } from '../components/FilterToolbar'
import InventoryTable from '../components/InventoryTable'
import MaterialDetailDrawer from '../components/MaterialDetailDrawer'
import BulkSearch from '../components/BulkSearch'
import Modal from '../components/Modal'
import MaterialForm from '../components/MaterialForm'
import ConfirmDialog from '../components/ConfirmDialog'
import TransferDialog from '../components/TransferDialog'
import { listInventory } from '../services/inventory'
import {
  createMaterial,
  deleteMaterial,
  updateMaterial,
} from '../services/materials'
import type { MaterialPayload } from '../services/materials'
import { createTransfer } from '../services/transfers'
import { useToast } from '../hooks/useToasts'
import type { InventoryRow } from '../types'

const PAGE_SIZE = 10

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

export default function SeccionGeneral({
  globalSearch,
}: {
  globalSearch: string
}) {
  const { pushToast, pushError } = useToast()
  const [filters, setFilters] = useState<FilterState>({
    buscar: '',
    categoria: '',
    um: '',
    almacen: '',
  })
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [categorias, setCategorias] = useState<string[]>([])
  const [unidades, setUnidades] = useState<string[]>([])
  const [selected, setSelected] = useState<InventoryRow | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const [tab, setTab] = useState<'buscador' | 'granel'>('buscador')
  const [page, setPage] = useState(1)
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)

  useEffect(() => {
    listInventory().then((all) => {
      const wh = new Map<string, string>()
      const cats = new Set<string>()
      const ums = new Set<string>()
      all.forEach((row) => {
        wh.set(row.almacen_id, row.almacen)
        if (row.categoria) cats.add(row.categoria)
        if (row.um) ums.add(row.um)
      })
      setWarehouses([...wh].map(([id, name]) => ({ id, name })))
      setCategorias([...cats])
      setUnidades([...ums])
    })
  }, [])

  useEffect(() => {
    listInventory({
      buscar: (globalSearch || filters.buscar) || undefined,
      categoria: filters.categoria || undefined,
      um: filters.um || undefined,
      almacen: filters.almacen || undefined,
    }).then(setRows)
  }, [filters, globalSearch, refreshToken])

  const handleFiltersChange = (next: FilterState) => {
    setFilters(next)
    setPage(1)
  }

  const paginatedRows = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return rows.slice(start, start + PAGE_SIZE)
  }, [rows, page])

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))

  const refresh = () => setRefreshToken((token) => token + 1)

  const handleSubmitMaterial = async (payload: MaterialPayload) => {
    try {
      if (formMode === 'create') {
        await createMaterial(payload)
        pushToast('Material creado')
      } else if (selected) {
        await updateMaterial(selected.codigo, payload)
        pushToast('Material modificado')
      }
      setFormMode(null)
      refresh()
    } catch (error) {
      pushError(errorMessage(error))
    }
  }

  const handleDelete = async () => {
    if (!selected) return
    try {
      await deleteMaterial(selected.codigo)
      pushToast('Material eliminado')
      setDeleteOpen(false)
      setSelected(null)
      refresh()
    } catch (error) {
      pushError(errorMessage(error))
    }
  }

  const handleTransfer = async (destination: string, quantity: number) => {
    if (!selected) return
    try {
      await createTransfer({
        source: selected.almacen_id,
        destination,
        sku: selected.codigo,
        quantity,
      })
      pushToast('Transferencia creada')
      setTransferOpen(false)
      refresh()
    } catch (error) {
      pushError(errorMessage(error))
    }
  }

  return (
    <div className="space-y-4">
      <KpiCards refreshToken={refreshToken} />

      <FilterToolbar
        filters={filters}
        onChange={handleFiltersChange}
        categorias={categorias}
        unidades={unidades}
        almacenes={warehouses}
        onAgregar={() => setFormMode('create')}
        onModificar={() => selected && setFormMode('edit')}
        onEliminar={() => selected && setDeleteOpen(true)}
        onTransferir={() => selected && setTransferOpen(true)}
      />

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex border-b border-slate-200">
          <button
            type="button"
            onClick={() => setTab('buscador')}
            className={`px-4 py-3 text-sm font-medium ${
              tab === 'buscador'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            1 Buscador
          </button>
          <button
            type="button"
            onClick={() => setTab('granel')}
            className={`px-4 py-3 text-sm font-medium ${
              tab === 'granel'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            2 Buscador a granel
          </button>
        </div>

        <div className="p-4">
          {tab === 'buscador' ? (
            <>
              <InventoryTable
                rows={paginatedRows}
                selectedCodigo={selected?.codigo ?? null}
                onSelect={setSelected}
              />
              <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
                <span>
                  Mostrando {paginatedRows.length} de {rows.length} registros
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
                  >
                    Anterior
                  </button>
                  <span>
                    Página {page} de {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
                  >
                    Siguiente
                  </button>
                </div>
              </div>
            </>
          ) : (
            <BulkSearch />
          )}
        </div>
      </div>

      <MaterialDetailDrawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        descripcion={selected?.descripcion ?? null}
        stockActual={selected?.stock_actual ?? 0}
        stockMinimo={selected?.stock_minimo ?? null}
        alertaStock={selected?.alerta_stock ?? false}
        um={selected?.um ?? null}
        codigo={selected?.codigo ?? ''}
        onModificar={() => selected && setFormMode('edit')}
        onEliminar={() => selected && setDeleteOpen(true)}
        onTransferir={() => selected && setTransferOpen(true)}
      />

      <Modal
        open={formMode !== null}
        title={formMode === 'create' ? 'Agregar Material' : 'Modificar Material'}
        onClose={() => setFormMode(null)}
      >
        <MaterialForm
          mode={formMode ?? 'create'}
          initial={
            formMode === 'edit' && selected
              ? {
                  codigo: selected.codigo,
                  descripcion: selected.descripcion,
                  um: selected.um,
                  stock_minimo: selected.stock_minimo,
                  categoria: selected.categoria,
                  tipo: selected.tipo,
                }
              : undefined
          }
          stockActual={selected?.stock_actual ?? 0}
          alertaStock={selected?.alerta_stock ?? false}
          onSubmit={handleSubmitMaterial}
          onCancel={() => setFormMode(null)}
        />
      </Modal>

      <ConfirmDialog
        open={deleteOpen}
        title="Eliminar Material"
        message={`¿Seguro que deseas eliminar el material ${selected?.codigo ?? ''}?`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />

      {selected && (
        <TransferDialog
          open={transferOpen}
          material={selected}
          warehouses={warehouses}
          onSubmit={handleTransfer}
          onCancel={() => setTransferOpen(false)}
        />
      )}
    </div>
  )
}
