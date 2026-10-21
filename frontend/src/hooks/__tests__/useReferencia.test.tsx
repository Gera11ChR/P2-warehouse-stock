import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  useCrearReferencia,
  useEliminarReferencia,
  useModificarReferencia,
  useOpcionesOrigenReferencia,
  useReferencia,
} from '../useReferencia'
import {
  crearReferencia,
  eliminarReferencia,
  listarReferencia,
  modificarReferencia,
} from '../../services/referencia'
import { listFibraStock } from '../../services/fibra'
import { listSecciones, stockSeccion } from '../../services/inventory'
import { useToast } from '../useToasts'
import type {
  ReferenciaLinea,
  ReferenciaList,
  Seccion,
  SeccionStockRow,
} from '../../types'

// REQ-REF-005/013/014/017 — capa de estado: fail-closed, sin recálculo en el
// cliente, invalidación ACOTADA a ['referencia', equipoId] tras el éxito
// (jamás inventarios, catálogo, reportes, actividades ni auditoría) y
// orígenes del selector de solo lectura (una opción por sección GENERAL
// activa, sin sumar stock; Inventario FO de listFibraStock).

vi.mock('../../services/referencia', () => ({
  listarReferencia: vi.fn(),
  crearReferencia: vi.fn(),
  modificarReferencia: vi.fn(),
  eliminarReferencia: vi.fn(),
}))
vi.mock('../../services/fibra', () => ({ listFibraStock: vi.fn() }))
vi.mock('../../services/inventory', () => ({
  listSecciones: vi.fn(),
  stockSeccion: vi.fn(),
}))
vi.mock('../useToasts', () => ({ useToast: vi.fn() }))

const pushToast = vi.fn()
const pushError = vi.fn()

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const claves = () => invalidate.mock.calls.map((c) => c[0]?.queryKey)
  return { queryClient, wrapper, claves }
}

const linea = (overrides: Partial<ReferenciaLinea> = {}): ReferenciaLinea => ({
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  cantidad_semanal: 2.5,
  ...overrides,
})

const lista = (items: ReferenciaLinea[]): ReferenciaList => ({
  items,
  total: items.length,
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useToast).mockReturnValue({ pushToast, pushError })
})

describe('useReferencia (GET, REQ-REF-005)', () => {
  it('expone las líneas devueltas por el backend (orden y U.M. los decide el servidor)', async () => {
    const { wrapper } = setup()
    vi.mocked(listarReferencia).mockResolvedValue([
      linea({ material_id: 2, descripcion: 'Acopladores', cantidad_semanal: 1 }),
      linea({ material_id: 1, descripcion: 'Cable UTP', cantidad_semanal: 3 }),
    ])
    const { result } = renderHook(() => useReferencia(4), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listarReferencia).toHaveBeenCalledWith(4)
    expect(result.current.data).toHaveLength(2)
  })

  it('enabled=false: no dispara la consulta', () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useReferencia(4, false), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(listarReferencia).not.toHaveBeenCalled()
  })

  it('FAIL-CLOSED: un error NUNCA se reinterpreta como Referencia vacía', async () => {
    const { wrapper } = setup()
    vi.mocked(listarReferencia).mockRejectedValue(new Error('403'))
    const { result } = renderHook(() => useReferencia(4), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})

describe('useCrearReferencia (POST, REQ-REF-006/017)', () => {
  it('éxito: toast + invalida SOLO la Referencia de la Unidad', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(crearReferencia).mockResolvedValue(lista([linea()]))
    const { result } = renderHook(() => useCrearReferencia(4), { wrapper })
    const payload = { lineas: [{ material_id: 10, cantidad_semanal: 2.5 }] }
    await result.current.mutateAsync(payload)
    expect(crearReferencia).toHaveBeenCalledWith(4, payload)
    expect(pushToast).toHaveBeenCalledWith(
      'Materiales agregados a la Referencia de la Unidad',
    )
    expect(claves()).toEqual([['referencia', 4]])
  })

  it('rechazo: pushError y NINGUNA invalidación (nada cambió)', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(crearReferencia).mockRejectedValue(new Error('409'))
    const { result } = renderHook(() => useCrearReferencia(4), { wrapper })
    await expect(
      result.current.mutateAsync({ lineas: [] }),
    ).rejects.toThrow('409')
    expect(pushError).toHaveBeenCalled()
    expect(claves()).toEqual([])
  })
})

