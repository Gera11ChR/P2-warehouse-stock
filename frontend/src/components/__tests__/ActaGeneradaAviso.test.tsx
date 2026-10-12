import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ActaGeneradaAviso from '../ActaGeneradaAviso'

describe('ActaGeneradaAviso', () => {
  it('Entrega: anuncia el acta (role=status) con el equipo y la acción hacia Reportes > Entrega', async () => {
    const user = userEvent.setup()
    const onVerActa = vi.fn()
    render(
      <ActaGeneradaAviso
        tipo="ENTREGA"
        equipoNombre="PARTNER 2017"
        onVerActa={onVerActa}
        onDismiss={() => undefined}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Acta de Entrega generada')
    expect(screen.getByRole('status')).toHaveTextContent(
      'movimiento TEAMS hacia PARTNER 2017 fue CONFIRMADO por el servidor',
    )
    await user.click(screen.getByRole('button', { name: 'Ir a Reportes > Entrega' }))
    expect(onVerActa).toHaveBeenCalledTimes(1)
  })

  it('Consumo: copy propio y acción hacia Reportes > Consumo', () => {
    render(
      <ActaGeneradaAviso
        tipo="CONSUMO"
        equipoNombre="PARTNER 2017"
        onVerActa={() => undefined}
        onDismiss={() => undefined}
      />,
    )
    expect(screen.getByText('Acta de Consumo generada')).toBeInTheDocument()
    expect(screen.getByText(/seguimiento de la unidad PARTNER 2017 fue cerrado/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ir a Reportes > Consumo' }),
    ).toBeInTheDocument()
  })

  it('sin handler no muestra acción y se puede descartar', async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<ActaGeneradaAviso tipo="ENTREGA" onDismiss={onDismiss} />)
    expect(screen.queryByRole('button', { name: /Ir a Reportes/ })).not.toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Cerrar aviso de Acta de Entrega generada' }),
    )
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })
})
