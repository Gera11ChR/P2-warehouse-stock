import { useState } from 'react'
import type { FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import {
  useEliminarReferencia,
  useModificarReferencia,
  useReferencia,
} from '../hooks/useReferencia'
import { queryKeys } from '../hooks/queryKeys'
import { mensajeErrorApi } from '../utils/errorMensaje'
import { extraerRespuestaError } from '../utils/operadorErrores'
import {
  formatearCantidad,
  mensajeCantidadInvalida,
  validarCantidad,
} from '../utils/cantidad'
import ConfirmDialog from './ConfirmDialog'
import ReferenciaAgregarForm from './ReferenciaAgregarForm'
import type { ReferenciaLinea } from '../types'

// ============================================================================
// PANEL «MATERIALES REFERENCIA» (REQ-REF-002/003/004/005/013/014/016, T9)
//
// Tabla Descripción / U.M. / Cantidad Semanal de la Referencia de la Unidad.
//  - Consulta: SOLO LECTURA (sin «+ Agregar», «Modificar» ni «Eliminar»).
//  - Configuración: «+ Agregar» (formulario con origen por línea), y por fila
//    «Modificar» (solo la Cantidad Semanal, edición en la propia fila) y
//    «Eliminar» (con confirmación explícita).
// La Referencia es VISUAL: no afecta inventarios ni catálogo. Estados de
// carga, error (con reintento) y vacío explícitos. FAIL-CLOSED: un error de
// lectura jamás se presenta como Referencia vacía.
//
// El padre monta el panel con `key` por (Unidad, subsección): al cambiar de
// Unidad o de subsección se descartan formulario, edición y confirmaciones
// pendientes, de modo que nada se envía a una Unidad distinta de la de origen
// (REQ-REF-004).
// ============================================================================

interface ReferenciaPanelProps {
  id?: string
  equipoId: number
  equipoNombre?: string
  modo: 'consulta' | 'configuracion'
}

/** `cuerpo.error.code` de un error HTTP (o undefined). */
function codigoDeError(error: unknown): string | undefined {
  const { cuerpo } = extraerRespuestaError(error)
  if (typeof cuerpo === 'object' && cuerpo !== null && 'error' in cuerpo) {
    const interno = (cuerpo as { error?: unknown }).error
    if (typeof interno === 'object' && interno !== null && 'code' in interno) {
      const code = (interno as { code?: unknown }).code
      return typeof code === 'string' ? code : undefined
    }
  }
  return undefined
}

export default function ReferenciaPanel({
  id,
  equipoId,
  equipoNombre,
  modo,
}: ReferenciaPanelProps) {
  const queryClient = useQueryClient()
  const referencia = useReferencia(equipoId)
  const modificar = useModificarReferencia(equipoId)
  const eliminar = useEliminarReferencia(equipoId)

  const [agregarAbierto, setAgregarAbierto] = useState(false)
  const [editando, setEditando] = useState<{
    materialId: number
    valor: string
    error: string | null
  } | null>(null)
  const [porEliminar, setPorEliminar] = useState<ReferenciaLinea | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const esConfiguracion = modo === 'configuracion'
  const lineas = referencia.data
  const existentes = new Set((lineas ?? []).map((linea) => linea.material_id))

  const refrescarPorLineaInexistente = () => {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.referencia(equipoId),
    })
    setAviso('La línea ya no existe en la Referencia; se actualizó la tabla.')
  }

  const guardarEdicion = (event: FormEvent) => {
    event.preventDefault()
    if (editando === null) return
    const cantidad = validarCantidad(editando.valor)
    if (!cantidad.ok) {
      setEditando({
        ...editando,
        error: mensajeCantidadInvalida(cantidad.motivo),
      })
      return
    }
    setAviso(null)
    modificar.mutate(
      {
        materialId: editando.materialId,
        payload: { cantidad_semanal: cantidad.cantidad },
      },
      {
        onSuccess: () => setEditando(null),
        onError: (error) => {
          if (codigoDeError(error) === 'REFERENCIA_NO_ENCONTRADA') {
            setEditando(null)
            refrescarPorLineaInexistente()
          }
        },
      },
    )
  }

  const confirmarEliminacion = () => {
    if (porEliminar === null) return
    const materialId = porEliminar.material_id
    setAviso(null)
    eliminar.mutate(materialId, {
      onSuccess: () => setPorEliminar(null),
      onError: (error) => {
        setPorEliminar(null)
        if (codigoDeError(error) === 'REFERENCIA_NO_ENCONTRADA') {
          refrescarPorLineaInexistente()
        }
      },
    })
  }

  const titulo = 'Materiales Referencia'
  const tituloId = `${id ?? 'referencia'}-titulo`

  return (
    <section
      id={id}
      aria-labelledby={tituloId}
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={tituloId} className="text-lg font-semibold text-slate-800">
          {titulo}
        </h3>
        {esConfiguracion && (
          <button
            type="button"
            onClick={() => setAgregarAbierto((abierto) => !abierto)}
            aria-expanded={agregarAbierto}
            className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            <Plus className="h-4 w-4" aria-hidden="true" /> Agregar
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        La Referencia es solo visual: la cantidad no afecta el inventario.
      </p>

      {aviso && (
        <p role="status" className="mt-2 text-sm font-medium text-amber-700">
          {aviso}
        </p>
      )}

      {referencia.isLoading && (
        <p role="status" className="mt-3 text-sm text-slate-500">
          Cargando la Referencia…
        </p>
      )}

      {referencia.isError && (
        <div
          role="alert"
          className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          <p>No se pudo cargar la Referencia de la Unidad.</p>
          <p className="mt-1 text-xs text-red-600">
            {mensajeErrorApi(referencia.error)}
          </p>
          <button
            type="button"
            onClick={() => void referencia.refetch()}
            className="mt-2 rounded-md border border-red-300 bg-white px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50"
          >
            Reintentar
          </button>
        </div>
      )}

      {lineas !== undefined && lineas.length === 0 && (
        <p
          role="status"
          className="mt-3 rounded-md border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500"
        >
          La Referencia de esta Unidad está vacía.
          {esConfiguracion
            ? ' Usa «Agregar» para elegir los materiales que maneja.'
            : ''}
        </p>
      )}

      {/* `relative` en el contenedor con scroll: contiene al contenido `sr-only`
          (position:absolute); sin él, el texto oculto de la cabecera
          «Acciones» escapa del recorte y ensancha la página en móvil. */}
      {lineas !== undefined && lineas.length > 0 && (
        <div className="relative mt-3 overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">
              {titulo}
              {equipoNombre ? ` de la Unidad ${equipoNombre}` : ''}
            </caption>
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">
                  Descripción
                </th>
                <th scope="col" className="px-4 py-3">
                  U.M.
                </th>
                <th scope="col" className="px-4 py-3">
                  Cantidad Semanal
                </th>
                {esConfiguracion && (
                  <th scope="col" className="px-4 py-3">
                    <span className="sr-only">Acciones</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lineas.map((linea) => {
                const enEdicion = editando?.materialId === linea.material_id
                return (
                  <tr key={linea.material_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700">
                      {linea.descripcion}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {linea.u_m ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {enEdicion && editando ? (
                        <form
                          onSubmit={guardarEdicion}
                          aria-label={`Modificar ${linea.descripcion}`}
                          className="flex flex-wrap items-start gap-2"
                          onKeyDown={(event) => {
                            if (event.key === 'Escape') setEditando(null)
                          }}
                        >
                          <div>
                            <input
                              type="text"
                              inputMode="decimal"
                              autoComplete="off"
                              spellCheck={false}
                              autoFocus
                              aria-label={`Cantidad Semanal de ${linea.descripcion}`}
                              aria-invalid={editando.error !== null}
                              aria-describedby={
                                editando.error ? 'referencia-edicion-error' : undefined
                              }
                              value={editando.valor}
                              onChange={(event) =>
                                setEditando({
                                  ...editando,
                                  valor: event.target.value,
                                  error: null,
                                })
                              }
                              className={`w-28 rounded-md border px-2 py-1 text-sm ${
                                editando.error
                                  ? 'border-red-400'
                                  : 'border-slate-300'
                              }`}
                            />
                            {editando.error && (
                              <p
                                id="referencia-edicion-error"
                                className="mt-1 text-xs font-medium text-red-600"
                              >
                                {editando.error}
                              </p>
                            )}
                          </div>
                          <button
                            type="submit"
                            disabled={modificar.isPending}
                            className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                          >
                            {modificar.isPending && (
                              <Loader2
                                className="h-3 w-3 animate-spin"
                                aria-hidden="true"
                              />
                            )}
                            Guardar
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditando(null)}
                            className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-600 hover:bg-slate-50"
                          >
                            Cancelar
                          </button>
                        </form>
                      ) : (
                        formatearCantidad(linea.cantidad_semanal)
                      )}
                    </td>
                    {esConfiguracion && (
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setAviso(null)
                              setEditando({
                                materialId: linea.material_id,
                                valor: String(linea.cantidad_semanal),
                                error: null,
                              })
                            }}
                            aria-label={`Modificar ${linea.descripcion}`}
                            className="flex items-center gap-1 rounded-md bg-yellow-500 px-2 py-1 text-xs font-medium text-white hover:bg-yellow-600"
                          >
                            <Pencil className="h-3 w-3" aria-hidden="true" />{' '}
                            Modificar
                          </button>
                          <button
                            type="button"
                            onClick={() => setPorEliminar(linea)}
                            aria-label={`Eliminar ${linea.descripcion}`}
                            className="flex items-center gap-1 rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
                          >
                            <Trash2 className="h-3 w-3" aria-hidden="true" />{' '}
                            Eliminar
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {esConfiguracion && agregarAbierto && (
        <ReferenciaAgregarForm
          equipoId={equipoId}
          existentes={existentes}
          onCerrar={() => setAgregarAbierto(false)}
        />
      )}

      <ConfirmDialog
        open={porEliminar !== null}
        title="Eliminar de la Referencia"
        message={`¿Seguro que deseas quitar "${porEliminar?.descripcion ?? ''}" de la Referencia de la Unidad? El material y los inventarios no se modifican.`}
        onConfirm={confirmarEliminacion}
        onCancel={() => setPorEliminar(null)}
      />
    </section>
  )
}
