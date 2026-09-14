import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MaterialForm from '../MaterialForm'

const baseMaterial = {
  codigo: 'SKU-1',
  descripcion: 'Material de prueba',
  um: 'PZ',
  stock_minimo: 5,
  categoria: 'Cables',
  tipo: 'GENERAL',
}

describe('MaterialForm STOCK ACTUAL', () => {
  it('renders an editable number input in edit mode', () => {
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        almacenId="DW-1"
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const input = screen.getByLabelText('Stock Actual')
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe('INPUT')
    expect(input).toHaveValue(42)
  })

  it('includes on_hand_quantity and warehouse_id in payload when stock changes', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        almacenId="DW-1"
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )
    const input = screen.getByLabelText('Stock Actual')
    await user.clear(input)
    await user.type(input, '57')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        on_hand_quantity: 57,
        warehouse_id: 'DW-1',
      }),
    )
  })

  it('omits on_hand_quantity from payload when stock is unchanged', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={42}
        almacenId="DW-1"
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    const payload = onSubmit.mock.calls[0][0]
    expect(payload.on_hand_quantity).toBeUndefined()
    expect(payload.warehouse_id).toBeUndefined()
  })

  it('renders a read-only stock display in create mode', () => {
    render(
      <MaterialForm
        mode="create"
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const input = screen.queryByLabelText('Stock Actual')
    expect(input).toBeNull()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('rejects negative values via the min attribute', () => {
    render(
      <MaterialForm
        mode="edit"
        initial={baseMaterial}
        stockActual={10}
        almacenId="DW-1"
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const input = screen.getByLabelText('Stock Actual')
    expect(input).toHaveAttribute('min', '0')
  })
})
