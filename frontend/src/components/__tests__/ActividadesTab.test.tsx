import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InventarioPorEquipos from '../../pages/InventarioPorEquipos'
import { ToastProvider } from '../ToastProvider'
import {
  listEquipos,
  inventarioEquipo,
} from '../../services/equipos'
import { obtenerActividadPendiente } from '../../services/actividades'

// ============================================================================
// PESTAÑA ACTIVIDADES — subsección de Inventario por Unidad (Etapa 1, T10)
// REQ-ACT-001: subsección "ACTIVIDADES" ubicada DESPUÉS de CONSUMO en la
// barra de subsecciones, que monta el panel de registro.
// ============================================================================

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
  inventarioEquipo: vi.fn(),
  createEquipo: vi.fn(),
  updateEquipo: vi.fn(),
  deleteEquipo: vi.fn(),
  patchInventarioLocal: vi.fn(),
}))
vi.mock('../../services/actividades', () => ({
  obtenerActividadPendiente: vi.fn(),
  listarActividades: vi.fn(),
  crearActividad: vi.fn(),
}))
vi.mock('../SeguimientoPanel', () => ({ default: () => <div>panel consumo</div> }))
vi.mock('../../hooks/useCategorias', () => ({
  useCategorias: () => ({ data: [] }),
}))
vi.mock('../../hooks/useUms', () => ({ useUms: () => ({ data: [] }) }))

const UNIDADES = [
  {
    equipo_id: 1,
    nombre: 'PARTNER 2017',
    descripcion: 'Cuadrilla de pruebas',
    is_active: true,
    integrantes: [],
  },
]

const FILA = {
  equipo_id: 1,
  material_id: 7,
  codigo: 'CON-ACO-001',
  descripcion: 'ACOPLADORES',
  u_m: 'PZ',
  stock_minimo: 50,
  stock_actual: 1,
  valor_unitario: 1,
  alerta_stock: true,
  ultimo_movimiento_id: null,
  stock_minimo_local: null,
  categoria_local_id: null,
  um_local_id: null,
  stock_minimo_efectivo: 50,
  categoria_efectiva: null,
  um_efectivo: 'PZ',
}

function renderPagina() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <InventarioPorEquipos />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listEquipos).mockResolvedValue(UNIDADES)
  vi.mocked(inventarioEquipo).mockResolvedValue([FILA])
  vi.mocked(obtenerActividadPendiente).mockResolvedValue({
    seguimiento: {
      seguimiento_id: 9,
      fecha_cierre: '2026-10-19T09:00:00Z',
      materiales: [
        {
          material_id: 3,
          codigo: null,
          descripcion: 'Cable FO',
          u_m: 'MTS',
          cantidad_consumida: 4,
          valor_unitario: 7.5,
        },
      ],
    },
  })
})

describe('Inventario por Unidad — subsección ACTIVIDADES (REQ-ACT-001)', () => {
  it('la pestaña ACTIVIDADES existe y está DESPUÉS de CONSUMO', async () => {
    renderPagina()
    const consumo = await screen.findByRole('button', { name: 'CONSUMO' })
    const actividades = screen.getByRole('button', { name: 'ACTIVIDADES' })
    // compareDocumentPosition devuelve dónde está `actividades` respecto a
    // `consumo`: FOLLOWING significa que ACTIVIDADES viene después.
    expect(
      consumo.compareDocumentPosition(actividades) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('sin unidades no hay nada que seleccionar', async () => {
    const user = userEvent.setup()
    vi.mocked(listEquipos).mockResolvedValue([])
    renderPagina()
    await user.click(await screen.findByRole('button', { name: 'ACTIVIDADES' }))
    expect(await screen.findByText('Seleccione una unidad')).toBeInTheDocument()
  })

  it('con unidad seleccionada monta el panel ACTIVIDADES', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.selectOptions(
      await screen.findByLabelText('Seleccionar Unidad'),
      '1',
    )
    await user.click(screen.getByRole('button', { name: 'ACTIVIDADES' }))

    expect(await screen.findByText('Materiales Consumidos')).toBeInTheDocument()
    expect(await screen.findByText('Cable FO')).toBeInTheDocument()
    expect(obtenerActividadPendiente).toHaveBeenCalledWith(1)
  })
})
