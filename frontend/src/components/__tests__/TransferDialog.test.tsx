import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransferDialog from '../TransferDialog'

const material = {
  codigo: 'SKU-1',
  descripcion: 'Material de prueba',
  um: 'PZ',
  categoria: 'Cables',
  tipo: 'GENERAL',
  stock_actual: 10,
  stock_minimo: 5,
  alerta_stock: false,
  almacen: 'Almacén Central',
  almacen_id: 'CENTRAL',
}

const warehouses = [
  { id: 'CENTRAL', name: 'Almacén Central', is_active: true },
  { id: 'NORTE', name: 'Almacén Norte', is_active: true },
  { id: 'SUR', name: 'Almacén Sur', is_active: true },
  { id: 'RETIRED', name: 'Almacén Retirado', is_active: false },
]

describe('TransferDialog destination options', () => {
  it('populates options with active warehouses excluding the origin', () => {
    render(
      <TransferDialog
        open
        material={material}
        warehouses={warehouses}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()
    const options = Array.from(select.querySelectorAll('option')).map(
      (o) => o.value,
    )
    expect(options).toContain('NORTE')
    expect(options).toContain('SUR')
    expect(options).not.toContain('CENTRAL')
    expect(options).not.toContain('RETIRED')
  })

  it('keeps the transfer button disabled until a destination is chosen', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <TransferDialog
        open
        material={material}
        warehouses={warehouses}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )
    const button = screen.getByRole('button', { name: 'Transferir' })
    expect(button).toBeDisabled()
    await user.selectOptions(screen.getByRole('combobox'), 'NORTE')
    const quantity = screen.getByRole('spinbutton')
    await user.type(quantity, '3')
    expect(button).toBeEnabled()
    await user.click(button)
    expect(onSubmit).toHaveBeenCalledWith('NORTE', 3)
  })

  it('renders no destination options when only the origin warehouse exists', () => {
    render(
      <TransferDialog
        open
        material={material}
        warehouses={[{ id: 'CENTRAL', name: 'Almacén Central', is_active: true }]}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    )
    const select = screen.getByRole('combobox')
    const options = Array.from(select.querySelectorAll('option')).map(
      (o) => o.value,
    )
    expect(options).toEqual([''])
  })
})
