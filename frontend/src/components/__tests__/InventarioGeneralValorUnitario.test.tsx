import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SeccionGeneral from '../../pages/SeccionGeneral'
import { updateMaterial } from '../../services/catalog'
import { getResumenGeneral, stockSeccion } from '../../services/inventory'

// ============================================================================
// T7 (Fase 8) — Trazabilidad RF-3 / RF-5 sobre el Inventario General:
//  · RF-3: la tabla del Inventario General muestra la columna VALOR UNITARIO
//    con la cifra a la izquierda y `MXN` a la derecha; el administrador edita
//    con decimales y, tras refrescar, la tabla muestra `2.50 MXN`.
//  · RF-5 (escenario «Refresco tras editar el valor»): la mutación invalida
//    `['inventario','resumen-general']` y el indicador muestra el nuevo Valor
//    Total proveniente de la API (React nunca lo recalcula).
// ============================================================================

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))
vi.mock('../../hooks/useUms', () => ({
  useUms: () => ({ data: [{ id: 1, nombre: 'PZ', is_active: true }] }),
}))
vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({ data: [] }),
}))
vi.mock('../../hooks/useOperadorRapido', () => ({
  useOperadorRapido: () => ({
    operacion: null,
    cerrar: vi.fn(),
    abrirSumar: vi.fn(),
    abrirMover: vi.fn(),
    sumar: { loading: false },
    mover: { loading: false },
  }),
}))
vi.mock('../../components/CatalogManagementPanel', () => ({
  default: () => <div data-testid="catalog-panel" />,
}))
vi.mock('../../services/catalog', () => ({
  listCategorias: vi.fn().mockResolvedValue([{ id: 1, nombre: 'Fibra', is_active: true }]),
  listCatalog: vi.fn().mockResolvedValue({
    start_index: 1,
    materiales: [
      {
        id_lista: 1,
        codigo: 'GEN-1',
        descripcion: 'Conector SC',
        categoria_id: 1,
        categoria: 'Fibra',
        u_m: 'PZ',
        stock_minimo: null,
        valor_unitario: 1,
        is_active: true,
      },
    ],
  }),
  createMaterial: vi.fn(),
  updateMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
}))
vi.mock('../../services/inventory', () => ({
  listSecciones: vi
    .fn()
    .mockResolvedValue([
      { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', is_active: true },
    ]),
  stockSeccion: vi.fn(),
  getResumenGeneral: vi.fn(),
}))

const FILA = {
  material_id: 1,
  codigo: 'GEN-1',
  descripcion: 'Conector SC',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: 4,
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
      <SeccionGeneral globalSearch="" />
    </QueryClientProvider>,
  )
  return { queryClient, spy }
}

describe('Inventario General — Valor Unitario (RF-3) y refresco del Valor Total (RF-5)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(stockSeccion).mockResolvedValue([FILA])
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 4, moneda: 'MXN' })
    vi.mocked(updateMaterial).mockResolvedValue({
      id_lista: 1,
      codigo: 'GEN-1',
      descripcion: 'Conector SC',
      categoria_id: 1,
      categoria: 'Fibra',
      u_m: 'PZ',
      stock_minimo: null,
      valor_unitario: 2.5,
      is_active: true,
    })
  })

  it('RF-3: la tabla del Inventario General muestra VALOR UNITARIO con la cifra y MXN a su derecha', async () => {
    vi.mocked(stockSeccion).mockResolvedValue([
      FILA,
      { ...FILA, material_id: 2, codigo: 'GEN-2', descripcion: 'Pigtail', valor_unitario: 12.345 },
    ])
    renderPagina()

    const fila1 = (await screen.findByText('Conector SC')).closest('tr')!
    const fila2 = (await screen.findByText('Pigtail')).closest('tr')!
    expect(
      screen.getByRole('columnheader', { name: 'Valor Unitario' }),
    ).toBeInTheDocument()
    expect(fila1).toHaveTextContent(/1\.00\s*MXN/)
    expect(fila2).toHaveTextContent(/12\.345\s*MXN/)
    // Solo presentación: la celda no es un control editable.
    expect(within(fila1).queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(within(fila1).queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('RF-3/RF-5: guardar 2.5 en Modificar Material envía valor_unitario: 2.5, invalida resumen-general y la tabla y el indicador muestran lo persistido', async () => {
    const user = userEvent.setup()
    const { spy } = renderPagina()

    await user.click(await screen.findByText('Conector SC'))
    await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])
    await screen.findByRole('heading', { name: 'Modificar Material' })

    // Precarga con el valor actual.
    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    expect(campo).toHaveValue('1')

    // Tras guardar, el servidor devuelve el estado persistido nuevo.
    vi.mocked(stockSeccion).mockResolvedValue([{ ...FILA, valor_unitario: 2.5 }])
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 10, moneda: 'MXN' })

    await user.clear(campo)
    await user.type(campo, '2.5')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(updateMaterial).toHaveBeenCalledTimes(1))
    const [id, payload] = vi.mocked(updateMaterial).mock.calls[0]
    expect(id).toBe(1)
    expect(payload.valor_unitario).toBe(2.5)

    // RF-5: se invalida la clave contractual del Valor Total.
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({
        queryKey: ['inventario', 'resumen-general'],
      }),
    )

    // RF-3: la tabla muestra `2.50 MXN` tras refrescar.
    await waitFor(() => {
      const fila = within(screen.getByRole('table')).getByText('Conector SC').closest('tr')!
      expect(fila).toHaveTextContent(/2\.50\s*MXN/)
    })
    // RF-5: el indicador muestra el Valor Total que entrega la API (10), sin recalcular.
    await waitFor(() =>
      expect(screen.getByTestId('valor-total')).toHaveTextContent('10.00'),
    )
    expect(getResumenGeneral).toHaveBeenCalledTimes(2)
  })
})
