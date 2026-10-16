import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import MaterialForm from '../MaterialForm'

const baseMaterial = {
  id_lista: 1,
  codigo: 'SKU-1',
  descripcion: 'Material de prueba',
  u_m: 'PZ',
  stock_minimo: 5,
  valor_unitario: 1,
  categoria_id: 1,
  categoria: 'Cables',
  is_active: true,
}

const mockCategorias = [
  { id: 1, nombre: 'Cables', is_active: true },
  { id: 2, nombre: 'Fibra', is_active: true },
]

describe('MaterialForm STOCK ACTUAL', () => {
  it('renderiza stock actual como solo lectura en modo create', () => {
    render(
      <MaterialForm
        mode="create"
        stockActual={0}
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText(/Solo lectura/i)).toBeInTheDocument()
  })

  it('habilita Stock Actual y Código (SKU) como editables en modo edit', () => {
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    // Stock Actual es un CampoCantidad de texto decimal editable (no un div
    // de solo lectura ni un spinbutton).
    const stockInput = screen.getByLabelText(/Stock Actual/)
    expect(stockInput).toHaveValue('42')
    expect(stockInput).toHaveAttribute('inputmode', 'decimal')
    expect(stockInput).toBeEnabled()
    expect(screen.queryByText(/Solo lectura/i)).not.toBeInTheDocument()

    // Código (SKU) editable en edición
    const codigoInput = screen.getByDisplayValue('SKU-1')
    expect(codigoInput).toBeEnabled()
  })

  it('no incluye stock_actual ni motivo en el payload si el stock no se tocó', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    const payload = onSubmit.mock.calls[0][0]
    expect(payload.stock_actual).toBeUndefined()
    expect(payload.motivo).toBeUndefined()
  })

  it('REQ-ERG-003: editar el stock sin motivo NO bloquea el envío y despacha motivo null', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    const stockInput = screen.getByLabelText(/Stock Actual/)
    await user.clear(stockInput)
    await user.type(stockInput, '60')

    // Al modificar el stock aparece el campo Motivo del ajuste + proyección
    expect(screen.getByPlaceholderText(/Conteo físico/)).toBeInTheDocument()
    expect(screen.getByText(/Proyección visual/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        stock_actual: 60,
        motivo: null,
      }),
    )
  })

  it('envía stock_actual + motivo cuando se edita el stock con motivo válido', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    const stockInput = screen.getByLabelText(/Stock Actual/)
    await user.clear(stockInput)
    await user.type(stockInput, '60')
    await user.type(
      screen.getByPlaceholderText(/Conteo físico/),
      'Conteo físico',
    )

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        stock_actual: 60,
        motivo: 'Conteo físico',
      }),
    )
  })

  it('despacha el código (SKU) editado en el payload de update', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    const codigoInput = screen.getByDisplayValue('SKU-1')
    await user.clear(codigoInput)
    await user.type(codigoInput, 'SKU-2')

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ codigo: 'SKU-2' }),
    )
  })
})

describe('MaterialForm CATEGORÍA DUAL', () => {
  it('renders category selector by default', () => {
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    expect(screen.getByText('Selector')).toBeInTheDocument()
    expect(screen.getAllByRole('combobox')).toHaveLength(2) // U.M. + Categoría
  })

  it('switches to nueva categoria input when radio is selected', async () => {
    const user = userEvent.setup()
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    await user.click(screen.getByText('Nueva categoría'))
    expect(
      screen.getByPlaceholderText('Nombre de la nueva categoría'),
    ).toBeInTheDocument()
  })

  it('includes nueva_categoria in payload when selected', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    // Fill required descripcion field (first textbox)
    const descripcionInput = screen.getAllByRole('textbox')[0]
    await user.type(descripcionInput, 'Producto nuevo')
    await user.click(screen.getByText('Nueva categoría'))
    await user.type(
      screen.getByPlaceholderText('Nombre de la nueva categoría'),
      'Ferretería',
    )
    await user.click(screen.getByRole('button', { name: 'Agregar' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        nueva_categoria: 'Ferretería',
        categoria_id: null,
      }),
    )
  })

  it('precarga y despacha categoria_id en modo edit (selector dual)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    // El selector precarga la categoría actual del material
    const categoriaSelect = screen.getAllByRole('combobox')[1] as HTMLSelectElement
    expect(categoriaSelect.value).toBe('1')

    await user.selectOptions(categoriaSelect, '2')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        categoria_id: 2,
        nueva_categoria: null,
      }),
    )
  })
})

describe('MaterialForm SIN CAMPO TIPO', () => {
  it('does not render TIPO field or selector', () => {
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    // Verify TIPO label doesn't exist
    expect(screen.queryByText('Tipo')).not.toBeInTheDocument()
    // Verify old TIPO options (Fibra Óptica / GENERAL as TIPO values) don't exist
    expect(screen.queryByText('Fibra Óptica')).not.toBeInTheDocument()
  })
})

