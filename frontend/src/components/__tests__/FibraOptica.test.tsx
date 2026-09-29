import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FibraOptica from '../../pages/FibraOptica'
import {
  eliminarFibraMaterial,
  listFibraStock,
  updateFibraMaterial,
} from '../../services/fibra'
import { listCatalog, listCategorias, listUms } from '../../services/catalog'

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
        is_active: true,
      },
    ],
  }),
  listCategorias: vi.fn().mockResolvedValue([
    { id: 1, nombre: 'Fibra', is_active: true },
  ]),
  listUms: vi.fn().mockResolvedValue([{ id: 1, nombre: 'PZ', is_active: true }]),
}))

vi.mock('../../services/fibra', () => ({
  listFibraStock: vi.fn(),
  updateFibraMaterial: vi.fn(),
  eliminarFibraMaterial: vi.fn(),
}))

const FILA_PAQUETE = {
  modulo: 'PAQUETE',
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: 10,
  alerta_stock: false,
}

const MATERIAL_EDITADO = {
  modulo: 'PAQUETE',
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: 10,
  alerta_stock: false,
  categoria: 'Fibra',
  categoria_id: 1,
}

function renderConQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <FibraOptica sub="paquete" />
    </QueryClientProvider>,
  )
  return queryClient
}

describe('FibraOptica — CRUD FO (REQ-CRUD-001/002, REQ-TRF-INV-002)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([
      FILA_PAQUETE,
    ])
    ;(updateFibraMaterial as ReturnType<typeof vi.fn>).mockResolvedValue(
      MATERIAL_EDITADO,
    )
    ;(eliminarFibraMaterial as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    )
    ;(listCatalog as ReturnType<typeof vi.fn>).mockResolvedValue({
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
          is_active: true,
        },
      ],
    })
    ;(listCategorias as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 1, nombre: 'Fibra', is_active: true },
    ])
    ;(listUms as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 1, nombre: 'PZ', is_active: true },
    ])
  })

  it('REQ-CRUD-001: al seleccionar una fila aparecen Ver Detalle / Modificar / Eliminar y el drawer', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    // Sin selección no hay barra de acciones.
    expect(
      screen.queryByRole('button', { name: 'Ver Detalle' }),
    ).not.toBeInTheDocument()

    await user.click(await screen.findByText('Cable FO'))

    expect(
      await screen.findByRole('button', { name: 'Ver Detalle' }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: 'Modificar' }).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByRole('button', { name: 'Eliminar' }).length,
    ).toBeGreaterThan(0)

    // El drawer se abre con la selección (REQ-CRUD-002: detalle de lectura).
    expect(screen.getByText('Detalle del Material')).toBeInTheDocument()
    expect(screen.getAllByText('FO-1').length).toBeGreaterThan(0)
  })

  it('REQ-CATFO-001/REQ-TRF-INV-002: Modificar guarda vía updateFibraMaterial e invalida ["fibra", modulo]', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    render(
      <QueryClientProvider client={queryClient}>
        <FibraOptica sub="paquete" />
      </QueryClientProvider>,
    )

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])

    // El modal abre el FibraMaterialForm precargado con la fila seleccionada.
    expect(
      await screen.findByRole('heading', { name: 'Modificar Material' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => {
      expect(updateFibraMaterial).toHaveBeenCalledWith(
        'PAQUETE',
        1,
        expect.objectContaining({ descripcion: 'Cable FO' }),
      )
    })
    // REQ-TRF-INV-002: la mutación invalida la clave del módulo FO y el
    // join de presentación (catálogo + categorías).
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['fibra', 'PAQUETE'],
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['catalogo'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['categorias'] })
  })

  it('REQ-STOCK-001: cambiar Stock Actual sin motivo muestra el error y NO llama updateFibraMaterial', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])

    // Stock Actual precargado con el valor registrado (10).
    const stockInput = await screen.findByDisplayValue('10')
    await user.clear(stockInput)
    await user.type(stockInput, '25')

    // Al modificar el stock aparece el motivo obligatorio del ajuste.
    expect(
      screen.getByPlaceholderText(/Conteo físico/),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(
      screen.getByText(/El motivo del ajuste es obligatorio/i),
    ).toBeInTheDocument()
    expect(updateFibraMaterial).not.toHaveBeenCalled()
  })

  it('REQ-DEL-004/REQ-TRF-INV-002: eliminar con stock exige motivo; con motivo llama eliminarFibraMaterial e invalida', async () => {
    const user = userEvent.setup()
    const queryClient = renderConQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Eliminar' })[0])

    // Stock 10 > 0 → Modal de eliminación con textarea de motivo.
    expect(
      await screen.findByRole('heading', { name: 'Eliminar Material' }),
    ).toBeInTheDocument()
    const motivoTextarea = screen.getByPlaceholderText(
      /Ej\. Material fuera de uso/,
    )

    // El confirm del modal es el ÚLTIMO botón "Eliminar" del árbol
    // (barra de acciones → drawer → modal).
    const confirmEliminar = () =>
      screen.getAllByRole('button', { name: 'Eliminar' }).at(-1)!

    // Sin motivo: error local y NINGUNA llamada al servicio.
    await user.click(confirmEliminar())
    expect(
      await screen.findByText(/El motivo de la eliminación es obligatorio/),
    ).toBeInTheDocument()
    expect(eliminarFibraMaterial).not.toHaveBeenCalled()

    await user.type(motivoTextarea, 'Baja administrativa')
    await user.click(confirmEliminar())

    await waitFor(() => {
      expect(eliminarFibraMaterial).toHaveBeenCalledWith(
        'PAQUETE',
        1,
        'Baja administrativa',
      )
    })
    // REQ-TRF-INV-002 + traza forense: invalida el stock del módulo y la
    // vista de auditoría (evento ELIMINACION_FO).
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['fibra', 'PAQUETE'],
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['auditoria'] })
  })
})