describe('useModificarReferencia (PATCH, REQ-REF-008/017)', () => {
  it('éxito: envía {materialId, payload} al servicio, toast e invalidación ACOTADA', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(modificarReferencia).mockResolvedValue(linea({ cantidad_semanal: 7 }))
    const { result } = renderHook(() => useModificarReferencia(4), { wrapper })
    await result.current.mutateAsync({
      materialId: 10,
      payload: { cantidad_semanal: 7 },
    })
    expect(modificarReferencia).toHaveBeenCalledWith(4, 10, {
      cantidad_semanal: 7,
    })
    expect(pushToast).toHaveBeenCalled()
    expect(claves()).toEqual([['referencia', 4]])
  })

  it('rechazo: pushError sin invalidar', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(modificarReferencia).mockRejectedValue(new Error('404'))
    const { result } = renderHook(() => useModificarReferencia(4), { wrapper })
    await expect(
      result.current.mutateAsync({ materialId: 10, payload: { cantidad_semanal: 7 } }),
    ).rejects.toThrow('404')
    expect(pushError).toHaveBeenCalled()
    expect(claves()).toEqual([])
  })
})

describe('useEliminarReferencia (DELETE, REQ-REF-009/017)', () => {
  it('éxito: elimina por materialId, toast e invalidación ACOTADA', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(eliminarReferencia).mockResolvedValue(undefined)
    const { result } = renderHook(() => useEliminarReferencia(4), { wrapper })
    await result.current.mutateAsync(10)
    expect(eliminarReferencia).toHaveBeenCalledWith(4, 10)
    expect(pushToast).toHaveBeenCalled()
    expect(claves()).toEqual([['referencia', 4]])
  })
})

describe('invalidación ACOTADA (REQ-REF-017)', () => {
  it('ninguna mutación de Referencia toca inventarios, catálogo, reportes, actividades ni auditoría', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(crearReferencia).mockResolvedValue(lista([linea()]))
    vi.mocked(modificarReferencia).mockResolvedValue(linea())
    vi.mocked(eliminarReferencia).mockResolvedValue(undefined)
    const { result } = renderHook(
      () => ({
        crear: useCrearReferencia(4),
        modificar: useModificarReferencia(4),
        eliminar: useEliminarReferencia(4),
      }),
      { wrapper },
    )
    await result.current.crear.mutateAsync({
      lineas: [{ material_id: 10, cantidad_semanal: 1 }],
    })
    await result.current.modificar.mutateAsync({
      materialId: 10,
      payload: { cantidad_semanal: 2 },
    })
    await result.current.eliminar.mutateAsync(10)
    const clavesInvalidadas = claves()
    expect(clavesInvalidadas).toHaveLength(3)
    for (const clave of clavesInvalidadas) {
      expect(clave).toEqual(['referencia', 4])
    }
    const prohibidas = [
      ['stock'],
      ['fibra'],
      ['secciones'],
      ['equipo', 4],
      ['auditoria'],
      ['inventario', 'resumen-general'],
      ['reportes'],
      ['actividades', 4],
      ['movimientos'],
    ]
    for (const prohibida of prohibidas) {
      expect(clavesInvalidadas).not.toContainEqual(prohibida)
    }
  })
})