describe('MaterialForm SECCIÓN DESTINO (fix NIS, REQ-CARGA-001)', () => {
  const seccionesDestino = [
    { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true },
    { almacen_id: 2, nombre: 'Inventario FO', tipo: 'FO', transferible: true },
  ] as import('../../types').SeccionTransferible[]

  it('lista el Inventario FO como destino de Carga Inicial', async () => {
    const user = userEvent.setup()
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        seccionesDestino={seccionesDestino}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )

    // La sección destino solo aparece cuando hay stock inicial > 0.
    expect(screen.queryByText('Inventario FO')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Stock Inicial'), '10')

    expect(screen.getByText('Inventario FO')).toBeInTheDocument()
    expect(screen.getByText('Inventario General')).toBeInTheDocument()
    // No existen módulos FO como opción.
    expect(screen.queryByText(/Paquete/)).not.toBeInTheDocument()
    expect(screen.queryByText(/En Uso/)).not.toBeInTheDocument()
  })
})

describe('MaterialForm VALOR UNITARIO (RF-3, RF-6, RF-8)', () => {
  function renderEdit(
    extra: Partial<ComponentProps<typeof MaterialForm>> = {},
  ) {
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={onSubmit}
        onCancel={() => undefined}
        {...extra}
      />,
    )
    return onSubmit
  }

  it('precarga el Valor Unitario con el valor persistido y label asociado', () => {
    renderEdit()
    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    expect(campo).toHaveAttribute('id', 'material-valor-unitario')
    expect(campo).toHaveValue('1')
    expect(campo).toBeEnabled()
  })

  it('el modo create NO tiene campo Valor Unitario (nace en 1.000)', () => {
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(screen.queryByLabelText(/Valor Unitario/)).not.toBeInTheDocument()
  })

  it('editar el Valor Unitario a 2.5 envía valor_unitario: 2.5 y NO envía stock_actual', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    await user.clear(campo)
    await user.type(campo, '2.5')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]
    expect(payload.valor_unitario).toBe(2.5)
    expect(payload).not.toHaveProperty('stock_actual')
    expect(payload).not.toHaveProperty('motivo')
  })

  it('0 es un Valor Unitario válido y se envía', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    await user.clear(campo)
    await user.type(campo, '0')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0].valor_unitario).toBe(0)
  })

  it('no tocar el Valor Unitario NO lo incluye en el payload', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('valor_unitario')
  })

  it.each(['1.2345', '-1', '1e3', 'abc'])(
    'el Valor Unitario inválido %s bloquea el envío con mensaje en línea',
    async (invalido) => {
      const user = userEvent.setup()
      const onSubmit = renderEdit()

      const campo = screen.getByLabelText('Valor Unitario (MXN)')
      await user.clear(campo)
      await user.type(campo, invalido)
      await user.click(screen.getByRole('button', { name: 'Guardar' }))

      expect(onSubmit).not.toHaveBeenCalled()
      expect(campo).toHaveAttribute('aria-invalid', 'true')
      expect(
        document.getElementById('material-valor-unitario-ayuda'),
      ).toHaveClass('text-red-600')
    },
  )

  it('el mensaje de 1.2345 indica el máximo de 3 decimales', async () => {
    const user = userEvent.setup()
    renderEdit()

    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    await user.clear(campo)
    await user.type(campo, '1.2345')

    expect(
      document.getElementById('material-valor-unitario-ayuda'),
    ).toHaveTextContent(/3 decimales/)
  })

  it('un Valor Unitario vacío bloquea el envío con mensaje en línea', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    await user.clear(screen.getByLabelText('Valor Unitario (MXN)'))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText('Ingresa el Valor Unitario (0 o mayor).'),
    ).toBeInTheDocument()
  })

  it('con esAdmin=false el campo está deshabilitado y valor_unitario nunca viaja', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit({ esAdmin: false })

    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    expect(campo).toBeDisabled()
    expect(campo).toHaveValue('1')

    // Otro campo editado sí viaja; el valor unitario nunca.
    const stock = screen.getByLabelText(/Stock Actual/)
    await user.clear(stock)
    await user.type(stock, '50')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]
    expect(payload).not.toHaveProperty('valor_unitario')
    expect(payload.stock_actual).toBe(50)
  })

  it('editar el stock a 7.25 envía stock_actual: 7.25 (decimal) sin valor_unitario', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    const stock = screen.getByLabelText(/Stock Actual/)
    await user.clear(stock)
    await user.type(stock, '7.25')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]
    expect(payload.stock_actual).toBe(7.25)
    expect(payload).not.toHaveProperty('valor_unitario')
  })

  it('el stock con 4 decimales bloquea el envío con mensaje; 0 es válido', async () => {
    const user = userEvent.setup()
    const onSubmit = renderEdit()

    const stock = screen.getByLabelText(/Stock Actual/)
    await user.clear(stock)
    await user.type(stock, '1.2345')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(stock).toHaveAttribute('aria-invalid', 'true')

    await user.clear(stock)
    await user.type(stock, '0')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0].stock_actual).toBe(0)
  })

  it('el Stock Inicial (create) acepta decimales y los envía como número', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="create"
        categorias={mockCategorias}
        seccionesDestino={[
          { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true },
        ]}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    await user.type(screen.getAllByRole('textbox')[0], 'Producto')
    await user.type(screen.getByLabelText('Stock Inicial'), '2.5')
    // El label «Sección destino» no está asociado al select (sin htmlFor):
    // es el último combobox del formulario.
    await user.selectOptions(screen.getAllByRole('combobox').at(-1)!, '1')
    await user.click(screen.getByRole('button', { name: 'Agregar' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ stock_inicial: 2.5, seccion_id: 1 }),
    )
  })
})
