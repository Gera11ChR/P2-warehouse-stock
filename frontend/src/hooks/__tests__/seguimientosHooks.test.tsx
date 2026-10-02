import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSeguimiento, useSeguimientos } from '../useSeguimientos'
import { useCrearSeguimiento } from '../useCrearSeguimiento'
import { useCerrarSeguimiento } from '../useCerrarSeguimiento'
import { useAgregarTodoSeguimiento } from '../useAgregarTodoSeguimiento'
import {
  agregarTodoSeguimiento,
  cerrarSeguimiento,
  crearSeguimiento,
  getSeguimiento,
  listSeguimientos,
} from '../../services/seguimientos'
import type { Seguimiento } from '../../types'

vi.mock('../../services/seguimientos', () => ({
  listSeguimientos: vi.fn(),
  getSeguimiento: vi.fn(),
  crearSeguimiento: vi.fn(),
  cerrarSeguimiento: vi.fn(),
  agregarTodoSeguimiento: vi.fn(),
}))

function seg(overrides: Partial<Seguimiento>): Seguimiento {
  return {
    id: 1,
    equipo_id: 4,
    fecha: '2026-10-01',
    observaciones: null,
    usuario: 'demo-operador',
    estado: 'CERRADA',
    created_at: '',
    updated_at: '',
    closed_at: null,
    items: [],
    ...overrides,
  }
}

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

beforeEach(() => vi.clearAllMocks())

describe('useSeguimientos / useSeguimiento (queries)', () => {
  it('no dispara sin equipo seleccionado', () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useSeguimientos(null), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(listSeguimientos).not.toHaveBeenCalled()
  })

  it('expone la lista y `abierta` (la ABIERTA vigente) o null', async () => {
    const { wrapper } = setup()
    vi.mocked(listSeguimientos).mockResolvedValue([
      seg({ id: 2, estado: 'ABIERTA' }),
      seg({ id: 1, estado: 'CERRADA' }),
    ])
    const { result } = renderHook(() => useSeguimientos(4), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listSeguimientos).toHaveBeenCalledWith(4)
    expect(result.current.data).toHaveLength(2)
    expect(result.current.abierta?.id).toBe(2)
  })

  it('sin ABIERTA → abierta null', async () => {
    const { wrapper } = setup()
    vi.mocked(listSeguimientos).mockResolvedValue([seg({ estado: 'CERRADA' })])
    const { result } = renderHook(() => useSeguimientos(4), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.abierta).toBeNull()
  })

  it('errores fail-closed: isError, nunca lista vacía inventada', async () => {
    const { wrapper } = setup()
    vi.mocked(listSeguimientos).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useSeguimientos(4), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
    expect(result.current.abierta).toBeNull()
  })

  it('useSeguimiento: obtiene el detalle solo con ambos ids', async () => {
    const { wrapper } = setup()
    vi.mocked(getSeguimiento).mockResolvedValue(seg({ id: 9 }))
    const { result: inactivo } = renderHook(() => useSeguimiento(4, null), {
      wrapper,
    })
    expect(inactivo.current.fetchStatus).toBe('idle')
    const { result } = renderHook(() => useSeguimiento(4, 9), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(getSeguimiento).toHaveBeenCalledWith(4, 9)
  })
})

describe('useCrearSeguimiento — invalidación', () => {
  it('éxito: invalida seguimientos + inventario del equipo + auditoría (no actas)', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(crearSeguimiento).mockResolvedValue(seg({ estado: 'ABIERTA' }))
    const { result } = renderHook(() => useCrearSeguimiento(4), { wrapper })
    const payload = { items: [{ material_id: 1, cantidad_tomada: 2 }] }
    await result.current.mutateAsync(payload)
    expect(crearSeguimiento).toHaveBeenCalledWith(4, payload)
    expect(claves()).toEqual(
      expect.arrayContaining([['seguimientos', 4], ['equipo', 4], ['auditoria']]),
    )
    expect(claves()).not.toContainEqual(['reportes', 'actas', 'consumo'])
  })

  it('error: no invalida nada (el estado persistido no cambió)', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(crearSeguimiento).mockRejectedValue(new Error('409'))
    const { result } = renderHook(() => useCrearSeguimiento(4), { wrapper })
    await expect(result.current.mutateAsync({ items: [] })).rejects.toThrow('409')
    expect(claves()).toEqual([])
  })
})

