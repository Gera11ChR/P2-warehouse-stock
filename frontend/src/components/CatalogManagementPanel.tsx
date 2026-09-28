import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useCategorias } from '../hooks/useCategorias'
import { useUms } from '../hooks/useUms'
import { useCategoriaAdmin } from '../hooks/useCategoriaAdmin'
import { useUmAdmin } from '../hooks/useUmAdmin'
import { useToast } from '../hooks/useToasts'
import { createCategoria } from '../services/catalog'
import CategoriaForm from './CategoriaForm'
import Modal from './Modal'
import ConfirmDialog from './ConfirmDialog'

// ============================================================================
// PANEL — GESTIÓN DE CATÁLOGO: CATEGORÍAS Y UNIDADES DE MEDIDA (FASE 7)
//
// Administración de categorías y U.M. (crear / renombrar / soft-delete).
// El RBAC es del backend (403 admin-only) y los errores (409 duplicado,
// etc.) se muestran tal como los devuelve el servidor. Las mutaciones
// invalida el estado persistido; la UI nunca es fuente de verdad.
//
// Nota: `useCategoriaAdmin` NO expone creación — se usa el servicio
// `createCategoria` con una mutación local (mismas invalidaciones).
// ============================================================================

type Entidad = 'categoria' | 'um'

interface ModalState {
  entidad: Entidad
  modo: 'crear' | 'editar'
  id: number
  nombre: string
}

