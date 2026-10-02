import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SeguimientoCierreForm from '../SeguimientoCierreForm'
import type { SeguimientoItem } from '../../types'

const items: SeguimientoItem[] = [
  {
    id: 1,
    material_id: 10,
    cantidad_tomada: 4,
    cantidad_sobrante: null,
    cantidad_consumida: null,
  },
  {
    id: 2,
    material_id: 20,
    cantidad_tomada: 2,
    cantidad_sobrante: null,
    cantidad_consumida: null,
  },
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

describe('SeguimientoCierreForm render', () => {
  it('renderiza una fila por ítem con descripción, tomada y sobrante default 0', () => {
    renderForm()

    expect(screen.getByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(screen.getByText('Conector RJ45')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()

    const sobrantes = screen.getAllByLabelText(/Sobrante/i)
    expect(sobrantes).toHaveLength(2)
    for (const input of sobrantes) {
      expect(input).toHaveValue(0)
    }
  })
})

describe('SeguimientoCierreForm validación', () => {
  it('sobrante > tomada → error y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    // Fila 1: tomada 4 → sobrante 5 inválido
    const inputs = screen.getAllByLabelText(/Sobrante/i)
    await user.clear(inputs[0])
    await user.type(inputs[0], '5')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByText(/no puede exceder la cantidad tomada/i),
    ).toBeInTheDocument()
  })

  it('submit válido → payload correcto (sobrantes por material + observaciones)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    const inputs = screen.getAllByLabelText(/Sobrante/i)
    await user.clear(inputs[0])
    await user.type(inputs[0], '1')
    await user.clear(inputs[1])
    await user.type(inputs[1], '2')
    await user.type(
      screen.getByLabelText(/Observaciones del cierre/i),
      'Cierre de obra',
    )
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      sobrantes: [
        { material_id: 10, cantidad_sobrante: 1 },
        { material_id: 20, cantidad_sobrante: 2 },
      ],
      observaciones_cierre: 'Cierre de obra',
    })
  })
})
