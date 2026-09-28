import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CatalogManagementPanel from '../CatalogManagementPanel'
import { ToastProvider } from '../ToastProvider'
import { useCategorias } from '../../hooks/useCategorias'
import { useUms } from '../../hooks/useUms'
import { useCategoriaAdmin } from '../../hooks/useCategoriaAdmin'
import { useUmAdmin } from '../../hooks/useUmAdmin'

vi.mock('../../hooks/useCategorias', () => ({ useCategorias: vi.fn() }))
vi.mock('../../hooks/useUms', () => ({ useUms: vi.fn() }))
vi.mock('../../hooks/useCategoriaAdmin', () => ({
  useCategoriaAdmin: vi.fn(),
}))
vi.mock('../../hooks/useUmAdmin', () => ({ useUmAdmin: vi.fn() }))

const mockedUseCategorias = vi.mocked(useCategorias)
const mockedUseUms = vi.mocked(useUms)
const mockedUseCategoriaAdmin = vi.mocked(useCategoriaAdmin)
const mockedUseUmAdmin = vi.mocked(useUmAdmin)

const renombrarCategoriaMutate = vi.fn()
const eliminarCategoriaMutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseCategorias.mockReturnValue({
    data: [{ id: 1, nombre: 'Cables', is_active: true }],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCategorias>)
  mockedUseUms.mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useUms>)
  mockedUseCategoriaAdmin.mockReturnValue({
    renombrar: { mutate: renombrarCategoriaMutate },
    eliminar: { mutate: eliminarCategoriaMutate },
  } as unknown as ReturnType<typeof useCategoriaAdmin>)
  mockedUseUmAdmin.mockReturnValue({
    crear: { mutate: vi.fn() },
    renombrar: { mutate: vi.fn() },
    eliminar: { mutate: vi.fn() },
  } as unknown as ReturnType<typeof useUmAdmin>)
})

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <CatalogManagementPanel />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('CatalogManagementPanel', () => {
  it('renderiza la lista de categorías y el bloque de U.M.', () => {
    renderPanel()

    expect(screen.getByText('Categorías')).toBeInTheDocument()
    expect(screen.getByText('Unidades de Medida')).toBeInTheDocument()
    expect(screen.getByText('Cables')).toBeInTheDocument()
    expect(
      screen.getByText('Sin unidades de medida registradas'),
    ).toBeInTheDocument()
  })

  it('Eliminar abre el ConfirmDialog con mensaje de soft-delete', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(
      screen.getByRole('button', { name: 'Eliminar categoría Cables' }),
    )

    expect(screen.getByText('Eliminar categoría')).toBeInTheDocument()
    expect(screen.getByText(/soft-delete/)).toBeInTheDocument()
    expect(eliminarCategoriaMutate).not.toHaveBeenCalled()
  })

  it('Modificar abre el modal con el nombre precargado y llama renombrar', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(
      screen.getByRole('button', { name: 'Modificar categoría Cables' }),
    )

    expect(screen.getByText('Modificar categoría')).toBeInTheDocument()
    const input = screen.getByLabelText('Nombre')
    expect(input).toHaveValue('Cables')

    await user.clear(input)
    await user.type(input, 'Ferretería')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(renombrarCategoriaMutate).toHaveBeenCalledTimes(1)
    expect(renombrarCategoriaMutate).toHaveBeenCalledWith(
      { id: 1, payload: { nombre: 'Ferretería' } },
      expect.any(Object),
    )
  })
})