interface DeleteState {
  entidad: Entidad
  id: number
  nombre: string
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

function CatalogoBloque({
  titulo,
  entidad,
  rows,
  isLoading,
  isError,
  mensajeVacio,
  onNueva,
  onModificar,
  onEliminar,
}: {
  titulo: string
  entidad: Entidad
  rows: { id: number; nombre: string }[]
  isLoading: boolean
  isError: boolean
  mensajeVacio: string
  onNueva: () => void
  onModificar: (row: { id: number; nombre: string }) => void
  onEliminar: (row: { id: number; nombre: string }) => void
}) {
  const tipoLabel = entidad === 'categoria' ? 'categoría' : 'U.M.'
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-800">{titulo}</h3>
        <button
          type="button"
          onClick={onNueva}
          className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
        >
          <Plus className="h-4 w-4" /> Nueva
        </button>
      </div>
      <div className="mt-3">
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {isError && (
          <p className="text-sm text-red-600">
            No se pudieron cargar los registros.
          </p>
        )}
        {!isLoading && !isError && rows.length === 0 && (
          <p className="text-sm text-slate-500">{mensajeVacio}</p>
        )}
        {!isLoading && !isError && rows.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex items-center justify-between gap-2 py-2"
              >
                <span className="text-sm text-slate-700">{row.nombre}</span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onModificar(row)}
                    aria-label={`Modificar ${tipoLabel} ${row.nombre}`}
                    className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Modificar
                  </button>
                  <button
                    type="button"
                    onClick={() => onEliminar(row)}
                    aria-label={`Eliminar ${tipoLabel} ${row.nombre}`}
                    className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Eliminar
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default function CatalogManagementPanel() {
  const { pushToast, pushError } = useToast()
  const queryClient = useQueryClient()

  const categoriasQuery = useCategorias()
  const umsQuery = useUms()
  const categoriaAdmin = useCategoriaAdmin()
  const umAdmin = useUmAdmin()

  const [modal, setModal] = useState<ModalState | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DeleteState | null>(null)

  // Creación de categoría: `useCategoriaAdmin` no expone `crear` — mutación
  // local contra el servicio con las MISMAS invalidaciones del admin hook.
  const crearCategoriaMut = useMutation({
    mutationFn: createCategoria,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categorias'] })
      queryClient.invalidateQueries({ queryKey: ['catalogo'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
    },
  })

  const abrirNueva = (entidad: Entidad) => {
    setModal({ entidad, modo: 'crear', id: 0, nombre: '' })
  }

  const abrirEditar = (
    entidad: Entidad,
    row: { id: number; nombre: string },
  ) => {
    setModal({ entidad, modo: 'editar', id: row.id, nombre: row.nombre })
  }

  const handleSubmitNombre = (payload: { nombre: string }) => {
    if (!modal) return
    const cerrar = () => setModal(null)
    const onError = (err: unknown) => pushError(errorMessage(err))

    if (modal.modo === 'crear') {
      if (modal.entidad === 'categoria') {
        crearCategoriaMut.mutate(payload, {
          onSuccess: () => {
            pushToast('Categoría creada')
            cerrar()
          },
          onError,
        })
      } else {
        umAdmin.crear.mutate(payload, {
          onSuccess: () => {
            pushToast('U.M. creada')
            cerrar()
          },
          onError,
        })
      }
      return
    }

    // modo editar → renombrar
    if (modal.entidad === 'categoria') {
      categoriaAdmin.renombrar.mutate(
        { id: modal.id, payload },
        {
          onSuccess: () => {
            pushToast('Categoría modificada')
            cerrar()
          },
          onError,
        },
      )
    } else {
      umAdmin.renombrar.mutate(
        { id: modal.id, payload },
        {
          onSuccess: () => {
            pushToast('U.M. modificada')
            cerrar()
          },
          onError,
        },
      )
    }
  }

  const handleConfirmDelete = () => {
    if (!deleteTarget) return
    const onSuccess = () => {
      pushToast(
        deleteTarget.entidad === 'categoria'
          ? 'Categoría eliminada'
          : 'U.M. eliminada',
      )
      setDeleteTarget(null)
    }
    const onError = (err: unknown) => pushError(errorMessage(err))

    if (deleteTarget.entidad === 'categoria') {
      categoriaAdmin.eliminar.mutate(deleteTarget.id, { onSuccess, onError })
    } else {
      umAdmin.eliminar.mutate(deleteTarget.id, { onSuccess, onError })
    }
  }

  const tituloForm =
    modal === null
      ? ''
      : modal.modo === 'crear'
        ? modal.entidad === 'categoria'
          ? 'Nueva categoría'
          : 'Nueva U.M.'
        : modal.entidad === 'categoria'
          ? 'Modificar categoría'
          : 'Modificar U.M.'

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <CatalogoBloque
        titulo="Categorías"
        entidad="categoria"
        rows={categoriasQuery.data ?? []}
        isLoading={categoriasQuery.isLoading}
        isError={categoriasQuery.isError}
        mensajeVacio="Sin categorías registradas"
        onNueva={() => abrirNueva('categoria')}
        onModificar={(row) => abrirEditar('categoria', row)}
        onEliminar={(row) =>
          setDeleteTarget({ entidad: 'categoria', id: row.id, nombre: row.nombre })
        }
      />

      <CatalogoBloque
        titulo="Unidades de Medida"
        entidad="um"
        rows={umsQuery.data ?? []}
        isLoading={umsQuery.isLoading}
        isError={umsQuery.isError}
        mensajeVacio="Sin unidades de medida registradas"
        onNueva={() => abrirNueva('um')}
        onModificar={(row) => abrirEditar('um', row)}
        onEliminar={(row) =>
          setDeleteTarget({ entidad: 'um', id: row.id, nombre: row.nombre })
        }
      />

      <Modal
        open={modal !== null}
        title={modal?.entidad === 'categoria' ? 'Categoría' : 'Unidad de Medida'}
        onClose={() => setModal(null)}
      >
        {modal && (
          <CategoriaForm
            titulo={tituloForm}
            labelNombre="Nombre"
            initial={{ id: modal.id, nombre: modal.nombre }}
            onSubmit={handleSubmitNombre}
            onCancel={() => setModal(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={deleteTarget !== null}
        title={
          deleteTarget?.entidad === 'categoria'
            ? 'Eliminar categoría'
            : 'Eliminar U.M.'
        }
        message="El registro se desactivará (soft-delete) y dejará de aparecer en los selectores."
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
