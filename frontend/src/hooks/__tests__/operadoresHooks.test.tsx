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
  it('GENERAL: devuelve el DTO del servidor e invalida ["stock"] + auditoría (no ["fibra"])', async () => {
    const { wrapper, claves } = setup()
    const out = {
      destino: 'GENERAL',
      modulo: null,
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
    expect(claves()).toEqual(expect.arrayContaining([['stock'], ['auditoria']]))
    expect(claves()).not.toContainEqual(['fibra', 'PAQUETE'])
  })

  it('FO EN_USO: invalida ["fibra","EN_USO"] y no ["stock"]', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(sumarCantidad).mockResolvedValue({} as never)
    const { result } = renderHook(() => useSumarCantidad(), { wrapper })
    await result.current.mutateAsync({
      destino: 'FO',
      modulo: 'EN_USO',
      material_id: 1,
      cantidad: 2,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([['fibra', 'EN_USO'], ['auditoria']]),
    )
    expect(claves()).not.toContainEqual(['stock'])
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
  })
})

describe('useMoverMaterial', () => {
  it('General → FO Paquete: invalida origen Y destino (["stock"] y ["fibra","PAQUETE"])', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(moverMaterial).mockResolvedValue({} as never)
    const { result } = renderHook(() => useMoverMaterial(), { wrapper })
    await result.current.mutateAsync({
      origen: 'GENERAL',
      destino: 'FO',
      destino_modulo: 'PAQUETE',
      material_id: 1,
      cantidad: 3,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([['stock'], ['fibra', 'PAQUETE'], ['auditoria']]),
    )
    expect(claves()).not.toContainEqual(['fibra', 'EN_USO'])
  })

  it('FO Paquete → FO En Uso: ambos módulos, sin ["stock"]', async () => {
    const { wrapper, claves } = setup()
    vi.mocked(moverMaterial).mockResolvedValue({} as never)
    const { result } = renderHook(() => useMoverMaterial(), { wrapper })
    await result.current.mutateAsync({
      origen: 'FO',
      origen_modulo: 'PAQUETE',
      destino: 'FO',
      destino_modulo: 'EN_USO',
      material_id: 1,
      cantidad: 3,
    })
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['fibra', 'PAQUETE'],
        ['fibra', 'EN_USO'],
        ['auditoria'],
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
        origen_modulo: 'EN_USO',
        destino: 'GENERAL',
        material_id: 1,
        cantidad: 1,
      }),
    ).rejects.toThrow('409')
    expect(claves()).toEqual(
      expect.arrayContaining([['fibra', 'EN_USO'], ['stock']]),
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
