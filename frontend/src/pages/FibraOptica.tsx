import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Eye, Pencil, Trash2 } from 'lucide-react'
import MaterialDetailDrawer from '../components/MaterialDetailDrawer'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import FibraMaterialForm from '../components/FibraMaterialForm'
import {
  eliminarFibraMaterial,
  listFibraStock,
  updateFibraMaterial,
} from '../services/fibra'
import { listCatalog, listCategorias } from '../services/catalog'
import { useUms } from '../hooks/useUms'
import { useToast } from '../hooks/useToasts'
import { stockLevel } from '../utils/stockLevel'
import type { StockLevel } from '../utils/stockLevel'
import type { FibraMaterialUpdatePayload, FibraModulo, FibraStockRow } from '../types'

interface FibraOpticaProps {
  sub: string
}

const MODULO_POR_SUB: Record<string, FibraModulo> = {
  paquete: 'PAQUETE',
  'en-uso': 'EN_USO',
}

const LEVEL_CLASS: Record<StockLevel, string> = {
  normal: 'bg-green-100 text-green-700',
  low: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

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

export default function FibraOptica({ sub }: FibraOpticaProps) {
  const esEnUso = sub === 'en-uso'
  const modulo = MODULO_POR_SUB[sub] ?? 'PAQUETE'
  const { pushToast, pushError } = useToast()
  const queryClient = useQueryClient()

  // CRUD FO (REQ-CRUD-001): selección de fila + drawer + modal de edición +
  // diálogo de eliminación, espejo del patrón de SeccionGeneral.
  const [selected, setSelected] = useState<FibraStockRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteMotivo, setDeleteMotivo] = useState('')
  const [deleteMotivoError, setDeleteMotivoError] = useState<string | null>(null)

  // ============================================================================
  // QUERIES
  // ============================================================================

  // Inventario FO independiente (REQ-DOMAIN-003/004): raíz autónoma con
  // esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK
  // MÍNIMO, ALERTA STOCK). La métrica de cada fila la gobierna `u_m`
  // (REQ-DOMAIN-005); el legado "carretes/metros" está deprecado.
  const stockQuery = useQuery({
    queryKey: ['fibra', modulo],
    queryFn: () => listFibraStock(modulo),
  })

  const { data: categorias = [] } = useQuery({
    queryKey: ['categorias'],
    queryFn: listCategorias,
  })

  // Unidades de medida del catálogo: alimentan el select U.M. del
  // FibraMaterialForm (fallback a UNIDADES si el catálogo llega vacío).
  const { data: ums = [] } = useUms()

  // Join de PRESENTACIÓN material_id → categoría desde el contrato oficial
  // /catalogo (patrón SeccionGeneral): alimenta el initial del formulario.
  const { data: catalogoData } = useQuery({
    queryKey: ['catalogo'],
    queryFn: () => listCatalog(),
    select: (data) => data.materiales,
  })

  const categoriaPorMaterial = useMemo(() => {
    const mapa: Record<number, string> = {}
    for (const m of catalogoData ?? []) {
      if (m.categoria) {
        mapa[m.id_lista] = m.categoria
      }
    }
    return mapa
  }, [catalogoData])

  // Precarga del id de categoría al editar (evita que la categoría
  // desaparezca al abrir el modal — espejo de SeccionGeneral).
  const categoriaIdPorMaterial = useMemo(() => {
    const mapa: Record<number, number> = {}
    for (const m of catalogoData ?? []) {
      if (m.categoria_id != null) {
        mapa[m.id_lista] = m.categoria_id
      }
    }
    return mapa
  }, [catalogoData])

  // ============================================================================
  // MUTATIONS
  // ============================================================================

  const updateMut = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number
      payload: FibraMaterialUpdatePayload
    }) => updateFibraMaterial(modulo, id, payload),
    onSuccess: () => {
      // REQ-TRF-INV-002: invalidar la clave del módulo tras cada mutación
      // CRUD FO para evitar stock obsoleto en la UI. La edición de catálogo
      // también invalida ['catalogo'] y ['categorias'] (join de presentación).
      queryClient.invalidateQueries({ queryKey: ['fibra', modulo] })
      queryClient.invalidateQueries({ queryKey: ['catalogo'] })
      queryClient.invalidateQueries({ queryKey: ['categorias'] })
      pushToast('Material modificado')
      setEditOpen(false)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const deleteMut = useMutation({
    mutationFn: ({ id, motivo }: { id: number; motivo?: string }) =>
      eliminarFibraMaterial(modulo, id, motivo),
    onSuccess: () => {
      // REQ-TRF-INV-002 + traza forense: el evento ELIMINACION_FO se ve en
      // la página Auditoría, por eso se invalida ['auditoria'] además del
      // stock del módulo.
      queryClient.invalidateQueries({ queryKey: ['fibra', modulo] })
      queryClient.invalidateQueries({ queryKey: ['auditoria'] })
      pushToast('Material eliminado del inventario FO')
      setDeleteOpen(false)
      setDrawerOpen(false)
      setSelected(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  // ============================================================================
  // HANDLERS
  // ============================================================================

  const handleSelect = (row: FibraStockRow) => {
    setSelected(row)
    setDrawerOpen(true)
  }

  const handleOpenDelete = () => {
    setDeleteMotivo('')
    setDeleteMotivoError(null)
    setDeleteOpen(true)
  }

  const handleConfirmDelete = () => {
    if (!selected) return
    // REQ-DEL-004: con stock > 0 el motivo es obligatorio (validación
    // cliente espejo del 422 del backend); con stock 0 es opcional.
    if (selected.stock_actual > 0) {
      const motivoLimpio = deleteMotivo.trim()
      if (!motivoLimpio) {
        setDeleteMotivoError(
          'El motivo de la eliminación es obligatorio cuando el material tiene stock: la eliminación queda registrada en Auditoría.',
        )
        return
      }
      deleteMut.mutate({ id: selected.material_id, motivo: motivoLimpio })
      return
    }
    deleteMut.mutate({ id: selected.material_id })
  }

  const rows = stockQuery.data ?? []
  const motivoRequerido = selected !== null && selected.stock_actual > 0

  // ============================================================================
  // RENDER
  // ============================================================================

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-800">
          Fibra Óptica — {esEnUso ? 'En Uso' : 'Paquete'}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {esEnUso
            ? 'Inventario independiente EN USO. La unidad de medida (U.M.) de cada fila define su métrica.'
            : 'Inventario independiente PAQUETE. La unidad de medida (U.M.) de cada fila define su métrica.'}
        </p>
      </div>

      {/* Barra de acciones del CRUD FO (REQ-CRUD-001): visible SOLO con
          selección — Ver Detalle abre el drawer, Modificar el modal de
          edición y Eliminar el diálogo de confirmación. */}
      {selected && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <p className="mr-2 text-sm text-slate-600">
            Seleccionado:{' '}
            <span className="font-mono">{selected.codigo ?? '—'}</span>
            {' — '}
            <span className="font-medium text-slate-700">
              {selected.descripcion}
            </span>
          </p>
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="flex items-center gap-1 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              <Eye className="h-4 w-4" /> Ver Detalle
            </button>
            <button
              type="button"
              onClick={() => setEditOpen(true)}
              className="flex items-center gap-1 rounded-md bg-yellow-500 px-3 py-2 text-sm font-medium text-white hover:bg-yellow-600"
            >
              <Pencil className="h-4 w-4" /> Modificar
            </button>
            <button
              type="button"
              onClick={handleOpenDelete}
              className="flex items-center gap-1 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              <Trash2 className="h-4 w-4" /> Eliminar
            </button>
          </div>
        </div>
      )}

      {stockQuery.isLoading && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
          <p className="text-slate-500">Cargando inventario de fibra…</p>
        </div>
      )}

      {stockQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-red-700">
            No se pudo obtener el inventario de fibra ({modulo}).
          </p>
        </div>
      )}

      {!stockQuery.isLoading && !stockQuery.isError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Nº</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Descripción</th>
                <th className="px-4 py-3">U.M.</th>
                <th className="px-4 py-3">Stock Actual</th>
                <th className="px-4 py-3">Stock Mínimo</th>
                <th className="px-4 py-3">Alerta Stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, index) => {
                const level = stockLevel(row)
                const esSeleccionado = selected?.material_id === row.material_id
                return (
                  <tr
                    key={row.material_id}
                    onClick={() => handleSelect(row)}
                    className={`cursor-pointer transition-colors hover:bg-blue-50 ${
                      esSeleccionado ? 'bg-blue-50' : ''
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-sm font-semibold text-slate-600">
                      {index + 1}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700">
                      {row.codigo ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.descripcion}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {row.u_m ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${LEVEL_CLASS[level]}`}
                      >
                        {row.stock_actual.toLocaleString('es-MX')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {row.stock_minimo != null ? row.stock_minimo : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {row.alerta_stock ? (
                        <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                          Alerta Stock
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {rows.length === 0 && (
            <p className="p-6 text-center text-sm text-slate-500">
              Sin materiales en el inventario {modulo}.
            </p>
          )}
        </div>
      )}

      {/* Drawer de detalle (REQ-CRUD-002): lectura pura del módulo FO —
          cerrar deselecciona la fila. */}
      <MaterialDetailDrawer
        open={drawerOpen && selected !== null}
        onClose={() => {
          setDrawerOpen(false)
          setSelected(null)
        }}
        descripcion={selected?.descripcion ?? null}
        stockActual={selected?.stock_actual ?? 0}
        stockMinimo={selected?.stock_minimo ?? null}
        alertaStock={selected?.alerta_stock ?? false}
        um={selected?.u_m ?? null}
        codigo={selected?.codigo ?? ''}
        onModificar={() => selected && setEditOpen(true)}
        onEliminar={() => selected && handleOpenDelete()}
      />

      {/* Modal de edición (REQ-CATFO-001, REQ-STOCK-001): FibraMaterialForm
          con catálogo dinámico y STOCK ACTUAL con motivo obligatorio. */}
      <Modal
        open={editOpen && selected !== null}
        title="Modificar Material"
        onClose={() => setEditOpen(false)}
      >
        {selected && (
          <FibraMaterialForm
            initial={{
              material_id: selected.material_id,
              codigo: selected.codigo,
              descripcion: selected.descripcion,
              u_m: selected.u_m,
              stock_minimo: selected.stock_minimo,
              categoria_id:
                categoriaIdPorMaterial[selected.material_id] ?? null,
              categoria: categoriaPorMaterial[selected.material_id] ?? null,
            }}
            stockActual={selected.stock_actual}
            alertaStock={selected.alerta_stock}
            categorias={categorias}
            ums={ums}
            onSubmit={(payload) =>
              updateMut.mutate({ id: selected.material_id, payload })
            }
            onCancel={() => setEditOpen(false)}
          />
        )}
      </Modal>

      {/* Eliminación (REQ-DEL-001/004): con stock > 0 el motivo es
          obligatorio (Modal + textarea con validación cliente); con stock 0
          basta el ConfirmDialog simple (patrón SeccionGeneral). */}
      {deleteOpen && selected && motivoRequerido ? (
        <Modal
          open={deleteOpen}
          title="Eliminar Material"
          onClose={() => setDeleteOpen(false)}
        >
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              El material{' '}
              <span className="font-mono">{selected.codigo ?? '—'}</span>{' '}
              ({selected.descripcion}) tiene{' '}
              <span className="font-semibold">
                {selected.stock_actual.toLocaleString('es-MX')}
              </span>{' '}
              {selected.u_m ?? ''} de stock en el inventario {modulo}. La
              eliminación física de la fila queda registrada en Auditoría
              (ELIMINACION_FO) con el stock eliminado y el motivo.
            </p>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Motivo de la eliminación *
              </label>
              <textarea
                value={deleteMotivo}
                onChange={(event) => {
                  setDeleteMotivo(event.target.value)
                  if (deleteMotivoError) setDeleteMotivoError(null)
                }}
                maxLength={500}
                rows={3}
                placeholder="Ej. Material fuera de uso, corrección de inventario, baja administrativa"
                className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
                  deleteMotivoError ? 'border-red-400' : 'border-slate-300'
                }`}
              />
              <div className="mt-1 flex items-center justify-between">
                <p
                  className={`text-xs ${
                    deleteMotivoError
                      ? 'font-medium text-red-600'
                      : 'text-slate-500'
                  }`}
                >
                  {deleteMotivoError ??
                    'Obligatorio cuando el material tiene stock (máx. 500 caracteres).'}
                </p>
                <span className="text-xs text-slate-400">
                  {deleteMotivo.length}/500
                </span>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteOpen(false)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Eliminar
              </button>
            </div>
          </div>
        </Modal>
      ) : (
        <ConfirmDialog
          open={deleteOpen}
          title="Eliminar Material"
          message={`¿Seguro que deseas eliminar el material ${selected?.codigo ?? ''} del inventario ${modulo}?`}
          onConfirm={handleConfirmDelete}
          onCancel={() => setDeleteOpen(false)}
        />
      )}

      <p className="text-xs text-slate-400">
        El inventario <span className="font-mono">{modulo}</span> se consume
        vía <span className="font-mono">/fibra/&lt;modulo&gt;</span> y ahora se
        gestiona directamente desde esta sección (Ver Detalle, Modificar,
        Eliminar). Las transferencias TEAMS/DEVOL siguen operando en la página
        Transferencias: el CRUD FO no altera el ruteo ni el inventario que
        consumen.
      </p>
    </div>
  )
}
