import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfigLocalForm from '../ConfigLocalForm'
import type { Categoria, InventarioEquipoRow, Ums } from '../../types'

const material: InventarioEquipoRow = {
  equipo_id: 1,
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  stock_minimo: 5,
  stock_actual: 42,
  alerta_stock: false,
  ultimo_movimiento_id: 7,
  stock_minimo_local: null,
  categoria_local_id: null,
  um_local_id: null,
  stock_minimo_efectivo: 5,
  categoria_efectiva: 'Cables',
  um_efectivo: 'METRO (M)',
}

const categorias: Categoria[] = [
  { id: 1, nombre: 'Cables', is_active: true },
  { id: 2, nombre: 'Antiguos', is_active: false },
]

const ums: Ums[] = [
  { id: 11, nombre: 'METRO (M)', is_active: true },
  { id: 12, nombre: 'PZ', is_active: true },
  { id: 13, nombre: 'ROLLO', is_active: false },
]

function renderForm(onSubmit = vi.fn()) {
  return render(
    <ConfigLocalForm
      material={material}
      categorias={categorias}
      ums={ums}
      onSubmit={onSubmit}
      onCancel={() => undefined}
    />,
  )
}

describe('ConfigLocalForm SOLO LECTURA (REQ-TEAM-001/002)', () => {
  it('renderiza código, descripción y stock actual como solo lectura', () => {
    renderForm()

    expect(screen.getByText('CBL-001')).toBeInTheDocument()
    expect(screen.getByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(screen.getByText(/42/)).toBeInTheDocument()

    // Stock actual NO es un input editable: el único spinbutton es
    // el de Stock Mínimo Local.
    expect(screen.getAllByRole('spinbutton')).toHaveLength(1)
    expect(screen.getByLabelText(/Stock Mínimo Local/i)).toBeEnabled()
  })
})

describe('ConfigLocalForm validación', () => {
  it('envío vacío → error "al menos un campo" y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/al menos un campo/i)).toBeInTheDocument()
  })

  it('stock mínimo negativo → error', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    const stockInput = screen.getByLabelText(/Stock Mínimo Local/i)
    await user.type(stockInput, '-5')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText(/mayor o igual a 0/i),
    ).toBeInTheDocument()
  })

  it('envío válido → onSubmit con payload EXACTO (solo campos editados)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.type(screen.getByLabelText(/Stock Mínimo Local/i), '10')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({ stock_minimo_local: 10 })
  })

  it('incluye categoría y U.M. cuando se seleccionan (campos vacíos omitidos)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.selectOptions(screen.getByLabelText(/Categoría Local/i), '1')
    await user.selectOptions(screen.getByLabelText(/U\.M\. Local/i), '12')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledWith({
      categoria_local_id: 1,
      um_local_id: 12,
    })
  })
})

describe('ConfigLocalForm selectores', () => {
  it('renderiza solo categorías ACTIVAS', () => {
    renderForm()

    const categoriaSelect = screen.getByLabelText(/Categoría Local/i)
    expect(within(categoriaSelect).getByText('Cables')).toBeInTheDocument()
    expect(
      within(categoriaSelect).queryByText('Antiguos'),
    ).not.toBeInTheDocument()
    expect(
      within(categoriaSelect).getByText('Heredar del catálogo'),
    ).toBeInTheDocument()
  })

  it('renderiza solo U.M. ACTIVAS', () => {
    renderForm()

    const umSelect = screen.getByLabelText(/U\.M\. Local/i)
    expect(within(umSelect).getByText('METRO (M)')).toBeInTheDocument()
    expect(within(umSelect).getByText('PZ')).toBeInTheDocument()
    expect(within(umSelect).queryByText('ROLLO')).not.toBeInTheDocument()
  })
})
