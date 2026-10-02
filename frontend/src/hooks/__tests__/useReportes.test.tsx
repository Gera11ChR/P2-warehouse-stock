import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useExportarReporte, useReporteActas } from '../useReportes'
import { descargarActaXlsx, ErrorDescargaReporte, listarActas } from '../../services/reportes'
import { guardarBlob } from '../../utils/descargaArchivo'

vi.mock('../../services/reportes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reportes')>()),
  listarActas: vi.fn(),
  descargarActaXlsx: vi.fn(),
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

describe('useReporteActas', () => {
  it('lista actas del tipo y filtros; cambiar filtros refetcha', async () => {
    const { wrapper } = setup()
    vi.mocked(listarActas).mockResolvedValue([])
    const { result, rerender } = renderHook(
      ({ equipo }: { equipo: number }) =>
        useReporteActas('entrega', { equipo_id: equipo }),
      { wrapper, initialProps: { equipo: 1 } },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listarActas).toHaveBeenLastCalledWith('entrega', { equipo_id: 1 })
    rerender({ equipo: 2 })
    await waitFor(() =>
      expect(listarActas).toHaveBeenLastCalledWith('entrega', { equipo_id: 2 }),
    )
  })

  it('invalidar ["reportes","actas","entrega"] recarga el listado de Entrega y no el de Consumo', async () => {
    const { wrapper, queryClient } = setup()
    vi.mocked(listarActas).mockResolvedValue([])
    const entrega = renderHook(() => useReporteActas('entrega', {}), { wrapper })
    const consumo = renderHook(() => useReporteActas('consumo', {}), { wrapper })
    await waitFor(() => {
      expect(entrega.result.current.isSuccess).toBe(true)
      expect(consumo.result.current.isSuccess).toBe(true)
    })
    expect(listarActas).toHaveBeenCalledTimes(2)
    await act(() =>
      queryClient.invalidateQueries({ queryKey: ['reportes', 'actas', 'entrega'] }),
    )
    expect(listarActas).toHaveBeenCalledTimes(3)
    expect(listarActas).toHaveBeenLastCalledWith('entrega', {})
  })
})

describe('useExportarReporte', () => {
  it('éxito: idle → loading → success; guarda el blob con el nombre del servidor', async () => {
    const { wrapper } = setup()
    const blob = new Blob(['x'])
    let resolver!: (v: { blob: Blob; nombreArchivo: string }) => void
    vi.mocked(descargarActaXlsx).mockReturnValue(
      new Promise((r) => {
        resolver = r
      }),
    )
    const { result } = renderHook(() => useExportarReporte('consumo'), {
      wrapper,
    })
    expect(result.current.status).toEqual({ estado: 'idle' })

    act(() => result.current.exportar('extenso', { equipo_id: 3 }))
    await waitFor(() =>
      expect(result.current.status).toEqual({
        estado: 'loading',
        formato: 'extenso',
      }),
    )
    expect(descargarActaXlsx).toHaveBeenCalledWith('consumo', 'extenso', {
      equipo_id: 3,
    })
    expect(guardarBlob).not.toHaveBeenCalled()

    await act(async () => resolver({ blob, nombreArchivo: 'acta.xlsx' }))
    await waitFor(() =>
      expect(result.current.status).toEqual({
        estado: 'success',
        formato: 'extenso',
        nombreArchivo: 'acta.xlsx',
      }),
    )
    expect(guardarBlob).toHaveBeenCalledWith(blob, 'acta.xlsx')
  })

  it.each([
    [404, 'No hay actas para los filtros indicados'],
    [422, 'Input should be a valid date'],
    [403, undefined],
  ])('error %i: estado error con httpStatus y detalle; no guarda archivo', async (status, detalle) => {
    const { wrapper } = setup()
    vi.mocked(descargarActaXlsx).mockRejectedValue(
      new ErrorDescargaReporte(status, detalle),
    )
    const { result } = renderHook(() => useExportarReporte('entrega'), {
      wrapper,
    })
    act(() => result.current.exportar('normal', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('error'))
    expect(result.current.status).toEqual({
      estado: 'error',
      formato: 'normal',
      httpStatus: status,
      detalle,
    })
    expect(guardarBlob).not.toHaveBeenCalled()
  })

  it('error sin respuesta (red): httpStatus indefinido', async () => {
    const { wrapper } = setup()
    vi.mocked(descargarActaXlsx).mockRejectedValue(new Error('Network Error'))
    const { result } = renderHook(() => useExportarReporte('entrega'), {
      wrapper,
    })
    act(() => result.current.exportar('normal', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('error'))
    expect(result.current.status).toMatchObject({
      estado: 'error',
      httpStatus: undefined,
    })
  })

  it('reiniciar vuelve a idle (no mientras hay una descarga en curso)', async () => {
    const { wrapper } = setup()
    vi.mocked(descargarActaXlsx).mockRejectedValueOnce(
      new ErrorDescargaReporte(404),
    )
    const { result } = renderHook(() => useExportarReporte('entrega'), {
      wrapper,
    })
    act(() => result.current.exportar('normal', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('error'))
    act(() => result.current.reiniciar())
    expect(result.current.status).toEqual({ estado: 'idle' })

    let resolver!: (v: { blob: Blob; nombreArchivo: string }) => void
    vi.mocked(descargarActaXlsx).mockReturnValueOnce(
      new Promise((r) => {
        resolver = r
      }),
    )
    act(() => result.current.exportar('extenso', {}))
    await waitFor(() => expect(result.current.status.estado).toBe('loading'))
    act(() => result.current.reiniciar())
    expect(result.current.status.estado).toBe('loading')
    await act(async () => resolver({ blob: new Blob(['x']), nombreArchivo: 'a.xlsx' }))
    await waitFor(() => expect(result.current.status.estado).toBe('success'))
  })
})
