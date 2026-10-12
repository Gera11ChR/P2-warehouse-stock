import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SeguimientoCierreForm from '../SeguimientoCierreForm'
import type { SeguimientoItem } from '../../types'

// RF-1 / REQ-CONSUMO-001: Consumido vacío y de captura obligatoria.

const items: SeguimientoItem[] = [
  { id: 1, material_id: 10, cantidad_tomada: 4, cantidad_consumida: null },
  { id: 2, material_id: 20, cantidad_tomada: 2, cantidad_consumida: null },
]

const materiales: Record<number, string> = {
  10: 'Cable UTP Cat 6',
  20: 'Conector RJ45',
}

function renderForm(onSubmit = vi.fn()) {
  return render(
    <SeguimientoCierreForm
      items={items}
      materiales={materiales}
      onSubmit={onSubmit}
      onCancel={() => undefined}
    />,
  )
}

const cerrar = () => screen.getByRole('button', { name: 'Cerrar Seguimiento' })

describe('SeguimientoCierreForm render', () => {
  it('REQ-CONSUMO-001: una fila por ítem con tomada y campo Consumido VACÍO', () => {
    const { container } = renderForm()

    expect(screen.getByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(screen.getByText('Conector RJ45')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()

    const campos = screen.getAllByLabelText('Consumido')
    expect(campos).toHaveLength(2)
    for (const input of campos) {
      expect(input).toHaveValue(null) // number vacío
      expect(input).toBeRequired()
    }
    expect(container).not.toHaveTextContent(/sobrante/i)
  })
})

describe('SeguimientoCierreForm validación', () => {
  it('REQ-CONSUMO-001: sin capturar nada no envía y nombra cada material faltante', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.click(cerrar())

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText('Indique la cantidad consumida de Cable UTP Cat 6.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Indique la cantidad consumida de Conector RJ45.'),
    ).toBeInTheDocument()
  })

  it('REQ-CONSUMO-001: con una sola línea capturada sigue sin enviar', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.type(screen.getAllByLabelText('Consumido')[0], '1')
    await user.click(cerrar())

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText('Indique la cantidad consumida de Conector RJ45.'),
    ).toBeInTheDocument()
  })

  it('consumido > tomada → error y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    const inputs = screen.getAllByLabelText('Consumido')
    await user.type(inputs[0], '5') // tomada 4
    await user.type(inputs[1], '1')
    await user.click(cerrar())

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText(/no puede exceder la cantidad tomada/i),
    ).toBeInTheDocument()
  })

  it('0 explícito es una captura válida (no se confunde con vacío)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    const inputs = screen.getAllByLabelText('Consumido')
    await user.type(inputs[0], '0')
    await user.type(inputs[1], '0')
    await user.click(cerrar())

    expect(onSubmit).toHaveBeenCalledWith({
      consumidos: [
        { material_id: 10, cantidad_consumida: 0 },
        { material_id: 20, cantidad_consumida: 0 },
      ],
    })
  })

  it('submit válido → payload { consumidos } + observaciones', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    const inputs = screen.getAllByLabelText('Consumido')
    await user.type(inputs[0], '1')
    await user.type(inputs[1], '2')
    await user.type(
      screen.getByLabelText(/Observaciones del cierre/i),
      'Cierre de obra',
    )
    await user.click(cerrar())

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      consumidos: [
        { material_id: 10, cantidad_consumida: 1 },
        { material_id: 20, cantidad_consumida: 2 },
      ],
      observaciones_cierre: 'Cierre de obra',
    })
  })
})