describe('useCerrarSeguimiento — invalidación y payload', () => {
  it('envía { seguimientoId } al servicio e invalida seguimientos, inventario del equipo y actas de CONSUMO', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(cerrarSeguimiento).mockResolvedValue(seg({}))
    const { result } = renderHook(() => useCerrarSeguimiento(4), { wrapper })
    const payload = { sobrantes: [{ material_id: 1, cantidad_sobrante: 0 }] }
    await result.current.mutateAsync({ seguimientoId: 7, payload })
    expect(cerrarSeguimiento).toHaveBeenCalledWith(4, 7, payload)
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['seguimientos', 4],
        ['equipo', 4],
        ['reportes', 'actas', 'consumo'],
        ['auditoria'],
      ]),
    )
  })

  it('error 409 (doble cierre): no invalida y propaga', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(cerrarSeguimiento).mockRejectedValue(new Error('409'))
    const { result } = renderHook(() => useCerrarSeguimiento(4), { wrapper })
    await expect(
      result.current.mutateAsync({ seguimientoId: 7, payload: { sobrantes: [] } }),
    ).rejects.toThrow('409')
    expect(claves()).toEqual([])
  })

  it('el cierre marca como obsoletas las actas de consumo cacheadas', async () => {
    const { wrapper, queryClient } = setup()
    queryClient.setQueryData(['reportes', 'actas', 'consumo', {}], [])
    const obs = queryClient
      .getQueryCache()
      .find({ queryKey: ['reportes', 'actas', 'consumo', {}] })
    expect(obs?.state.isInvalidated).toBe(false)
    vi.mocked(cerrarSeguimiento).mockResolvedValue(seg({}))
    const { result } = renderHook(() => useCerrarSeguimiento(4), { wrapper })
    await result.current.mutateAsync({ seguimientoId: 7, payload: { sobrantes: [] } })
    expect(obs?.state.isInvalidated).toBe(true)
  })
})

describe('useAgregarTodoSeguimiento (REQ-P2-CON-003; sin pantalla)', () => {
  it('llama al servicio con y sin clave de idempotencia e invalida seguimientos', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(agregarTodoSeguimiento).mockResolvedValue({
      lineas_agregadas: 3,
      seguimiento: seg({ estado: 'ABIERTA' }),
    })
    const { result } = renderHook(() => useAgregarTodoSeguimiento(4), {
      wrapper,
    })
    const r1 = await result.current.mutateAsync({ seguimientoId: 7 })
    expect(agregarTodoSeguimiento).toHaveBeenLastCalledWith(4, 7, undefined)
    expect(r1.lineas_agregadas).toBe(3)
    await result.current.mutateAsync({
      seguimientoId: 7,
      claveIdempotencia: 'agregar-todo-k',
    })
    expect(agregarTodoSeguimiento).toHaveBeenLastCalledWith(
      4,
      7,
      'agregar-todo-k',
    )
    expect(claves()).toEqual(
      expect.arrayContaining([['seguimientos', 4], ['equipo', 4], ['auditoria']]),
    )
  })

  it('409 (no ABIERTA) se propaga sin invalidar', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(agregarTodoSeguimiento).mockRejectedValue(new Error('409'))
    const { result } = renderHook(() => useAgregarTodoSeguimiento(4), {
      wrapper,
    })
    await expect(
      result.current.mutateAsync({ seguimientoId: 7 }),
    ).rejects.toThrow('409')
    expect(claves()).toEqual([])
  })
})
