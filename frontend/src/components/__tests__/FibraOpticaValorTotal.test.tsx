import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FibraOptica from '../../pages/FibraOptica'
import {
  eliminarFibraMaterial,
  listFibraStock,
  updateFibraMaterial,
} from '../../services/fibra'

// ============================================================================
// T7 (Fase 8) — RF-3 / RF-5 sobre el Inventario FO unificado:
//  · RF-3: tras editar el Valor Unitario con decimales (2.5) la tabla FO
//    muestra `2.50 MXN` al refrescar.
//  · RF-5/RF-4: Modificar y Eliminar un material FO invalidan la clave
//    `['inventario','resumen-general']` (el Valor Total lo calcula el servidor).
// ============================================================================

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))
vi.mock('../../services/catalog', () => ({
  listCatalog: vi.fn().mockResolvedValue({
    start_index: 1,
    materiales: [
      {
        id_lista: 1,
        codigo: 'FO-1',
        descripcion: 'Cable FO',
        categoria_id: 1,
        categoria: 'Fibra',
        u_m: 'PZ',
        stock_minimo: null,
        valor_unitario: 1,
        is_active: true,
      },
    ],
  }),
  listCategorias: vi.fn().mockResolvedValue([{ id: 1, nombre: 'Fibra', is_active: true }]),
  listUms: vi.fn().mockResolvedValue([{ id: 1, nombre: 'PZ', is_active: true }]),
}))
vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({
    data: [
      { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true },
      { almacen_id: 2, nombre: 'Inventario FO', tipo: 'FO', transferible: true },
    ],
  }),
}))
vi.mock('../../services/fibra', () => ({
  listFibraStock: vi.fn(),
  updateFibraMaterial: vi.fn(),
  eliminarFibraMaterial: vi.fn(),
}))

const FILA_FO = {
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: 10,
  valor_unitario: 1,
  alerta_stock: false,
}

function renderPagina() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const spy = vi.spyOn(queryClient, 'invalidateQueries')
  render(
    <QueryClientProvider client={queryClient}>
      <FibraOptica />
    </QueryClientProvider>,
  )
  return spy
}

const CLAVE_RESUMEN = { queryKey: ['inventario', 'resumen-general'] }

describe('Inventario FO — Valor Unitario y refresco del Valor Total (RF-3, RF-5)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listFibraStock).mockResolvedValue([FILA_FO])
    vi.mocked(updateFibraMaterial).mockResolvedValue({
      ...FILA_FO,
      valor_unitario: 2.5,
      categoria: 'Fibra',
      categoria_id: 1,
    })
    vi.mocked(eliminarFibraMaterial).mockResolvedValue(undefined)
  })

  it('RF-3/RF-5: guardar 2.5 invalida resumen-general y la tabla FO muestra 2.50 MXN al refrescar', async () => {
    const user = userEvent.setup()
    const spy = renderPagina()

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])
    await screen.findByRole('heading', { name: 'Modificar Material' })

    vi.mocked(listFibraStock).mockResolvedValue([{ ...FILA_FO, valor_unitario: 2.5 }])
    const valor = screen.getByLabelText('Valor Unitario (MXN)')
    await user.clear(valor)
    await user.type(valor, '2.5')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(updateFibraMaterial).toHaveBeenCalledTimes(1))
    expect(vi.mocked(updateFibraMaterial).mock.calls[0][1].valor_unitario).toBe(2.5)

    await waitFor(() => expect(spy).toHaveBeenCalledWith(CLAVE_RESUMEN))
    await waitFor(() => {
      const fila = within(screen.getByRole('table')).getByText('Cable FO').closest('tr')!
      expect(fila).toHaveTextContent(/2\.50\s*MXN/)
    })
  })

  it('RF-1/RF-10: la página muestra UNA sola tabla «Inventario FO», sin pestañas ni subapartados Paquete/En Uso', async () => {
    renderPagina()

    expect(await screen.findByRole('heading', { name: 'Inventario FO' })).toBeInTheDocument()
    await screen.findAllByText('Cable FO')
    expect(screen.getAllByRole('table')).toHaveLength(1)
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.queryByText(/paquete/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/en uso/i)).not.toBeInTheDocument()
  })

  it('RF-4/RF-5: eliminar un material FO (stock con motivo) invalida resumen-general', async () => {
    const user = userEvent.setup()
    const spy = renderPagina()

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Eliminar' })[0])
    expect(
      await screen.findByRole('heading', { name: 'Eliminar Material' }),
    ).toBeInTheDocument()
    await user.type(
      screen.getByPlaceholderText(/Ej\. Material fuera de uso/),
      'Baja administrativa',
    )
    await user.click(screen.getAllByRole('button', { name: 'Eliminar' }).at(-1)!)

    await waitFor(() => expect(eliminarFibraMaterial).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(spy).toHaveBeenCalledWith(CLAVE_RESUMEN))
  })
})
