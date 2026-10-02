import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MaterialDetailDrawer from '../MaterialDetailDrawer'

function renderDrawer(
  props: Partial<React.ComponentProps<typeof MaterialDetailDrawer>> = {},
) {
  return render(
    <MaterialDetailDrawer
      open
      onClose={() => undefined}
      descripcion="ACOPLADORES"
      stockActual={12}
      stockMinimo={1}
      alertaStock={false}
      um="PZ"
      codigo="CON-ACO-001"
      onModificar={() => undefined}
      onEliminar={() => undefined}
      onSumarCantidad={() => undefined}
      onMover={() => undefined}
      {...props}
    />,
  )
}

describe('MaterialDetailDrawer — operaciones junto a Modificar / Eliminar (REQ-P2-INV-005)', () => {
  it('muestra + Cantidad y Mover junto a Modificar y Eliminar', () => {
    renderDrawer()
    for (const nombre of ['+ Cantidad', 'Mover', 'Modificar', 'Eliminar']) {
      expect(screen.getByRole('button', { name: nombre })).toBeInTheDocument()
    }
  })

  it('ordena las operaciones de inventario antes de la gestión del material', () => {
    renderDrawer()
    const nombres = screen
      .getAllByRole('button')
      .map((b) => b.textContent?.trim())
      .filter((t) => ['+ Cantidad', 'Mover', 'Modificar', 'Eliminar'].includes(t ?? ''))
    expect(nombres).toEqual(['+ Cantidad', 'Mover', 'Modificar', 'Eliminar'])
    expect(
      screen.getByRole('group', { name: 'Operaciones de inventario' }),
    ).toContainElement(screen.getByRole('button', { name: 'Mover' }))
    expect(
      screen.getByRole('group', { name: 'Gestión del material' }),
    ).toContainElement(screen.getByRole('button', { name: 'Eliminar' }))
  })

  it('invoca los handlers de cada acción', async () => {
    const user = userEvent.setup()
    const onSumarCantidad = vi.fn()
    const onMover = vi.fn()
    renderDrawer({ onSumarCantidad, onMover })
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    await user.click(screen.getByRole('button', { name: 'Mover' }))
    expect(onSumarCantidad).toHaveBeenCalledTimes(1)
    expect(onMover).toHaveBeenCalledTimes(1)
  })

  it('Mover se deshabilita con motivo si el material no tiene stock; + Cantidad sigue disponible', () => {
    renderDrawer({ stockActual: 0 })
    expect(screen.getByRole('button', { name: 'Mover' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Mover' })).toHaveAttribute(
      'title',
      'Sin stock disponible para mover',
    )
    expect(screen.getByRole('button', { name: '+ Cantidad' })).toBeEnabled()
  })

  it('sin handlers no muestra acciones muertas (retrocompatible)', () => {
    renderDrawer({ onSumarCantidad: undefined, onMover: undefined })
    expect(screen.queryByRole('button', { name: '+ Cantidad' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mover' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Modificar' })).toBeInTheDocument()
  })
})
