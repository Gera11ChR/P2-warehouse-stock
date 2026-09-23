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
  it('renders stock actual as read-only in both create and edit modes', () => {
    const { rerender } = render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText(/Solo lectura/i)).toBeInTheDocument()
    
    rerender(
      <MaterialForm
        mode="create"
        stockActual={0}
        categorias={mockCategorias}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('does not include stock fields in payload (read-only)', async () => {
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
    expect(payload.on_hand_quantity).toBeUndefined()
    expect(payload.stock_actual).toBeUndefined()
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
