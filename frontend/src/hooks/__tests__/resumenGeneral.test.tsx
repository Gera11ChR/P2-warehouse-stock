import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useResumenGeneral } from '../useResumenGeneral'
import {
  invalidarSeguimientoEquipo,
  invalidarTrasConfirmarMovimiento,
  invalidarTrasMover,
  invalidarTrasSumar,
  queryKeys,
} from '../queryKeys'
import { getResumenGeneral } from '../../services/inventory'

// RF-4/RF-5: la clave `['inventario','resumen-general']` se invalida en TODA
// mutación que cambia existencias o valor; React nunca calcula el total.

vi.mock('../../services/inventory', () => ({
  getResumenGeneral: vi.fn(),
}))

const CLAVE = ['inventario', 'resumen-general']

function nuevoCliente() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(client, 'invalidateQueries')
  return { client, spy }
}

const invalidaResumen = (spy: ReturnType<typeof nuevoCliente>['spy']) =>
  spy.mock.calls.some(
    ([filtro]) => JSON.stringify(filtro?.queryKey) === JSON.stringify(CLAVE),
  )

describe('useResumenGeneral', () => {
  it('consulta GET /inventario/resumen-general y expone el valor del servidor', async () => {
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 22.5, moneda: 'MXN' })
    const { client } = nuevoCliente()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useResumenGeneral(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ valor_total: 22.5, moneda: 'MXN' })
    expect(client.getQueryCache().find({ queryKey: [...CLAVE] })).toBeDefined()
  })

  it('un error de API no se reinterpreta como 0 (fail-closed)', async () => {
    vi.mocked(getResumenGeneral).mockRejectedValue(new Error('500'))
    const { client } = nuevoCliente()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useResumenGeneral(), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})

describe('invalidación de resumen-general tras mutaciones (plan §4.1)', () => {
  it('queryKeys.resumenGeneral() es la clave contractual', () => {
    expect(queryKeys.resumenGeneral()).toEqual(CLAVE)
  })

  it('+Cantidad y Mover (GENERAL y FO) invalidan el Valor Total', async () => {
    const a = nuevoCliente()
    await invalidarTrasSumar(a.client, { destino: 'FO', material_id: 1, cantidad: 2.5 })
    expect(invalidaResumen(a.spy)).toBe(true)

    const b = nuevoCliente()
    await invalidarTrasMover(b.client, {
      origen: 'GENERAL',
      destino: 'FO',
      material_id: 1,
      cantidad: 1,
    })
    expect(invalidaResumen(b.spy)).toBe(true)
  })

  it('confirmar TRANSF/Devolución y las mutaciones de seguimiento invalidan el Valor Total', async () => {
    const a = nuevoCliente()
    await invalidarTrasConfirmarMovimiento(a.client, 'TEAMS')
    expect(invalidaResumen(a.spy)).toBe(true)

    const b = nuevoCliente()
    await invalidarTrasConfirmarMovimiento(b.client, 'DEVOL')
    expect(invalidaResumen(b.spy)).toBe(true)

    const c = nuevoCliente()
    await invalidarSeguimientoEquipo(c.client, 3)
    expect(invalidaResumen(c.spy)).toBe(true)
  })
})
