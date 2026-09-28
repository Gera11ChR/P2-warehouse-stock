import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DespliegueNuevaListaForm from '../DespliegueNuevaListaForm'
import type { InventarioEquipoRow } from '../../types'

function fila(overrides: Partial<InventarioEquipoRow>): InventarioEquipoRow {
  return {
    equipo_id: 1,
    material_id: 10,
    codigo: 'CBL-001',
    descripcion: 'Cable UTP Cat 6',
    u_m: 'METRO (M)',
    stock_minimo: 5,
    stock_actual: 5,
    alerta_stock: false,
    ultimo_movimiento_id: null,
    stock_minimo_local: null,
    categoria_local_id: null,
    um_local_id: null,
    stock_minimo_efectivo: 5,
    categoria_efectiva: 'Cables',
    um_efectivo: 'METRO (M)',
    ...overrides,
  }
}

const materiales: InventarioEquipoRow[] = [
  fila({ material_id: 10, descripcion: 'Cable UTP Cat 6', stock_actual: 5 }),
  fila({ material_id: 20, descripcion: 'Conector RJ45', stock_actual: 3 }),
]

function renderForm(
  onSubmit = vi.fn(),
  props: Partial<{ materiales: InventarioEquipoRow[] }> = {},
) {
  return render(
    <DespliegueNuevaListaForm
      materiales={props.materiales ?? materiales}
      onSubmit={onSubmit}
      onCancel={() => undefined}
    />,
  )
}

describe('DespliegueNuevaListaForm validación', () => {
  it('envío vacío → error de mínimo una línea y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Crear Despliegue' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(
      /al menos una línea/i,
    )
  })

  it('agregar línea + submit → payload items correcto (default cantidad 1)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.click(screen.getByRole('button', { name: 'Crear Despliegue' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      items: [{ material_id: 10, cantidad_tomada: 1 }],
    })
  })

  it('incluye observaciones en el payload solo cuando se escribe', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.type(screen.getByLabelText(/Observaciones/i), 'Obra zona norte')
    await user.click(screen.getByRole('button', { name: 'Crear Despliegue' }))

    expect(onSubmit).toHaveBeenCalledWith({
      items: [{ material_id: 10, cantidad_tomada: 1 }],
      observaciones: 'Obra zona norte',
    })
  })

  it('cantidad > stock → guardia de presentación y NO llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10') // stock 5
    await user.clear(screen.getByLabelText(/Cantidad/i))
    await user.type(screen.getByLabelText(/Cantidad/i), '99')

    expect(screen.getByText(/Máx\. 5/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Crear Despliegue' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/excede el stock disponible/i)).toBeInTheDocument()
  })
})

describe('DespliegueNuevaListaForm duplicados', () => {
  it('deshabilita el material ya usado en otra línea', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))

    const selects = screen.getAllByRole('combobox')
    await user.selectOptions(selects[0], '10')

    const opcionEnSegundaLinea = within(selects[1]).getByRole('option', {
      name: /Cable UTP Cat 6/,
    })
    expect(opcionEnSegundaLinea).toBeDisabled()

    const opcionLibre = within(selects[1]).getByRole('option', {
      name: /Conector RJ45/,
    })
    expect(opcionLibre).toBeEnabled()
  })
})

describe('DespliegueNuevaListaForm estado vacío', () => {
  it('muestra mensaje cuando el equipo no tiene materiales con stock', () => {
    renderForm(vi.fn(), { materiales: [] })

    expect(
      screen.getByText('El equipo no tiene materiales con stock.'),
    ).toBeInTheDocument()
  })
})
