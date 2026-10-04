import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Header from '../Header'

// REQ-BREAD-001/002/006: la cabecera NO debe renderizar el prefijo raíz
// "Dashboard /" y debe mostrar únicamente la ruta limpia de la sección.
describe('Header — breadcrumb sin prefijo Dashboard', () => {
  it('no renderiza el texto "Dashboard" para una sección simple', () => {
    render(<Header breadcrumb="Sección General" onSearch={vi.fn()} />)

    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
  })

  it('no renderiza el texto "Dashboard" para una subvista compuesta', () => {
    render(<Header breadcrumb="Fibra Óptica / Paquete" onSearch={vi.fn()} />)

    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
  })

  it('muestra únicamente la ruta limpia de la sección simple', () => {
    render(<Header breadcrumb="Sección General" onSearch={vi.fn()} />)

    expect(screen.getByText('Sección General')).toBeInTheDocument()
    expect(screen.queryByText(/\//)).not.toBeInTheDocument()
  })

  it('muestra únicamente la ruta limpia de la subvista compuesta', () => {
    render(<Header breadcrumb="Fibra Óptica / Paquete" onSearch={vi.fn()} />)

    expect(screen.getByText('Fibra Óptica / Paquete')).toBeInTheDocument()
  })

  it('conserva el separador interno de la subvista pero sin nodo raíz', () => {
    render(<Header breadcrumb="Reportes / Consumo" onSearch={vi.fn()} />)

    const nav = screen.getByRole('navigation')
    expect(nav).toHaveTextContent('Reportes / Consumo')
    expect(nav).not.toHaveTextContent('Dashboard')
  })
})

// REQ-BREAD-004: el buscador global debe permanecer operativo.
describe('Header — buscador global operativo', () => {
  it('mantiene el placeholder y el atajo Ctrl + K', () => {
    render(<Header breadcrumb="Sección General" onSearch={vi.fn()} />)

    expect(
      screen.getByPlaceholderText('Buscar materiales, SKU o descripción...'),
    ).toBeInTheDocument()
    expect(screen.getByText('Ctrl + K')).toBeInTheDocument()
  })

  it('propaga el término buscado mediante onSearch', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(<Header breadcrumb="Sección General" onSearch={onSearch} />)

    await user.type(
      screen.getByPlaceholderText('Buscar materiales, SKU o descripción...'),
      'fibra',
    )

    expect(onSearch).toHaveBeenLastCalledWith('fibra')
  })
})
