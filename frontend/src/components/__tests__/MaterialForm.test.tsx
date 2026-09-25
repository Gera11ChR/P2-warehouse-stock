import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MaterialForm from '../MaterialForm'

const baseMaterial = {
  id_lista: 1,
  codigo: 'SKU-1',
  descripcion: 'Material de prueba',
  u_m: 'PZ',
  stock_minimo: 5,
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

    // Stock Actual ahora es un input numérico editable (no un div de solo lectura)
    const stockInput = screen.getAllByRole('spinbutton')[0]
    expect(stockInput).toHaveValue(42)
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

  it('exige motivo al editar el stock: no llama onSubmit y muestra error', async () => {
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

    const stockInput = screen.getAllByRole('spinbutton')[0]
    await user.clear(stockInput)
    await user.type(stockInput, '60')

    // Al modificar el stock aparece el campo Motivo del ajuste + proyección
    expect(screen.getByPlaceholderText(/Conteo físico/)).toBeInTheDocument()
    expect(screen.getByText(/Proyección visual/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText(/El motivo del ajuste es obligatorio/i),
    ).toBeInTheDocument()
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

    const stockInput = screen.getAllByRole('spinbutton')[0]
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
