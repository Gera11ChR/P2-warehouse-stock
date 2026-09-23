import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import {
  listEquipos,
  createEquipo,
  updateEquipo,
  deleteEquipo,
} from '../services/equipos'
import type {
  EquipoCreatePayload,
  EquipoUpdatePayload,
} from '../services/equipos'
import { catalogoEquipo } from '../services/inventory'
import EquipoInventoryTable from '../components/EquipoInventoryTable'
import EquipoForm from '../components/EquipoForm'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../hooks/useToasts'
import type { Equipo } from '../types'

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

export default function InventarioPorEquipos() {
  const { pushToast, pushError } = useToast()
  const queryClient = useQueryClient()

  const [selectedEquipoId, setSelectedEquipoId] = useState<number | null>(null)
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [equipoToEdit, setEquipoToEdit] = useState<Equipo | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [equipoToDelete, setEquipoToDelete] = useState<Equipo | null>(null)

  // ============================================================================
  // QUERIES
  // ============================================================================

  const {
    data: equipos = [],
    isLoading: equiposLoading,
    isError: equiposError,
  } = useQuery({
    queryKey: ['equipos'],
    queryFn: listEquipos,
  })

  // Compute effective equipo_id: use selected or default to first active
  const effectiveEquipoId = useMemo(() => {
    if (selectedEquipoId !== null) {
      return selectedEquipoId
    }
    const first = equipos.find((e) => e.is_active)
    return first?.equipo_id ?? null
  }, [selectedEquipoId, equipos])

  const {
    data: inventarioRows = [],
    isLoading: inventarioLoading,
    isError: inventarioError,
    error: inventarioErrorObj,
  } = useQuery({
    queryKey: ['equipo', effectiveEquipoId],
    queryFn: () => catalogoEquipo(effectiveEquipoId!),
    enabled: effectiveEquipoId !== null,
  })

  // ============================================================================
  // MUTATIONS
  // ============================================================================

  const createMut = useMutation({
    mutationFn: createEquipo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipos'] })
      pushToast('Equipo creado')
      setFormMode(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const updateMut = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number
      payload: EquipoUpdatePayload
    }) => updateEquipo(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipos'] })
      queryClient.invalidateQueries({ queryKey: ['equipo', effectiveEquipoId] })
      pushToast('Equipo modificado')
      setFormMode(null)
      setEquipoToEdit(null)
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const deleteMut = useMutation({
    mutationFn: deleteEquipo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipos'] })
      pushToast('Equipo eliminado')
      setDeleteOpen(false)
      setEquipoToDelete(null)
      // Si eliminamos el equipo actualmente seleccionado, limpiar la selección
      if (equipoToDelete?.equipo_id === selectedEquipoId) {
        setSelectedEquipoId(null)
      }
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const handleSubmitEquipo = async (
    payload: EquipoCreatePayload | EquipoUpdatePayload,
  ) => {
    if (formMode === 'create') {
      createMut.mutate(payload as EquipoCreatePayload)
    } else if (equipoToEdit) {
      updateMut.mutate({ id: equipoToEdit.equipo_id, payload })
    }
  }

  const handleDelete = () => {
    if (equipoToDelete) {
      deleteMut.mutate(equipoToDelete.equipo_id)
    }
  }

  const handleEditEquipo = (equipo: Equipo) => {
    setEquipoToEdit(equipo)
    setFormMode('edit')
  }

  const handleDeleteEquipo = (equipo: Equipo) => {
    setEquipoToDelete(equipo)
    setDeleteOpen(true)
  }

  // ============================================================================
  // RENDER
  // ============================================================================

  return (
    <div className="space-y-4">
      {/* Header con acciones */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-slate-800">
          Inventario por Equipos
        </h2>
        <button
          type="button"
          onClick={() => setFormMode('create')}
          className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
        >
          <Plus className="h-4 w-4" /> Crear Equipo
        </button>
      </div>

      {/* Selector de equipo */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-700">
              Seleccionar Equipo
            </label>
            {equiposLoading && (
              <p className="mt-1 text-sm text-slate-500">Cargando equipos...</p>
            )}
            {equiposError && (
              <p className="mt-1 text-sm text-red-600">
                No se pudieron cargar los equipos
              </p>
            )}
            {!equiposLoading && !equiposError && (
              <select
                value={effectiveEquipoId ?? ''}
                onChange={(e) =>
                  setSelectedEquipoId(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm font-medium"
              >
                <option value="">— Seleccione un equipo —</option>
                {equipos
                  .filter((e) => e.is_active)
                  .map((e) => (
                    <option key={e.equipo_id} value={e.equipo_id}>
                      {e.nombre} ({e.integrantes.length}{' '}
                      {e.integrantes.length === 1 ? 'integrante' : 'integrantes'})
                    </option>
                  ))}
              </select>
            )}
          </div>
          {effectiveEquipoId !== null && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  const equipo = equipos.find(
                    (e) => e.equipo_id === effectiveEquipoId,
                  )
                  if (equipo) handleEditEquipo(equipo)
                }}
                className="flex items-center gap-1 rounded-md bg-yellow-500 px-3 py-2 text-sm font-medium text-white hover:bg-yellow-600"
              >
                <Pencil className="h-4 w-4" /> Modificar
              </button>
              <button
                type="button"
                onClick={() => {
                  const equipo = equipos.find(
                    (e) => e.equipo_id === effectiveEquipoId,
                  )
                  if (equipo) handleDeleteEquipo(equipo)
                }}
                className="flex items-center gap-1 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                <Trash2 className="h-4 w-4" /> Eliminar
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Tabla de inventario sparse */}
      <div>
        {effectiveEquipoId === null && (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
            <p className="text-slate-500">
              Seleccione un equipo para ver su inventario
            </p>
          </div>
        )}

        {effectiveEquipoId !== null && inventarioLoading && (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
            <p className="text-slate-500">Cargando inventario...</p>
          </div>
        )}

        {effectiveEquipoId !== null && inventarioError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-700">
              No se pudo obtener el inventario del equipo
            </p>
            <p className="mt-1 text-sm text-red-600">
              {errorMessage(inventarioErrorObj)}
            </p>
          </div>
        )}

        {effectiveEquipoId !== null &&
          !inventarioLoading &&
          !inventarioError && (
            <>
              <EquipoInventoryTable rows={inventarioRows} />
              <p className="mt-2 text-xs text-slate-500">
                Mostrando {inventarioRows.length} materiales (modelo sparse: stock 0
                donde no hay registro físico)
              </p>
            </>
          )}
      </div>

      {/* Modal CRUD */}
      <Modal
        open={formMode !== null}
        title={formMode === 'create' ? 'Crear Equipo' : 'Modificar Equipo'}
        onClose={() => {
          setFormMode(null)
          setEquipoToEdit(null)
        }}
      >
        <EquipoForm
          mode={formMode ?? 'create'}
          initial={equipoToEdit ?? undefined}
          onSubmit={handleSubmitEquipo}
          onCancel={() => {
            setFormMode(null)
            setEquipoToEdit(null)
          }}
        />
      </Modal>

      {/* Confirmación de eliminación */}
      <ConfirmDialog
        open={deleteOpen}
        title="Eliminar Equipo"
        message={`¿Seguro que deseas eliminar el equipo "${equipoToDelete?.nombre ?? ''}"? Esta acción marcará el equipo como inactivo.`}
        onConfirm={handleDelete}
        onCancel={() => {
          setDeleteOpen(false)
          setEquipoToDelete(null)
        }}
      />
    </div>
  )
}
