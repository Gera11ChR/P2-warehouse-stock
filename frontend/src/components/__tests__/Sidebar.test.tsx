import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Sidebar from '../Sidebar'

// REQ-P2-UI-001: logo corporativo en la esquina superior izquierda.
describe('Sidebar — marca corporativa', () => {
  it('muestra el logo corporativo con texto alternativo accesible', () => {
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={vi.fn()} />)

    const logo = screen.getByRole('img', { name: 'Logotipo corporativo DMS Telecom' })
    expect(logo).toBeInTheDocument()
    expect(logo.getAttribute('src')).toMatch(/company_logobrand/)
  })

  it('ubica el logo en la cabecera, antes de la navegación (esquina superior izquierda)', () => {
    const { container } = render(
      <Sidebar current={{ page: 'seccion-general' }} onNavigate={vi.fn()} />,
    )

    const aside = container.querySelector('aside')
    const logo = screen.getByRole('img', { name: 'Logotipo corporativo DMS Telecom' })
    const nav = screen.getByRole('navigation')

    // El logo es el primer contenido del aside (cabecera) y precede al menú.
    expect(aside?.firstElementChild?.contains(logo)).toBe(true)
    expect(
      logo.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // La marca textual acompaña al logo en la misma cabecera.
    expect(aside?.firstElementChild).toHaveTextContent('DMS - TELECOM')
  })

  it('no conserva rótulos legacy de DESPLIEGUE en el menú', () => {
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={vi.fn()} />)

    expect(screen.queryByText(/despliegue/i)).not.toBeInTheDocument()
  })

  it('mantiene la navegación a Reportes', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={onNavigate} />)

    await user.click(screen.getByRole('button', { name: /reportes/i }))
    expect(onNavigate).toHaveBeenCalledWith(expect.objectContaining({ page: 'reportes' }))
  })
})
