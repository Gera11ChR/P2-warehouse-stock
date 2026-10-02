import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SeguimientoNuevaListaForm from '../SeguimientoNuevaListaForm'
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
  props: Partial<ComponentProps<typeof SeguimientoNuevaListaForm>> = {},
) {
  return render(
    <SeguimientoNuevaListaForm
      materiales={materiales}
      onSubmit={onSubmit}
      onCancel={() => undefined}
      {...props}
    />,
  )
}

describe('SeguimientoNuevaListaForm validación', () => {
  it('envío vacío → error de mínimo una línea y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

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
    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

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
    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

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

    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/excede el stock disponible/i)).toBeInTheDocument()
  })
})

describe('SeguimientoNuevaListaForm duplicados', () => {
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

describe('SeguimientoNuevaListaForm estado vacío', () => {
  it('muestra mensaje cuando el equipo no tiene materiales con stock', () => {
    renderForm(vi.fn(), { materiales: [] })

    expect(
      screen.getByText('El equipo no tiene materiales con stock.'),
    ).toBeInTheDocument()
  })
})


describe('SeguimientoNuevaListaForm — «Agregar todo» (REQ-P2-CON-003/004)', () => {
  const agregarTodo = () =>
    screen.getByRole('button', { name: 'Agregar todo' })

  it('se ubica en la cabecera junto al título de la lista', () => {
    renderForm()
    const titulo = screen.getByRole('heading', {
      name: 'Nueva lista de seguimiento',
    })
    expect(titulo.parentElement).toContainElement(agregarTodo())
  })

  it('carga todas las líneas con stock y su stock completo, y lo anuncia', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const onAgregarTodo = vi.fn()
    renderForm(onSubmit, {
      onAgregarTodo,
      materiales: [...materiales, fila({ material_id: 30, stock_actual: 0 })],
    })

    await user.click(agregarTodo())

    expect(screen.getByText('Líneas: 2')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      'Se agregaron 2 materiales con su stock completo',
    )
    expect(onAgregarTodo).toHaveBeenCalledWith(
      expect.objectContaining({ agregadas: 2, yaPresentes: 0 }),
    )

    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))
    expect(onSubmit).toHaveBeenCalledWith({
      items: [
        { material_id: 10, cantidad_tomada: 5 },
        { material_id: 20, cantidad_tomada: 3 },
      ],
    })
  })

  it('con líneas parciales completa solo las faltantes y conserva las cantidades editadas', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.clear(screen.getByLabelText('Cantidad'))
    await user.type(screen.getByLabelText('Cantidad'), '2')

    await user.click(agregarTodo())

    expect(screen.getByText('Líneas: 2')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      'Se agregó 1 material con su stock completo; 1 material ya estaba en la lista y conserva su cantidad',
    )
    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))
    expect(onSubmit).toHaveBeenCalledWith({
      items: [
        { material_id: 10, cantidad_tomada: 2 },
        { material_id: 20, cantidad_tomada: 3 },
      ],
    })
  })

  it('doble clic es idempotente: no duplica líneas y avisa que no hubo cambios', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.dblClick(agregarTodo())

    expect(screen.getByText('Líneas: 2')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      'La lista ya incluye todos los materiales con stock del equipo (2). No se agregó ninguna línea.',
    )
  })

  it('descarta filas vacías al cargar todo (no bloquean el envío)', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    expect(screen.getByText('Líneas: 1')).toBeInTheDocument()

    await user.click(agregarTodo())
    expect(screen.getByText('Líneas: 2')).toBeInTheDocument()
  })

  it('queda deshabilitado con motivo si el equipo no tiene stock', () => {
    renderForm(vi.fn(), {
      materiales: [fila({ material_id: 10, stock_actual: 0 })],
    })
    expect(agregarTodo()).toBeDisabled()
    expect(
      screen.getByText('El equipo no tiene materiales con stock.'),
    ).toBeInTheDocument()
  })

  it('queda deshabilitado si la lista no es editable', async () => {
    const user = userEvent.setup()
    renderForm(vi.fn(), { editable: false })
    expect(agregarTodo()).toBeDisabled()
    expect(screen.getByText('La lista ya no admite cambios.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Agregar línea' })).toBeDisabled()
    await user.click(agregarTodo())
    expect(screen.getByText('Líneas: 0')).toBeInTheDocument()
  })

  it('muestra estado de carga y no precarga mientras el inventario se actualiza', async () => {
    const user = userEvent.setup()
    renderForm(vi.fn(), { isLoading: true })
    expect(agregarTodo()).toBeDisabled()
    expect(agregarTodo()).toHaveAttribute('aria-busy', 'true')
    await user.click(agregarTodo())
    expect(screen.getByText('Líneas: 0')).toBeInTheDocument()
  })
})
