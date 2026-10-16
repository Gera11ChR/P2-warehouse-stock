import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSumarCantidad } from '../useSumarCantidad'
import { useMoverMaterial } from '../useMoverMaterial'
import { moverMaterial, sumarCantidad } from '../../services/inventory'
import {
  invalidarInventariosRapidos,
  invalidarTrasConfirmarMovimiento,
} from '../queryKeys'

vi.mock('../../services/inventory', () => ({
  sumarCantidad: vi.fn(),
  moverMaterial: vi.fn(),
}))

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

describe('useSumarCantidad', () => {
  it('GENERAL: devuelve el DTO del servidor e invalida ["stock"] + auditoría + Valor Total (no ["fibra"])', async () => {
    const { wrapper, claves } = setup()
    const out = {
      destino: 'GENERAL',
      material_id: 1,
      stock_nuevo: 42,
      reenvio_idempotente: false,
    }
    vi.mocked(sumarCantidad).mockResolvedValue(out as never)
    const { result } = renderHook(() => useSumarCantidad(), { wrapper })
    const r = await result.current.mutateAsync({
      destino: 'GENERAL',
      material_id: 1,
      cantidad: 2,
      clave_idempotencia: 'sumar-k',
    })
    expect(r).toBe(out)
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['stock'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['fibra'])
  })

  it('FO: invalida ["fibra"] (inventario único, sin módulo) + Valor Total y no ["stock"]', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(sumarCantidad).mockResolvedValue({} as never)
    const { result } = renderHook(() => useSumarCantidad(), { wrapper })
    await result.current.mutateAsync({
      destino: 'FO',
      material_id: 1,
      cantidad: 2.5,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['fibra'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['stock'])
    expect(claves()).not.toContainEqual(['fibra', 'EN_USO'])
    expect(claves()).not.toContainEqual(['fibra', 'PAQUETE'])
  })

  it('un rechazo (p. ej. 400) también recarga el stock afectado (pantalla posiblemente obsoleta)', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(sumarCantidad).mockRejectedValue(new Error('400'))
    const { result } = renderHook(() => useSumarCantidad(), { wrapper })
    await expect(
      result.current.mutateAsync({
        destino: 'GENERAL',
        material_id: 1,
        cantidad: 0,
      }),
    ).rejects.toThrow('400')
    expect(claves()).toContainEqual(['stock'])
    expect(claves()).toContainEqual(['inventario', 'resumen-general'])
  })
})

describe('useMoverMaterial', () => {
  it('General → FO: invalida origen Y destino (["stock"] y ["fibra"]) + Valor Total', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(moverMaterial).mockResolvedValue({} as never)
    const { result } = renderHook(() => useMoverMaterial(), { wrapper })
    await result.current.mutateAsync({
      origen: 'GENERAL',
      destino: 'FO',
      material_id: 1,
      cantidad: 3,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['stock'],
        ['fibra'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['fibra', 'PAQUETE'])
    expect(claves()).not.toContainEqual(['fibra', 'EN_USO'])
  })

  it('FO → General: invalida ["fibra"] y ["stock"] (cada clave una sola vez)', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(moverMaterial).mockResolvedValue({} as never)
    const { result } = renderHook(() => useMoverMaterial(), { wrapper })
    await result.current.mutateAsync({
      origen: 'FO',
      destino: 'GENERAL',
      material_id: 1,
      cantidad: 0.75,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([['fibra'], ['stock'], ['auditoria']]),
    )
    expect(claves().filter((k) => k?.[0] === 'fibra')).toHaveLength(1)
    expect(claves().filter((k) => k?.[0] === 'stock')).toHaveLength(1)
  })

  it('invalidarInventariosRapidos FO + FO: una sola ["fibra"], además de auditoría y Valor Total', async () => {
    const { queryClient, claves } = setup()
    await invalidarInventariosRapidos(queryClient, [
      { inventario: 'FO' },
      { inventario: 'FO' },
    ])
    expect(claves().filter((k) => k?.[0] === 'fibra')).toHaveLength(1)
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['fibra'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['stock'])
  })

  it('rechazo (409): igual recarga origen y destino', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(moverMaterial).mockRejectedValue(new Error('409'))
    const { result } = renderHook(() => useMoverMaterial(), { wrapper })
    await expect(
      result.current.mutateAsync({
        origen: 'FO',
        destino: 'GENERAL',
        material_id: 1,
        cantidad: 1,
      }),
    ).rejects.toThrow('409')
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['fibra'],
        ['stock'],
        ['inventario', 'resumen-general'],
      ]),
    )
  })
})

describe('helpers de invalidación (queryKeys)', () => {
  it('invalidarInventariosRapidos deduplica extremos iguales', async () => {
    const { queryClient, claves } = setup()
    await invalidarInventariosRapidos(queryClient, [
      { inventario: 'GENERAL' },
      { inventario: 'GENERAL' },
    ])
    expect(claves().filter((k) => k?.[0] === 'stock')).toHaveLength(1)
  })

  it('confirmar TEAMS: movimientos, secciones, stock, fibra, equipo, auditoría y actas de ENTREGA', async () => {
    const { queryClient, claves } = setup()
    await invalidarTrasConfirmarMovimiento(queryClient, 'TEAMS')
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['movimientos'],
        ['secciones'],
        ['stock'],
        ['fibra'],
        ['equipo'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
        ['reportes', 'actas', 'entrega'],
      ]),
    )
  })

  it('confirmar DEVOL no invalida actas (solo TEAMS genera Acta de Entrega)', async () => {
    const { queryClient, claves } = setup()
    await invalidarTrasConfirmarMovimiento(queryClient, 'DEVOL')
    expect(claves()).not.toContainEqual(['reportes', 'actas', 'entrega'])
    expect(claves()).toContainEqual(['equipo'])
  })
})
