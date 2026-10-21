import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  useExportarReporteActividades,
  useReporteActividades,
} from '../useReportes'
import {
  descargarReporteActividadesXlsx,
  ErrorDescargaReporte,
  listarReporteActividades,
} from '../../services/reportes'
import { guardarBlob } from '../../utils/descargaArchivo'
import type { Actividad } from '../../types'

vi.mock('../../services/reportes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reportes')>()),
  listarReporteActividades: vi.fn(),
  descargarReporteActividadesXlsx: vi.fn(),
}))
vi.mock('../../utils/descargaArchivo', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../utils/descargaArchivo')>()),
  guardarBlob: vi.fn(),
}))

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

beforeEach(() => vi.clearAllMocks())

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

describe('useReporteActividades', () => {
  it('expone los items del backend; cambiar filtros refetcha', async () => {
    const { wrapper } = setup()
    vi.mocked(listarReporteActividades).mockResolvedValue([actividad])
    const { result, rerender } = renderHook(
      ({ equipo }: { equipo: number }) =>
        useReporteActividades({ equipo_id: equipo }),
      { wrapper, initialProps: { equipo: 1 } },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([actividad])
    expect(listarReporteActividades).toHaveBeenLastCalledWith({ equipo_id: 1 })
    rerender({ equipo: 2 })
    await waitFor(() =>
      expect(listarReporteActividades).toHaveBeenLastCalledWith({
        equipo_id: 2,
      }),
    )
  })

  it('invalidar ["reportes","actividades"] recarga el listado', async () => {
    const { wrapper, queryClient } = setup()
    vi.mocked(listarReporteActividades).mockResolvedValue([])
    renderHook(() => useReporteActividades({}), { wrapper })
    await waitFor(() =>
      expect(listarReporteActividades).toHaveBeenCalledTimes(1),
    )
    await act(() =>
      queryClient.invalidateQueries({ queryKey: ['reportes', 'actividades'] }),
    )
    expect(listarReporteActividades).toHaveBeenCalledTimes(2)
  })

  it('FAIL-CLOSED: un error NO se traduce a lista vacía', async () => {
    const { wrapper } = setup()
    vi.mocked(listarReporteActividades).mockRejectedValue(new Error('403'))
    const { result } = renderHook(() => useReporteActividades({}), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})

describe('useExportarReporteActividades', () => {
  it('éxito consolidado: idle → loading → success; guarda el blob con el nombre del servidor', async () => {
    const { wrapper } = setup()
    const blob = new Blob(['x'])
    let resolver!: (v: { blob: Blob; nombreArchivo: string }) => void
    vi.mocked(descargarReporteActividadesXlsx).mockReturnValue(
      new Promise((r) => {
        resolver = r
      }),
    )
    const { result } = renderHook(() => useExportarReporteActividades(), {
      wrapper,
    })
    expect(result.current.status).toEqual({ estado: 'idle' })

    act(() => result.current.exportar('consolidado', { equipo_id: 3 }))
    await waitFor(() =>
      expect(result.current.status).toEqual({
        estado: 'loading',
        alcance: 'consolidado',
      }),
    )
    expect(descargarReporteActividadesXlsx).toHaveBeenCalledWith({
      equipo_id: 3,
    })
    expect(guardarBlob).not.toHaveBeenCalled()

    await act(async () => resolver({ blob, nombreArchivo: 'libro.xlsx' }))
    await waitFor(() =>
      expect(result.current.status).toEqual({
        estado: 'success',
        alcance: 'consolidado',
        nombreArchivo: 'libro.xlsx',
      }),
    )
    expect(guardarBlob).toHaveBeenCalledWith(blob, 'libro.xlsx')
  })

  it('exportación individual: alcance individual y actividad_id en la petición', async () => {
    const { wrapper } = setup()
    vi.mocked(descargarReporteActividadesXlsx).mockResolvedValue({
      blob: new Blob(['x']),
      nombreArchivo: 'reporte-actividades-R0001.xlsx',
    })
    const { result } = renderHook(() => useExportarReporteActividades(), {
      wrapper,
    })
    act(() => result.current.exportar('individual', { actividad_id: 1 }))
    await waitFor(() => expect(result.current.status.estado).toBe('success'))
    expect(result.current.status).toEqual({
      estado: 'success',
      alcance: 'individual',
      nombreArchivo: 'reporte-actividades-R0001.xlsx',
    })
    expect(descargarReporteActividadesXlsx).toHaveBeenCalledWith({
      actividad_id: 1,
    })
  })

  it.each([
    [404, 'Sin actividades para los filtros indicados'],
    [422, 'Input should be a valid date'],
  ])(
    'error %i: estado error con alcance, httpStatus y detalle; no guarda archivo',
    async (status, detalle) => {
      const { wrapper } = setup()
      vi.mocked(descargarReporteActividadesXlsx).mockRejectedValue(
        new ErrorDescargaReporte(status, detalle),
      )
      const { result } = renderHook(() => useExportarReporteActividades(), {
        wrapper,
      })
      act(() => result.current.exportar('consolidado', {}))
      await waitFor(() => expect(result.current.status.estado).toBe('error'))
      expect(result.current.status).toEqual({
        estado: 'error',
        alcance: 'consolidado',
        httpStatus: status,
        detalle,
      })
      expect(guardarBlob).not.toHaveBeenCalled()
    },
  )

  it('error sin respuesta (red): httpStatus indefinido', async () => {
    const { wrapper } = setup()
    vi.mocked(descargarReporteActividadesXlsx).mockRejectedValue(
      new Error('Network Error'),
    )
    const { result } = renderHook(() => useExportarReporteActividades(), {
      wrapper,
    })
    act(() => result.current.exportar('consolidado', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('error'))
    expect(result.current.status).toMatchObject({
      estado: 'error',
      httpStatus: undefined,
    })
  })

  it('reiniciar vuelve a idle y NO actúa durante una descarga en curso', async () => {
    const { wrapper } = setup()
    vi.mocked(descargarReporteActividadesXlsx).mockRejectedValueOnce(
      new ErrorDescargaReporte(404),
    )
    const { result } = renderHook(() => useExportarReporteActividades(), {
      wrapper,
    })
    act(() => result.current.exportar('consolidado', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('error'))
    act(() => result.current.reiniciar())
    expect(result.current.status).toEqual({ estado: 'idle' })

    let resolver!: (v: { blob: Blob; nombreArchivo: string }) => void
    vi.mocked(descargarReporteActividadesXlsx).mockReturnValueOnce(
      new Promise((r) => {
        resolver = r
      }),
    )
    act(() => result.current.exportar('individual', { actividad_id: 2 }))
    await waitFor(() => expect(result.current.status.estado).toBe('loading'))
    expect(result.current.isPending).toBe(true)
    act(() => result.current.reiniciar())
    expect(result.current.status.estado).toBe('loading')
    await act(async () =>
      resolver({ blob: new Blob(['x']), nombreArchivo: 'a.xlsx' }),
    )
    await waitFor(() => expect(result.current.status.estado).toBe('success'))
  })
})
