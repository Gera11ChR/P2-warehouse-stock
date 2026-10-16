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
        valor_unitario: 1,
        is_active: true,
      },
    ],
  }),
  listCategorias: vi.fn().mockResolvedValue([
    { id: 1, nombre: 'Fibra', is_active: true },
  ]),
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

const MATERIAL_EDITADO = {
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: 10,
  valor_unitario: 1,
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
      <FibraOptica />
    </QueryClientProvider>,
  )
  return queryClient
}

describe('FibraOptica — CRUD FO (REQ-CRUD-001/002, REQ-TRF-INV-002)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([
      FILA_FO,
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
          valor_unitario: 1,
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

  it('REQ-CATFO-001/REQ-TRF-INV-002: Modificar guarda vía updateFibraMaterial e invalida ["fibra"]', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    render(
      <QueryClientProvider client={queryClient}>
        <FibraOptica />
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
        1,
        expect.objectContaining({ descripcion: 'Cable FO' }),
      )
    })
    // REQ-TRF-INV-002: la mutación invalida la clave única del Inventario FO y el
    // join de presentación (catálogo + categorías).
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['fibra'],
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['catalogo'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['categorias'] })
  })

  it('REQ-ERG-004: cambiar Stock Actual sin motivo NO bloquea y llama updateFibraMaterial con motivo null', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])

    // Stock Actual precargado con el valor registrado (10).
    const stockInput = await screen.findByLabelText('Stock Actual')
    expect(stockInput).toHaveValue('10')
    await user.clear(stockInput)
    await user.type(stockInput, '25')

    // Al modificar el stock aparece el campo opcional del motivo.
    expect(
      screen.getByPlaceholderText(/Conteo físico/),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() => {
      expect(updateFibraMaterial).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ stock_actual: 25, motivo: null }),
      )
    })
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
        1,
        'Baja administrativa',
      )
    })
    // REQ-TRF-INV-002 + traza forense: invalida el Inventario FO y la
    // vista de auditoría (evento ELIMINACION_FO).
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['fibra'],
      })
    })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['auditoria'] })
  })

  it('REQ-P2-INV-005: el drawer FO ofrece + Cantidad y Mover junto a Modificar / Eliminar', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    await user.click(await screen.findByText('Cable FO'))

    expect(await screen.findByRole('button', { name: '+ Cantidad' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mover' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Modificar' }).length).toBeGreaterThan(0)
  })

  it('+ Cantidad abre el diálogo con el inventario FO de origen y Esc devuelve el foco', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    await user.click(await screen.findByText('Cable FO'))
    const boton = await screen.findByRole('button', { name: '+ Cantidad' })
    await user.click(boton)

    const dialogo = screen.getByRole('dialog', { name: '+ Cantidad' })
    expect(dialogo).toHaveTextContent('Inventario FO')
    expect(dialogo).toHaveTextContent('FO-1')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(boton).toHaveFocus()
  })

  it('Mover ofrece como destino los demás inventarios (sin el origen Inventario FO)', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    await user.click(await screen.findByText('Cable FO'))
    await user.click(await screen.findByRole('button', { name: 'Mover' }))

    const select = screen.getByLabelText('Inventario destino')
    const opciones = Array.from(select.querySelectorAll('option')).map(
      (o) => o.textContent,
    )
    expect(opciones).toEqual([
      '— Selecciona destino —',
      'Inventario General',
    ])
  })

  it('RF-3: la tabla única muestra el título Inventario FO y la columna Valor Unitario con cifra y MXN', async () => {
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([
      { ...FILA_FO, valor_unitario: 12.345 },
    ])
    renderConQueryClient()

    expect(
      await screen.findByRole('heading', { name: 'Inventario FO' }),
    ).toBeInTheDocument()
    const fila = (await screen.findByText('Cable FO')).closest('tr')!
    expect(
      screen.getByRole('columnheader', { name: 'Valor Unitario' }),
    ).toBeInTheDocument()
    expect(fila).toHaveTextContent('12.345')
    expect(fila).toHaveTextContent('MXN')
    expect(listFibraStock).toHaveBeenCalled()
  })

  it('RF-3: un valor entero se presenta con dos decimales (1 → 1.00 MXN)', async () => {
    renderConQueryClient()

    const fila = (await screen.findByText('Cable FO')).closest('tr')!
    expect(fila).toHaveTextContent(/1\.00\s*MXN/)
  })

  it('estado vacío: «Sin materiales en el Inventario FO.»', async () => {
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([])
    renderConQueryClient()

    expect(
      await screen.findByText('Sin materiales en el Inventario FO.'),
    ).toBeInTheDocument()
  })

  it('error de carga: «No se pudo obtener el Inventario FO…»', async () => {
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('boom'),
    )
    renderConQueryClient()

    expect(
      await screen.findByText(/No se pudo obtener el Inventario FO/),
    ).toBeInTheDocument()
  })

  describe('Valor Unitario y Stock decimal en Modificar (RF-3/RF-6/RF-8)', () => {
    async function abrirModificar() {
      const user = userEvent.setup()
      renderConQueryClient()
      await user.click(await screen.findByText('Cable FO'))
      await user.click(screen.getAllByRole('button', { name: 'Modificar' })[0])
      await screen.findByRole('heading', { name: 'Modificar Material' })
      return user
    }

    it('precarga el Valor Unitario con el valor persistido', async () => {
      await abrirModificar()
      expect(screen.getByLabelText('Valor Unitario (MXN)')).toHaveValue('1')
    })

    it('editar el Valor Unitario a 2.5 envía valor_unitario: 2.5 y NO stock_actual', async () => {
      const user = await abrirModificar()

      const valor = screen.getByLabelText('Valor Unitario (MXN)')
      await user.clear(valor)
      await user.type(valor, '2.5')
      await user.click(screen.getByRole('button', { name: 'Guardar' }))

      await waitFor(() => {
        expect(updateFibraMaterial).toHaveBeenCalledTimes(1)
      })
      const [id, payload] = (updateFibraMaterial as ReturnType<typeof vi.fn>)
        .mock.calls[0]
      expect(id).toBe(1)
      expect(payload.valor_unitario).toBe(2.5)
      expect(payload).not.toHaveProperty('stock_actual')
    })

    it('no tocar el Valor Unitario NO lo incluye en el payload', async () => {
      const user = await abrirModificar()

      await user.click(screen.getByRole('button', { name: 'Guardar' }))

      await waitFor(() => {
        expect(updateFibraMaterial).toHaveBeenCalledTimes(1)
      })
      const [, payload] = (updateFibraMaterial as ReturnType<typeof vi.fn>).mock
        .calls[0]
      expect(payload).not.toHaveProperty('valor_unitario')
      expect(payload).not.toHaveProperty('stock_actual')
    })

    it('un Valor Unitario con 4 decimales (1.2345) bloquea el envío con mensaje', async () => {
      const user = await abrirModificar()

      const valor = screen.getByLabelText('Valor Unitario (MXN)')
      await user.clear(valor)
      await user.type(valor, '1.2345')
      await user.click(screen.getByRole('button', { name: 'Guardar' }))

      expect(updateFibraMaterial).not.toHaveBeenCalled()
      expect(valor).toHaveAttribute('aria-invalid', 'true')
      expect(
        document.getElementById('fibra-valor-unitario-ayuda'),
      ).toHaveTextContent(/3 decimales/)
    })

    it('editar el stock a 7.25 envía stock_actual: 7.25', async () => {
      const user = await abrirModificar()

      const stock = screen.getByLabelText('Stock Actual')
      await user.clear(stock)
      await user.type(stock, '7.25')
      await user.click(screen.getByRole('button', { name: 'Guardar' }))

      await waitFor(() => {
        expect(updateFibraMaterial).toHaveBeenCalledTimes(1)
      })
      const [, payload] = (updateFibraMaterial as ReturnType<typeof vi.fn>).mock
        .calls[0]
      expect(payload.stock_actual).toBe(7.25)
      expect(payload).not.toHaveProperty('valor_unitario')
    })
  })
})
