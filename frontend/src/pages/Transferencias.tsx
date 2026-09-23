import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { Check, Plus, Search, Trash2, Undo2, X } from 'lucide-react'
import Modal from '../components/Modal'
import { listEquipos } from '../services/equipos'
import { catalogoEquipo, listSecciones, stockSeccion } from '../services/inventory'
import {
  cancelarMovimiento,
  crearBorrador,
  eliminarBorrador,
  listMovimientos,
  procesarMovimiento,
} from '../services/movimientos'
import type { MovimientoBorradorCreatePayload } from '../services/movimientos'
import { useToast } from '../hooks/useToasts'
import type { CartLine, Movimiento, TipoMovimiento } from '../types'
import { ESTADOS_MOVIMIENTO } from '../types'

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

const BADGE_ESTADO: Record<string, string> = {
  BORRADOR: 'bg-slate-100 text-slate-700',
  CONFIRMADO: 'bg-green-100 text-green-700',
  CANCELADO: 'bg-red-100 text-red-700',
}

function CartRows({
  lines,
  field,
  onChange,
  onRemove,
}: {
  lines: CartLine[]
  field: 'cantidad_transferir' | 'cantidad_devolver'
  onChange: (materialId: number, cantidad: number) => void
  onRemove: (materialId: number) => void
}) {
  if (lines.length === 0) {
    return (
      <p className="p-4 text-center text-sm text-slate-500">
        Carrito vacío. Seleccione materiales y agregue cantidades.
      </p>
    )
  }
  return (
    <ul className="divide-y divide-slate-100">
      {lines.map((line) => {
        const cantidad = line[field] ?? 0
        const invalida = !Number.isFinite(cantidad) || cantidad <= 0
        const saldoEstimado = line.stock_disponible - cantidad
        return (
          <li key={line.material_id} className="p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">
                  {line.descripcion}
                </p>
                <p className="text-xs text-slate-500">
                  {line.codigo ?? '—'} · {line.u_m ?? '—'} · Disponible:{' '}
                  {line.stock_disponible.toLocaleString('es-MX')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={line[field] ?? ''}
                  onChange={(event) =>
                    onChange(line.material_id, Number(event.target.value))
                  }
                  className={`w-24 rounded-md border px-2 py-1 text-sm ${
                    invalida ? 'border-red-400' : 'border-slate-300'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => onRemove(line.material_id)}
                  className="rounded p-1 text-red-600 hover:bg-red-50"
                  title="Quitar línea"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            <p
              className={`mt-1 text-xs ${
                saldoEstimado < 0 ? 'font-semibold text-red-600' : 'text-slate-500'
              }`}
            >
              Saldo estimado después de la operación:{' '}
              {saldoEstimado.toLocaleString('es-MX')}
              {saldoEstimado < 0 && ' — supera el stock disponible (visual)'}
            </p>
          </li>
        )
      })}
    </ul>
  )
}

export default function Transferencias() {
  const { pushToast, pushError } = useToast()
  const queryClient = useQueryClient()

  const [tab, setTab] = useState<TipoMovimiento>('TEAMS')

  // TEAMS state: sección origen → equipo destino
  const [seccionOrigen, setSeccionOrigen] = useState<number | null>(null)
  const [equipoDestino, setEquipoDestino] = useState<number | null>(null)
  // DEVOL state: equipo origen → sección destino
  const [equipoOrigen, setEquipoOrigen] = useState<number | null>(null)
  const [seccionDestino, setSeccionDestino] = useState<number | null>(null)

  const [busqueda, setBusqueda] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [carrito, setCarrito] = useState<CartLine[]>([])

  // Cancelación (FASE 4)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [movimientoACancelar, setMovimientoACancelar] =
    useState<Movimiento | null>(null)
  const [motivoCancelacion, setMotivoCancelacion] = useState('')

  // ============================================================================
  // QUERIES
  // ============================================================================

  const { data: secciones = [], isError: seccionesError } = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
  })

  const { data: equipos = [], isError: equiposError } = useQuery({
    queryKey: ['equipos'],
    queryFn: listEquipos,
  })

  const stockOrigenQuery = useQuery({
    queryKey: ['stock', seccionOrigen],
    queryFn: () => stockSeccion(seccionOrigen!),
    enabled: tab === 'TEAMS' && seccionOrigen !== null,
  })

  const inventarioEquipoQuery = useQuery({
    queryKey: ['equipo', equipoOrigen],
    queryFn: () => catalogoEquipo(equipoOrigen!),
    enabled: tab === 'DEVOL' && equipoOrigen !== null,
  })

  const movimientosQuery = useQuery({
    queryKey: ['movimientos'],
    queryFn: () => listMovimientos(),
  })

  // ============================================================================
  // FILAS DISPONIBLES (según tab)
  // ============================================================================

  const filasDisponibles = useMemo<CartLine[]>(() => {
    const term = busqueda.trim().toLowerCase()
    if (tab === 'TEAMS') {
      const rows = stockOrigenQuery.data ?? []
      return rows
        .filter(
          (r) =>
            !term ||
            r.descripcion.toLowerCase().includes(term) ||
            (r.codigo ?? '').toLowerCase().includes(term),
        )
        .map((r) => ({
          material_id: r.material_id,
          codigo: r.codigo,
          descripcion: r.descripcion,
          u_m: r.u_m,
          stock_disponible: r.stock_actual,
        }))
    }
    const rows = inventarioEquipoQuery.data ?? []
    return rows
      .filter((r) => r.stock_actual > 0)
      .filter(
        (r) =>
          !term ||
          r.descripcion.toLowerCase().includes(term) ||
          (r.codigo ?? '').toLowerCase().includes(term),
      )
      .map((r) => ({
        material_id: r.id_lista,
        codigo: r.codigo,
        descripcion: r.descripcion,
        u_m: r.u_m,
        stock_disponible: r.stock_actual,
      }))
  }, [tab, busqueda, stockOrigenQuery.data, inventarioEquipoQuery.data])

  // ============================================================================
  // CARRITO
  // ============================================================================

  const field: 'cantidad_transferir' | 'cantidad_devolver' =
    tab === 'TEAMS' ? 'cantidad_transferir' : 'cantidad_devolver'

  const agregarAlCarrito = (fila: CartLine) => {
    setCarrito((prev) => {
      if (prev.some((l) => l.material_id === fila.material_id)) {
        return prev
      }
      return [...prev, { ...fila, [field]: 1 }]
    })
  }

  const actualizarCantidad = (materialId: number, cantidad: number) => {
    setCarrito((prev) =>
      prev.map((l) =>
        l.material_id === materialId ? { ...l, [field]: cantidad } : l,
      ),
    )
  }

  const quitarDelCarrito = (materialId: number) => {
    setCarrito((prev) => prev.filter((l) => l.material_id !== materialId))
  }

  const limpiarCarrito = () => setCarrito([])

  const carritoInvalido =
    carrito.length === 0 ||
    carrito.some((l) => {
      const c = l[field] ?? 0
      return !Number.isFinite(c) || c <= 0
    })

  const extremosValidos =
    tab === 'TEAMS'
      ? seccionOrigen !== null && equipoDestino !== null
      : equipoOrigen !== null && seccionDestino !== null

  const payload: MovimientoBorradorCreatePayload | null =
    extremosValidos && !carritoInvalido
      ? tab === 'TEAMS'
        ? {
            tipo_movimiento: 'TEAMS',
            origen_almacen_id: seccionOrigen,
            destino_equipo_id: equipoDestino,
            observaciones: observaciones.trim() || null,
            detalle: carrito.map((l) => ({
              material_id: l.material_id,
              cantidad: l[field] ?? 0,
            })),
          }
        : {
            tipo_movimiento: 'DEVOL',
            origen_equipo_id: equipoOrigen,
            destino_almacen_id: seccionDestino,
            observaciones: observaciones.trim() || null,
            detalle: carrito.map((l) => ({
              material_id: l.material_id,
              cantidad: l[field] ?? 0,
            })),
          }
      : null

  // ============================================================================
  // MUTACIONES
  // ============================================================================

  const invalidarInventarios = () => {
    queryClient.invalidateQueries({ queryKey: ['movimientos'] })
    queryClient.invalidateQueries({ queryKey: ['secciones'] })
    if (tab === 'TEAMS') {
      queryClient.invalidateQueries({ queryKey: ['stock', seccionOrigen] })
      queryClient.invalidateQueries({ queryKey: ['equipo', equipoDestino] })
    } else {
      queryClient.invalidateQueries({ queryKey: ['equipo', equipoOrigen] })
      queryClient.invalidateQueries({ queryKey: ['stock', seccionDestino] })
    }
  }

  const crearBorradorMut = useMutation({
    mutationFn: crearBorrador,
    onError: (error) => pushError(errorMessage(error)),
    onSuccess: (movimiento) => {
      procesarMut.mutate(movimiento.id)
    },
  })

  const procesarMut = useMutation({
    mutationFn: procesarMovimiento,
    onSuccess: () => {
      pushToast('Movimiento CONFIRMADO por el servidor')
      invalidarInventarios()
      limpiarCarrito()
    },
    onError: (error) => {
      pushError(`${errorMessage(error)} — el borrador se conserva en el historial`)
      queryClient.invalidateQueries({ queryKey: ['movimientos'] })
      limpiarCarrito()
    },
  })

  const eliminarBorradorMut = useMutation({
    mutationFn: eliminarBorrador,
    onSuccess: () => {
      pushToast('Borrador eliminado')
      queryClient.invalidateQueries({ queryKey: ['movimientos'] })
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const cancelarMut = useMutation({
    mutationFn: ({
      id,
      motivo,
    }: {
      id: number
      motivo: string | null
    }) => cancelarMovimiento(id, motivo),
    onSuccess: (_data, variables) => {
      pushToast('Movimiento CANCELADO y stock restaurado por el servidor')
      queryClient.invalidateQueries({ queryKey: ['movimientos'] })
      queryClient.invalidateQueries({ queryKey: ['auditoria'] })
      queryClient.invalidateQueries({ queryKey: ['secciones'] })
      const m = movimientos.find((mov) => mov.id === variables.id)
      if (m) {
        if (m.origen_almacen_id != null) {
          queryClient.invalidateQueries({
            queryKey: ['stock', m.origen_almacen_id],
          })
        }
        if (m.destino_almacen_id != null) {
          queryClient.invalidateQueries({
            queryKey: ['stock', m.destino_almacen_id],
          })
        }
        if (m.origen_equipo_id != null) {
          queryClient.invalidateQueries({
            queryKey: ['equipo', m.origen_equipo_id],
          })
        }
        if (m.destino_equipo_id != null) {
          queryClient.invalidateQueries({
            queryKey: ['equipo', m.destino_equipo_id],
          })
        }
      }
      setCancelOpen(false)
      setMovimientoACancelar(null)
      setMotivoCancelacion('')
    },
    onError: (error) => pushError(errorMessage(error)),
  })

  const confirmarCancelacion = () => {
    if (movimientoACancelar) {
      cancelarMut.mutate({
        id: movimientoACancelar.id,
        motivo: motivoCancelacion.trim() || null,
      })
    }
  }

  const confirmar = () => {
    if (payload) {
      crearBorradorMut.mutate(payload)
    }
  }

  // ============================================================================
  // HISTORIAL
  // ============================================================================

  const movimientos: Movimiento[] = movimientosQuery.data ?? []

  const nombreSeccion = (id: number | null): string =>
    secciones.find((s) => s.almacen_id === id)?.nombre ?? `Sección ${id}`
  const nombreEquipo = (id: number | null): string =>
    equipos.find((e) => e.equipo_id === id)?.nombre ?? `Equipo ${id}`

  const detalleMovimiento = (m: Movimiento): string => {
    if (m.tipo_movimiento === 'TEAMS') {
      return `${nombreSeccion(m.origen_almacen_id)} → ${nombreEquipo(
        m.destino_equipo_id,
      )}`
    }
    return `${nombreEquipo(m.origen_equipo_id)} → ${nombreSeccion(
      m.destino_almacen_id,
    )}`
  }

  // ============================================================================
  // RENDER
  // ============================================================================

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-slate-800">Transferencias</h2>

      {/* Tabs */}
      <div className="flex gap-2">
        {(['TEAMS', 'DEVOL'] as TipoMovimiento[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => {
              setTab(t)
              setCarrito([])
              setBusqueda('')
            }}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              tab === t
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Selectores de extremos */}
      <div className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2">
        {tab === 'TEAMS' ? (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Sección Origen
              </label>
              <select
                value={seccionOrigen ?? ''}
                onChange={(e) =>
                  setSeccionOrigen(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">— Seleccione sección —</option>
                {secciones
                  .filter((s) => s.is_active)
                  .map((s) => (
                    <option key={s.almacen_id} value={s.almacen_id}>
                      {s.nombre}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Equipo Destino
              </label>
              <select
                value={equipoDestino ?? ''}
                onChange={(e) =>
                  setEquipoDestino(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">— Seleccione equipo —</option>
                {equipos
                  .filter((e) => e.is_active)
                  .map((e) => (
                    <option key={e.equipo_id} value={e.equipo_id}>
                      {e.nombre}
                    </option>
                  ))}
              </select>
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Equipo Origen
              </label>
              <select
                value={equipoOrigen ?? ''}
                onChange={(e) =>
                  setEquipoOrigen(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">— Seleccione equipo —</option>
                {equipos
                  .filter((e) => e.is_active)
                  .map((e) => (
                    <option key={e.equipo_id} value={e.equipo_id}>
                      {e.nombre}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Sección Destino
              </label>
              <select
                value={seccionDestino ?? ''}
                onChange={(e) =>
                  setSeccionDestino(
                    e.target.value === '' ? null : Number(e.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">— Seleccione sección —</option>
                {secciones
                  .filter((s) => s.is_active)
                  .map((s) => (
                    <option key={s.almacen_id} value={s.almacen_id}>
                      {s.nombre}
                    </option>
                  ))}
              </select>
            </div>
          </>
        )}
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-slate-700">
            Observaciones
          </label>
          <input
            type="text"
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            maxLength={2000}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {(seccionesError || equiposError) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          No se pudieron cargar secciones/equipos. Revise la conexión con el
          backend.
        </div>
      )}

      {/* Buscador + materiales disponibles */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 p-3">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder={
              tab === 'TEAMS'
                ? 'Buscar en inventario de la sección…'
                : 'Buscar en inventario del equipo…'
            }
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        {tab === 'TEAMS' && stockOrigenQuery.isLoading && (
          <p className="p-4 text-sm text-slate-500">Cargando inventario…</p>
        )}
        {tab === 'TEAMS' && stockOrigenQuery.isError && (
          <p className="p-4 text-sm text-red-600">
            No se pudo obtener el inventario de la sección origen.
          </p>
        )}
        {tab === 'DEVOL' && inventarioEquipoQuery.isLoading && (
          <p className="p-4 text-sm text-slate-500">
            Cargando inventario del equipo…
          </p>
        )}
        {tab === 'DEVOL' && inventarioEquipoQuery.isError && (
          <p className="p-4 text-sm text-red-600">
            No se pudo obtener el inventario del equipo origen.
          </p>
        )}

        {filasDisponibles.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">ID Lista</th>
                <th className="px-4 py-2">Código</th>
                <th className="px-4 py-2">Descripción</th>
                <th className="px-4 py-2">U.M.</th>
                <th className="px-4 py-2">Disponible</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filasDisponibles.map((fila) => (
                <tr key={fila.material_id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-slate-600">
                    {fila.material_id}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-700">
                    {fila.codigo ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {fila.descripcion}
                  </td>
                  <td className="px-4 py-2 text-slate-500">{fila.u_m ?? '—'}</td>
                  <td className="px-4 py-2 font-semibold text-slate-700">
                    {fila.stock_disponible.toLocaleString('es-MX')}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => agregarAlCarrito(fila)}
                      disabled={carrito.some(
                        (l) => l.material_id === fila.material_id,
                      )}
                      className="rounded-md bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-40"
                    >
                      <Plus className="inline h-3 w-3" /> Agregar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {filasDisponibles.length === 0 &&
          !stockOrigenQuery.isLoading &&
          !inventarioEquipoQuery.isLoading && (
            <p className="p-4 text-sm text-slate-500">
              {tab === 'TEAMS'
                ? 'Seleccione una sección origen para ver su inventario.'
                : 'Seleccione un equipo origen para ver su inventario (solo materiales con stock > 0).'}
            </p>
          )}
      </div>

      {/* Carrito + Revisar */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 p-3">
          <h3 className="text-sm font-semibold text-slate-800">
            Carrito ({carrito.length})
          </h3>
          <button
            type="button"
            onClick={limpiarCarrito}
            className="flex items-center gap-1 text-xs font-medium text-red-600 hover:text-red-800"
          >
            <X className="h-3 w-3" /> Vaciar
          </button>
        </div>
        <CartRows
          lines={carrito}
          field={field}
          onChange={actualizarCantidad}
          onRemove={quitarDelCarrito}
        />
        <div className="flex items-center justify-between border-t border-slate-100 p-3">
          <p className="text-xs text-slate-400">
            Proyecciones visuales: no representan el saldo confirmado por el
            servidor.
          </p>
          <button
            type="button"
            onClick={confirmar}
            disabled={
              carritoInvalido ||
              !extremosValidos ||
              crearBorradorMut.isPending ||
              procesarMut.isPending
            }
            className="flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Check className="h-4 w-4" /> Confirmar {tab}
          </button>
        </div>
      </div>

      {/* Historial de movimientos */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-3">
          <h3 className="text-sm font-semibold text-slate-800">
            Historial de movimientos
          </h3>
        </div>
        {movimientosQuery.isLoading && (
          <p className="p-4 text-sm text-slate-500">Cargando historial…</p>
        )}
        {movimientosQuery.isError && (
          <p className="p-4 text-sm text-red-600">
            No se pudo obtener el historial de movimientos.
          </p>
        )}
        {movimientos.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2">ID</th>
                <th className="px-4 py-2">Tipo</th>
                <th className="px-4 py-2">Recorrido</th>
                <th className="px-4 py-2">Líneas</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {movimientos.map((m) => (
                <tr key={m.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-slate-600">{m.id}</td>
                  <td className="px-4 py-2 font-semibold text-slate-700">
                    {m.tipo_movimiento}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {detalleMovimiento(m)}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {m.detalle.length}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                        BADGE_ESTADO[m.estado] ?? 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {ESTADOS_MOVIMIENTO[m.estado]}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    {m.estado === 'BORRADOR' && (
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => procesarMut.mutate(m.id)}
                          disabled={procesarMut.isPending}
                          className="rounded-md bg-green-600 px-2 py-1 text-xs font-medium text-white hover:bg-green-700"
                        >
                          Procesar
                        </button>
                        <button
                          type="button"
                          onClick={() => eliminarBorradorMut.mutate(m.id)}
                          className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
                        >
                          Eliminar
                        </button>
                      </div>
                    )}
                    {m.estado === 'CONFIRMADO' && (
                      <button
                        type="button"
                        onClick={() => {
                          setMovimientoACancelar(m)
                          setMotivoCancelacion('')
                          setCancelOpen(true)
                        }}
                        className="flex items-center gap-1 rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
                      >
                        <Undo2 className="h-3 w-3" /> Cancelar
                      </button>
                    )}
                    {m.estado === 'CANCELADO' && (
                      <button
                        type="button"
                        disabled
                        title="Movimiento Revertido / Cancelado"
                        className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-400 cursor-not-allowed"
                      >
                        Movimiento Revertido / Cancelado
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {movimientos.length === 0 &&
          !movimientosQuery.isLoading &&
          !movimientosQuery.isError && (
            <p className="p-4 text-sm text-slate-500">Sin movimientos.</p>
          )}
      </div>

      {/* Modal de cancelación (FASE 4) */}
      <Modal
        open={cancelOpen}
        title="Cancelar Movimiento"
        onClose={() => setCancelOpen(false)}
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-700">
            La cancelación revierte el movimiento{' '}
            <span className="font-semibold">
              #{movimientoACancelar?.id ?? ''}{' '}
              {movimientoACancelar?.tipo_movimiento ?? ''}
            </span>{' '}
            y restaura el stock de origen y destino. Esta acción es irreversible
            y queda registrada en auditoría.
          </p>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Motivo (opcional)
            </label>
            <textarea
              value={motivoCancelacion}
              onChange={(e) => setMotivoCancelacion(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="Motivo de la cancelación"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCancelOpen(false)}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Volver
            </button>
            <button
              type="button"
              onClick={confirmarCancelacion}
              disabled={cancelarMut.isPending}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {cancelarMut.isPending ? 'Cancelando…' : 'Confirmar Cancelación'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
