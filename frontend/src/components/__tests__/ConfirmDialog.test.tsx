import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfirmDialog from '../ConfirmDialog'

// REQ-REF-016 (hallazgo F-1 de T11): las confirmaciones exponen
// role="dialog" + aria-modal con nombre y descripción, y gestionan el foco:
// foco inicial en «Cancelar», Tab atrapado, Esc cancela y el foco vuelve al
// elemento que abrió el diálogo. Componente compartido: el comportamiento
// existente (open/title/message/confirmLabel/onConfirm/onCancel) se conserva.

function Arnes({
  onConfirm = vi.fn(),
  onCancel = vi.fn(),
  confirmLabel,
}: {
  onConfirm?: () => void
  onCancel?: () => void
  confirmLabel?: string
}) {
  const [abierto, setAbierto] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setAbierto(true)}>
        Abrir
      </button>
      <ConfirmDialog
        open={abierto}
        title="Eliminar de la Referencia"
        message="¿Seguro que deseas quitar este material?"
        confirmLabel={confirmLabel}
        onConfirm={() => {
          onConfirm()
          setAbierto(false)
        }}
        onCancel={() => {
          onCancel()
          setAbierto(false)
        }}
      />
    </>
  )
}

describe('ConfirmDialog — atributos de accesibilidad', () => {
  it('cerrado: no renderiza nada', () => {
    render(
      <ConfirmDialog
        open={false}
        title="T"
        message="M"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('abierto: role="dialog", aria-modal="true", con nombre y descripción', async () => {
    const user = userEvent.setup()
    render(<Arnes />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))

    const dialogo = screen.getByRole('dialog', {
      name: 'Eliminar de la Referencia',
    })
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(dialogo).toHaveAccessibleDescription(
      '¿Seguro que deseas quitar este material?',
    )
    // El nombre y la descripción apuntan a elementos existentes del diálogo.
    const labelledby = dialogo.getAttribute('aria-labelledby')!
    const describedby = dialogo.getAttribute('aria-describedby')!
    expect(document.getElementById(labelledby)).toHaveTextContent(
      'Eliminar de la Referencia',
    )
    expect(document.getElementById(describedby)).toHaveTextContent(
      '¿Seguro que deseas quitar este material?',
    )
  })

  it('conserva la etiqueta de confirmación por defecto y la personalizada', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<Arnes />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    expect(screen.getByRole('button', { name: 'Eliminar' })).toBeInTheDocument()
    unmount()

    render(<Arnes confirmLabel="Confirmar" />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    expect(
      screen.getByRole('button', { name: 'Confirmar' }),
    ).toBeInTheDocument()
  })
})

describe('ConfirmDialog — gestión de foco', () => {
  it('al abrir, el foco pasa a «Cancelar» (opción segura)', async () => {
    const user = userEvent.setup()
    render(<Arnes />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus()
  })

  it('Tab y Shift+Tab quedan atrapados dentro del diálogo', async () => {
    const user = userEvent.setup()
    render(<Arnes />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    const cancelar = screen.getByRole('button', { name: 'Cancelar' })
    const confirmar = screen.getByRole('button', { name: 'Eliminar' })

    await user.tab()
    expect(confirmar).toHaveFocus()
    await user.tab() // desde el último vuelve al primero
    expect(cancelar).toHaveFocus()
    await user.tab({ shift: true }) // desde el primero va al último
    expect(confirmar).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Abrir' })).not.toHaveFocus()
  })

  it('Esc cancela sin confirmar y devuelve el foco al elemento que abrió', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(<Arnes onCancel={onCancel} onConfirm={onConfirm} />)
    const abrir = screen.getByRole('button', { name: 'Abrir' })
    await user.click(abrir)

    await user.keyboard('{Escape}')

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(abrir).toHaveFocus()
  })

  it('«Cancelar» y «Eliminar» invocan su manejador y devuelven el foco', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(<Arnes onCancel={onCancel} onConfirm={onConfirm} />)
    const abrir = screen.getByRole('button', { name: 'Abrir' })

    await user.click(abrir)
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(abrir).toHaveFocus()

    await user.click(abrir)
    await user.click(screen.getByRole('button', { name: 'Eliminar' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(abrir).toHaveFocus()
  })

  it('Enter con el foco inicial NO confirma la acción destructiva', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<Arnes onConfirm={onConfirm} onCancel={onCancel} />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    await user.keyboard('{Enter}')
    expect(onConfirm).not.toHaveBeenCalled()
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
