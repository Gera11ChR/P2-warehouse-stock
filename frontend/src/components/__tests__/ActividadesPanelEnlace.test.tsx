import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ActividadesPanel from '../ActividadesPanel'
import { ToastProvider } from '../ToastProvider'
import { NavigationContext } from '../../hooks/navigationContext'
import type { NavigationTarget } from '../../types'
import {
  crearActividad,
  obtenerActividadPendiente,
} from '../../services/actividades'
import type { Actividad } from '../../types'

// ============================================================================
// ENLACE DESDE EL AVISO DE CONFIRMACIÓN (REQ-REP-015)
//
// Tras confirmar una actividad, el aviso de éxito ofrece «Ir a Reportes ›
// Actividades» con la Unidad y el folio recién confirmado preseleccionados.
// Sin navegación disponible la acción se oculta (sin botón inerte).
// ============================================================================

vi.mock('../../services/actividades', () => ({
  obtenerActividadPendiente: vi.fn(),
  listarActividades: vi.fn(),
  crearActividad: vi.fn(),
}))

const mPendiente = vi.mocked(obtenerActividadPendiente)
const mCrear = vi.mocked(crearActividad)

const pendiente = {
  seguimiento: {
    seguimiento_id: 9,
    fecha_cierre: '2026-10-20T09:00:00Z',
    materiales: [],
  },
}

const actividad: Actividad = {
  actividad_id: 1,
  folio: 'R0001',
  folio_num: 1,
  seguimiento_id: 9,
  equipo_id: 4,
  equipo_nombre: 'Unidad Norte',
  fecha: '2026-10-20T10:00:00Z',
  usuario: 'qa',
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido'],
  comentarios: null,
  materiales: [],
}

function renderPanel(navigate?: (target: NavigationTarget) => void) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <NavigationContext.Provider value={navigate ?? null}>
          <ActividadesPanel equipoId={4} equipoNombre="Unidad Norte" />
        </NavigationContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

async function confirmarActividad(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Vehículo'), 'Camioneta 12')
  await user.type(screen.getByLabelText('Nombre Cliente(s)'), 'Cliente A')
  await user.type(screen.getByLabelText('Dirección(es)'), 'Calle 1')
  await user.type(screen.getByLabelText('Actividad realizada 1'), 'Tendido')
  await user.click(screen.getByRole('button', { name: 'Confirmar' }))
  const botones = screen.getAllByRole('button', { name: 'Confirmar' })
  await user.click(botones[botones.length - 1])
}

beforeEach(() => {
  vi.clearAllMocks()
  mPendiente.mockResolvedValue({ seguimiento: pendiente.seguimiento })
  mCrear.mockResolvedValue(actividad)
})

describe('ActividadesPanel — enlace al reporte (REQ-REP-015)', () => {
  it('tras confirmar ofrece el enlace y navega con Unidad y folio preseleccionados', async () => {
    const user = userEvent.setup()
    const navigate = vi.fn()
    renderPanel(navigate)

    await confirmarActividad(user)
    await screen.findByText('Actividad confirmada — Folio R0001')

    await user.click(
      await screen.findByRole('button', { name: 'Ir a Reportes › Actividades' }),
    )

    expect(navigate).toHaveBeenCalledWith({
      page: 'reportes',
      sub: 'actividades',
      equipoId: 4,
      actividadId: 1,
    })
  })

  it('sin navegación disponible la acción se oculta', async () => {
    const user = userEvent.setup()
    renderPanel()

    await confirmarActividad(user)
    await waitFor(() =>
      expect(mCrear).toHaveBeenCalledTimes(1),
    )

    expect(
      screen.queryByRole('button', { name: 'Ir a Reportes › Actividades' }),
    ).not.toBeInTheDocument()
  })
})
