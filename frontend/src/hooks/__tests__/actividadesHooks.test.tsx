import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  useActividadPendiente,
  useActividades,
  useCrearActividad,
} from '../useActividades'
import {
  crearActividad,
  listarActividades,
  obtenerActividadPendiente,
} from '../../services/actividades'
import type { Actividad, ActividadCreatePayload } from '../../types'

vi.mock('../../services/actividades', () => ({
  obtenerActividadPendiente: vi.fn(),
  listarActividades: vi.fn(),
  crearActividad: vi.fn(),
}))

const pendienteMock = vi.mocked(obtenerActividadPendiente)
const listaMock = vi.mocked(listarActividades)
const crearMock = vi.mocked(crearActividad)

const actividad: Actividad = {
  actividad_id: 1,
  folio: 'R0001',
  folio_num: 1,
  seguimiento_id: 9,
  equipo_id: 4,
  equipo_nombre: 'Unidad Norte',
  fecha: '2026-10-19T10:00:00Z',
  usuario: 'demo-operador',
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido de fibra'],
  comentarios: null,
  materiales: [],
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

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useActividadPendiente', () => {
  it('expone el pendiente devuelto por el backend', async () => {
    const { wrapper } = setup()
    pendienteMock.mockResolvedValue({
      seguimiento: {
        seguimiento_id: 9,
        fecha_cierre: '2026-10-19T09:00:00Z',
        materiales: [],
      },
    })
    const { result } = renderHook(() => useActividadPendiente(4), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.seguimiento?.seguimiento_id).toBe(9)
  })

  it('no dispara sin equipo (enabled guard)', async () => {
    const { wrapper } = setup()
    renderHook(() => useActividadPendiente(null), { wrapper })
    expect(pendienteMock).not.toHaveBeenCalled()
  })

  it('FAIL-CLOSED: un error NO se traduce a "sin pendiente"', async () => {
    const { wrapper } = setup()
    pendienteMock.mockRejectedValue(new Error('403'))
    const { result } = renderHook(() => useActividadPendiente(4), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})

describe('useActividades', () => {
  it('expone el historial devuelto por el backend', async () => {
    const { wrapper } = setup()
    listaMock.mockResolvedValue({ items: [actividad], total: 1 })
    const { result } = renderHook(() => useActividades(4), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total).toBe(1)
  })
})

describe('useCrearActividad', () => {
  it('postea el payload y tras success invalida pendiente, historial, el listado de Reportes › Actividades y auditoría', async () => {
    const { wrapper, claves } = setup()
    crearMock.mockResolvedValue(actividad)
    const { result } = renderHook(() => useCrearActividad(4), { wrapper })
    const payload: ActividadCreatePayload = {
      seguimiento_id: 9,
      vehiculo: 'Camioneta 12',
      clientes: 'Cliente A',
      direcciones: 'Calle 1',
      actividades: ['Tendido de fibra'],
      comentarios: null,
    }
    await waitFor(() =>
      result.current.mutateAsync(payload).then(() => undefined),
    )
    expect(crearMock).toHaveBeenCalledWith(4, payload)
    const clavesInvalidadas = claves().map((k) => JSON.stringify(k))
    expect(clavesInvalidadas).toContain(
      JSON.stringify(['actividades', 4, 'pendiente']),
    )
    expect(clavesInvalidadas).toContain(JSON.stringify(['actividades', 4]))
    // REQ-REP-015: el listado de Reportes › Actividades se recarga tras
    // confirmar (clave del prefijo sin params: queryKeys.reporteActividades()).
    expect(clavesInvalidadas).toContain(
      JSON.stringify(['reportes', 'actividades']),
    )
    expect(clavesInvalidadas).toContain(JSON.stringify(['auditoria']))
  })

  it('mutación rechazada: el error se propaga y NO se invalida nada', async () => {
    const { wrapper, claves } = setup()
    crearMock.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          error: { message: 'El seguimiento ya tiene una actividad confirmada.' },
        },
      },
    })
    const { result } = renderHook(() => useCrearActividad(4), { wrapper })
    await waitFor(() =>
      result.current
        .mutateAsync({
          seguimiento_id: 9,
          vehiculo: 'V',
          clientes: 'C',
          direcciones: 'D',
          actividades: ['A'],
        })
        .catch(() => undefined)
        .then(() => undefined),
    )
    expect(result.current.isError).toBe(true)
    expect(claves()).toEqual([])
  })

  it('el folio devuelto por el backend llega intacto (sin cálculo local)', async () => {
    const { wrapper } = setup()
    crearMock.mockResolvedValue({ ...actividad, folio: 'R0002', folio_num: 2 })
    const { result } = renderHook(() => useCrearActividad(4), { wrapper })
    let respuesta: Actividad | undefined
    await waitFor(() =>
      result.current
        .mutateAsync({
          seguimiento_id: 9,
          vehiculo: 'V',
          clientes: 'C',
          direcciones: 'D',
          actividades: ['A'],
        })
        .then((a) => {
          respuesta = a
        })
        .then(() => undefined),
    )
    expect(respuesta?.folio).toBe('R0002')
  })
})
