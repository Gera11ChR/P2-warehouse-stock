import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SeccionGeneral from '../../pages/SeccionGeneral'

// ============================================================================
// REQ-SIMPL-001/002/006 — Eliminación del Buscador a granel (ROJO intencional)
//
// Tras el cambio 2026-10-04-eliminar-buscador-a-granel, la vista de
// Inventario General DEBE renderizarse sin la barra de pestañas («1
// Buscador» / «2 Buscador a granel») y con la tabla del buscador principal
// directamente visible. Hoy (pre-implementación) las aserciones de pestañas
// FALLAN porque la barra de pestañas todavía se renderiza.
// ============================================================================

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))

vi.mock('../../hooks/useUms', () => ({
  useUms: () => ({ data: [] }),
}))

vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({ data: [] }),
}))

vi.mock('../../hooks/useOperadorRapido', () => ({
  useOperadorRapido: () => ({
    operacion: null,
    cerrar: vi.fn(),
    abrirSumar: vi.fn(),
    abrirMover: vi.fn(),
    sumar: { loading: false },
    mover: { loading: false },
  }),
}))

vi.mock('../../services/catalog', () => ({
  listCategorias: vi.fn().mockResolvedValue([]),
  listCatalog: vi.fn().mockResolvedValue({ start_index: 1, materiales: [] }),
  createMaterial: vi.fn(),
  updateMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
}))

vi.mock('../../services/inventory', () => ({
  listSecciones: vi.fn().mockResolvedValue([]),
  stockSeccion: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../components/CatalogManagementPanel', () => ({
  default: () => <div data-testid="catalog-panel" />,
}))

function renderConQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <SeccionGeneral globalSearch="" />
    </QueryClientProvider>,
  )
  return queryClient
}

describe('SeccionGeneral — simplificación del buscador (REQ-SIMPL-001/002/006)', () => {
  it('REQ-SIMPL-001: NO renderiza la pestaña "2 Buscador a granel"', () => {
    renderConQueryClient()

    expect(screen.queryByText(/buscador a granel/i)).toBeNull()
  })

  it('REQ-SIMPL-001/002: NO renderiza la barra de pestañas (el botón "1 Buscador" no debe existir)', () => {
    renderConQueryClient()

    expect(screen.queryByText('1 Buscador')).toBeNull()
  })

  it('REQ-SIMPL-006: el buscador principal se muestra directamente como única vista', async () => {
    renderConQueryClient()

    // Con los mocks vacíos la tabla queda sin filas y la vista informa
    // «Mostrando 0 de 0 registros».
    expect(await screen.findByText(/Mostrando 0 de 0 registros/)).toBeTruthy()
  })
})