describe('useOpcionesOrigenReferencia (orígenes de SOLO lectura, P-8/Q5)', () => {
  const seccionGeneral = (id: number, nombre: string, activa = true): Seccion => ({
    almacen_id: id,
    nombre,
    tipo: 'GENERAL',
    is_active: activa,
  })

  const filaStock = (
    material_id: number,
    descripcion: string,
    stock_actual: number,
    u_m: string | null = 'PZ',
  ): SeccionStockRow => ({
    material_id,
    codigo: null,
    descripcion,
    u_m,
    stock_minimo: null,
    stock_actual,
    valor_unitario: 1,
    alerta_stock: false,
  })

  it('General: una opción por sección GENERAL ACTIVA; el stock se copia TAL CUAL (sin sumar)', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockResolvedValue([
      seccionGeneral(1, 'Inventario General'),
      seccionGeneral(2, 'Inventario Norte'),
      seccionGeneral(3, 'Sección inactiva', false),
      { almacen_id: 9, nombre: 'FO', tipo: 'FO', is_active: true },
    ])
    // Mismo material en DOS secciones con stock distinto: dos opciones.
    vi.mocked(stockSeccion)
      .mockResolvedValueOnce([filaStock(10, 'Cinta aislante', 40)])
      .mockResolvedValueOnce([filaStock(10, 'Cinta aislante', 12), filaStock(11, 'Acopladores', 3)])
    vi.mocked(listFibraStock).mockResolvedValue([])
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() =>
      expect(result.current.general.options).toEqual([
        {
          origen: 'general',
          almacen_id: 1,
          nombre_seccion: 'Inventario General',
          material_id: 10,
          descripcion: 'Cinta aislante',
          u_m: 'PZ',
          stock_actual: 40,
        },
        {
          origen: 'general',
          almacen_id: 2,
          nombre_seccion: 'Inventario Norte',
          material_id: 10,
          descripcion: 'Cinta aislante',
          u_m: 'PZ',
          stock_actual: 12,
        },
        {
          origen: 'general',
          almacen_id: 2,
          nombre_seccion: 'Inventario Norte',
          material_id: 11,
          descripcion: 'Acopladores',
          u_m: 'PZ',
          stock_actual: 3,
        },
      ]),
    )
    expect(stockSeccion).toHaveBeenCalledTimes(2)
    expect(stockSeccion).not.toHaveBeenCalledWith(3)
    expect(result.current.general.isError).toBe(false)
  })

  it('FO: una opción por fila de listFibraStock', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockResolvedValue([])
    vi.mocked(listFibraStock).mockResolvedValue([
      {
        material_id: 20,
        codigo: 'FIB-001',
        descripcion: 'Fibra drop 1 hilo',
        u_m: 'METRO (M)',
        stock_minimo: 100,
        stock_actual: 2500,
        valor_unitario: 1,
        alerta_stock: false,
      },
    ])
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() =>
      expect(result.current.fo.options).toEqual([
        {
          origen: 'fo',
          material_id: 20,
          descripcion: 'Fibra drop 1 hilo',
          u_m: 'METRO (M)',
          stock_actual: 2500,
        },
      ]),
    )
  })

  it('FAIL-CLOSED: error de secciones → sin opciones (jamás origen vacío)', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockRejectedValue(new Error('500'))
    vi.mocked(listFibraStock).mockResolvedValue([])
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() => expect(result.current.general.isError).toBe(true))
    expect(result.current.general.options).toBeUndefined()
  })

  it('FAIL-CLOSED: error en UNA consulta de stock → sin opciones General', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockResolvedValue([
      seccionGeneral(1, 'Inventario General'),
      seccionGeneral(2, 'Inventario Norte'),
    ])
    vi.mocked(stockSeccion)
      .mockResolvedValueOnce([filaStock(10, 'Cinta', 40)])
      .mockRejectedValueOnce(new Error('500'))
    vi.mocked(listFibraStock).mockResolvedValue([])
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() => expect(result.current.general.isError).toBe(true))
    expect(result.current.general.options).toBeUndefined()
  })

  it('FAIL-CLOSED: error del Inventario FO → isError y options undefined', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockResolvedValue([])
    vi.mocked(listFibraStock).mockRejectedValue(new Error('403'))
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() => expect(result.current.fo.isError).toBe(true))
    expect(result.current.fo.options).toBeUndefined()
  })

  it('refetch del origen General reintenta secciones y TODAS las consultas de stock', async () => {
    const { wrapper } = setup()
    vi.mocked(listSecciones).mockRejectedValue(new Error('500'))
    vi.mocked(listFibraStock).mockResolvedValue([])
    const { result } = renderHook(() => useOpcionesOrigenReferencia(true), {
      wrapper,
    })
    await waitFor(() => expect(result.current.general.isError).toBe(true))
    const llamadas = vi.mocked(listSecciones).mock.calls.length
    result.current.general.refetch()
    await waitFor(() =>
      expect(vi.mocked(listSecciones).mock.calls.length).toBeGreaterThan(llamadas),
    )
  })

  it('enabled=false: ninguna consulta de orígenes se dispara', () => {
    const { wrapper } = setup()
    renderHook(() => useOpcionesOrigenReferencia(false), { wrapper })
    expect(listSecciones).not.toHaveBeenCalled()
    expect(listFibraStock).not.toHaveBeenCalled()
  })
})
