import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import CatalogManagementPanel from '../components/CatalogManagementPanel'
import { useUms } from '../hooks/useUms'
import {
  listCategorias,
  listCatalog,
  createMaterial,
  updateMaterial,
  deleteMaterial,
} from '../services/catalog'
import type {
  MaterialCreatePayload,
  MaterialUpdatePayload,
} from '../services/catalog'
import { listSecciones, stockSeccion } from '../services/inventory'
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
  const queryClient = useQueryClient()

  const [filters, setFilters] = useState<FilterState>({
    buscar: '',
    categoria: '',
    um: '',
    almacen: '',
  })
  const [selectedAlmacenId, setSelectedAlmacenId] = useState<number | null>(null)
  const [selected, setSelected] = useState<InventoryRow | null>(null)
  const [tab, setTab] = useState<'buscador' | 'granel'>('buscador')
  const [page, setPage] = useState(1)
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  // ============================================================================
  // QUERIES
  // ============================================================================

  const { data: categorias = [] } = useQuery({
    queryKey: ['categorias'],
    queryFn: listCategorias,
  })

  // Unidades de medida del catálogo (FASE 7): alimentan el select U.M. del
  // MaterialForm y la gestión de catálogo (CatalogManagementPanel).
  const { data: ums = [] } = useUms()

  // REQ-UI-005: join de PRESENTACIÓN material_id → categoría desde el
  // contrato oficial /catalogo. La fila de stock por sección no incluye
  // categoría; este mapa solo proyecta la columna y alimenta el filtro.
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

  // F.4 (REQ-API-004/005): precarga del id de categoría al editar material.
  // Evita el síntoma del Issue #10 ("la categoría desaparece al editar").
  const categoriaIdPorMaterial = useMemo(() => {
    const mapa: Record<number, number> = {}
    for (const m of catalogoData ?? []) {
      if (m.categoria_id != null) {
        mapa[m.id_lista] = m.categoria_id
      }
    }
    return mapa
  }, [catalogoData])

  const { data: secciones = [] } = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
  })

  // Compute effective almacen_id: use selected or default to first active
  const effectiveAlmacenId = useMemo(() => {
    if (selectedAlmacenId !== null) {
      return selectedAlmacenId
    }
    const first = secciones.find((s) => s.is_active)
    return first?.almacen_id ?? null
  }, [selectedAlmacenId, secciones])

  const activeSeccion = useMemo(() => {
    return secciones.find((s) => s.almacen_id === effectiveAlmacenId) ?? null
  }, [effectiveAlmacenId, secciones])

  const { data: stockRows = [] } = useQuery({
    queryKey: ['stock', effectiveAlmacenId],
    queryFn: () => stockSeccion(effectiveAlmacenId!),
    enabled: effectiveAlmacenId !== null,
  })

  // Merge stock rows with almacen context → InventoryRow
  const rows: InventoryRow[] = useMemo(() => {
    if (!activeSeccion) return []
    return stockRows.map((row) => ({
      ...row,
      almacen_id: activeSeccion.almacen_id,
      almacen: activeSeccion.nombre,
    }))
  }, [stockRows, activeSeccion])

  // ============================================================================
  // FILTERS
  // ============================================================================

  const filteredRows = useMemo(() => {
    let result = rows
    const searchTerm = globalSearch || filters.buscar
    if (searchTerm) {
      const lower = searchTerm.toLowerCase()
      result = result.filter(
        (row) =>
          row.descripcion?.toLowerCase().includes(lower) ||
          row.codigo?.toLowerCase().includes(lower),
      )
    }
    if (filters.um) {
      result = result.filter((row) => row.u_m === filters.um)
    }
    // REQ-UI-005: filtro por categoría (nombre) resuelto con el join de
    // presentación material_id → categoría del catálogo oficial.
    if (filters.categoria) {
      result = result.filter(
        (row) => categoriaPorMaterial[row.material_id] === filters.categoria,
      )
    }
    return result
  }, [rows, globalSearch, filters, categoriaPorMaterial])

  const handleFiltersChange = (next: FilterState) => {
    setFilters(next)
    setPage(1)
  }

  const paginatedRows = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return filteredRows.slice(start, start + PAGE_SIZE)
  }, [filteredRows, page])

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))

  // ============================================================================
  // MUTATIONS
  // ============================================================================

  const createMut = useMutation({
    mutationFn: createMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stock', effectiveAlmacenId] })
      queryClient.invalidateQueries({ queryKey: ['categorias'] })
      queryClient.invalidateQueries({ queryKey: ['catalogo'] })
      pushToast('Material creado')
      setFormMode(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: MaterialUpdatePayload }) =>
      updateMaterial(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stock', effectiveAlmacenId] })
      queryClient.invalidateQueries({ queryKey: ['categorias'] })
      queryClient.invalidateQueries({ queryKey: ['catalogo'] })
      pushToast('Material modificado')
      setFormMode(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      // REQ-UI-003 (F.2): el material eliminado debe desaparecer de TODAS
      // las vistas activas — stock de sección, catálogo (Buscador a granel,
      // Reportes y join de categoría), inventario autónomo de equipos e
      // inventarios FO. El backend ya lo omite en las respuestas; estas
      // invalidaciones fuerzan el refetch para reflejarlo sin ghost records.
      queryClient.invalidateQueries({ queryKey: ['stock', effectiveAlmacenId] })
      queryClient.invalidateQueries({ queryKey: ['catalogo'] })
      queryClient.invalidateQueries({ queryKey: ['categorias'] })
      queryClient.invalidateQueries({ queryKey: ['equipos'] })
      queryClient.invalidateQueries({ queryKey: ['equipo'] })
      queryClient.invalidateQueries({ queryKey: ['fibra'] })
      queryClient.invalidateQueries({ queryKey: ['auditoria'] })
      pushToast('Material eliminado')
      setDeleteOpen(false)
      setSelected(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const handleSubmitMaterial = async (
    payload: MaterialCreatePayload | MaterialUpdatePayload,
  ) => {
    if (formMode === 'create') {
      createMut.mutate(payload as MaterialCreatePayload)
    } else if (selected) {
      updateMut.mutate({ id: selected.material_id, payload })
    }
  }

  const handleDelete = async () => {
    if (!selected) return
    deleteMut.mutate(selected.material_id)
  }

  // ============================================================================
  // RENDER
  // ============================================================================

  // Extract unique U.M. from rows for filter
  const unidades = useMemo(() => {
    const set = new Set<string>()
    rows.forEach((row) => {
      if (row.u_m) set.add(row.u_m)
    })
    return Array.from(set)
  }, [rows])

  return (
    <div className="space-y-4">
      <KpiCards stock={rows} />

      <FilterToolbar
        filters={filters}
        onChange={handleFiltersChange}
        categorias={categorias.map((c) => c.nombre)}
        unidades={unidades}
        almacenes={secciones.map((s) => ({
          id: String(s.almacen_id),
          name: s.nombre,
        }))}
        selectedAlmacen={effectiveAlmacenId}
        onAlmacenChange={setSelectedAlmacenId}
        onAgregar={() => setFormMode('create')}
        onModificar={() => selected && setFormMode('edit')}
        onEliminar={() => selected && setDeleteOpen(true)}
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
                categoriaPorMaterial={categoriaPorMaterial}
              />
              <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
                <span>
                  Mostrando {paginatedRows.length} de {filteredRows.length} registros
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
        um={selected?.u_m ?? null}
        codigo={selected?.codigo ?? ''}
        onModificar={() => selected && setFormMode('edit')}
        onEliminar={() => selected && setDeleteOpen(true)}
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
                  id_lista: selected.material_id,
                  codigo: selected.codigo,
                  descripcion: selected.descripcion,
                  u_m: selected.u_m,
                  stock_minimo: selected.stock_minimo,
                  categoria_id: categoriaIdPorMaterial[selected.material_id] ?? null,
                  categoria: categoriaPorMaterial[selected.material_id] ?? null,
                  is_active: true,
                }
              : undefined
          }
          stockActual={selected?.stock_actual ?? 0}
          alertaStock={selected?.alerta_stock ?? false}
          categorias={categorias}
          secciones={secciones}
          ums={ums}
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

      {/* Gestión de catálogo (FASE 7) — categorías y unidades de medida */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-800">
          Gestión de catálogo — Categorías y Unidades de Medida
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Cree, renombre o desactive (soft-delete) categorías y unidades de
          medida. La autoridad de validación y RBAC es del backend.
        </p>
        <div className="mt-4">
          <CatalogManagementPanel />
        </div>
      </section>
    </div>
  )
}
