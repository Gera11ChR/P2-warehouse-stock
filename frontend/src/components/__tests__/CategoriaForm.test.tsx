import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CategoriaForm from '../CategoriaForm'

const initial = { id: 1, nombre: 'Cables' }

function renderForm(onSubmit = vi.fn()) {
  return render(
    <CategoriaForm
      titulo="Renombrar categoría"
      labelNombre="Nombre de la categoría"
      initial={initial}
      onSubmit={onSubmit}
      onCancel={() => undefined}
    />,
  )
}

describe('CategoriaForm', () => {
  it('precarga el nombre actual', () => {
    renderForm()
    expect(screen.getByDisplayValue('Cables')).toBeInTheDocument()
  })

  it('nombre vacío → error y no llama onSubmit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.clear(screen.getByDisplayValue('Cables'))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/El nombre es obligatorio/i)).toBeInTheDocument()
  })

  it('submit válido → onSubmit con { nombre }', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderForm(onSubmit)

    await user.clear(screen.getByDisplayValue('Cables'))
    await user.type(screen.getByLabelText(/Nombre de la categoría/i), 'Ferretería')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({ nombre: 'Ferretería' })
  })
})
