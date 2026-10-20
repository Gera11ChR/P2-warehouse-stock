import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ActividadesPanel from '../ActividadesPanel'
import { ToastProvider } from '../ToastProvider'
import {
  crearActividad,
  obtenerActividadPendiente,
} from '../../services/actividades'
import type { Actividad, ActividadMaterial } from '../../types'

// ============================================================================
// PANEL — ACTIVIDADES DE LA UNIDAD (Etapa 1, T10)
// REQ-ACT-002 (materiales en solo lectura), REQ-ACT-003 (vínculo 1 a 1 y
// «Confirmar» deshabilitado), REQ-ACT-017 (estados pendiente/exitosa/
// rechazada con datos conservados). Hooks REALES y capa HTTP mockeada
// (patrón de SeguimientoPanelFlujo).
// ============================================================================

vi.mock('../../services/actividades', () => ({
  obtenerActividadPendiente: vi.fn(),
  listarActividades: vi.fn(),
  crearActividad: vi.fn(),
}))

const mPendiente = vi.mocked(obtenerActividadPendiente)
const mCrear = vi.mocked(crearActividad)

const materiales: ActividadMaterial[] = [
  {
    material_id: 3,
    codigo: null,
    descripcion: 'Cable FO',
    u_m: 'MTS',
    cantidad_consumida: 4,
    valor_unitario: 7.5,
  },
]

const pendiente = {
  seguimiento: {
    seguimiento_id: 9,
    fecha_cierre: '2026-10-19T09:00:00Z',
    materiales,
  },
}

const actividad: Actividad = {
  actividad_id: 1,
  folio: 'R0001',
  folio_num: 1,
  seguimiento_id: 9,
  equipo_id: 4,
  equipo_nombre: 'Unidad Norte',
  fecha: '2026-10-19T10:00:00Z',
  usuario: 'demo-operador',
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido de fibra'],
  comentarios: null,
  materiales,
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ActividadesPanel equipoId={4} equipoNombre="Unidad Norte" />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { claves: () => invalidate.mock.calls.map((c) => c[0]?.queryKey) }
}

beforeEach(() => {
  vi.clearAllMocks()
  mPendiente.mockResolvedValue({ seguimiento: pendiente.seguimiento })
})

describe('ActividadesPanel — consulta del pendiente (REQ-ACT-002/003)', () => {
  it('muestra el estado de carga mientras consulta', () => {
    mPendiente.mockReturnValue(new Promise(() => {}))
    renderPanel()
    expect(screen.getByText('Cargando actividades...')).toBeInTheDocument()
  })

  it('FAIL-CLOSED: un error de consulta se muestra y NO se traduce a «sin pendiente»', async () => {
    mPendiente.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 403,
        data: { error: { message: 'No autorizado para esta Unidad.' } },
      },
    })
    renderPanel()
    expect(
      await screen.findByText(
        'No se pudo consultar el seguimiento pendiente de actividad.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('No autorizado para esta Unidad.')).toBeInTheDocument()
    expect(
      screen.queryByText(/No hay un seguimiento cerrado pendiente/),
    ).not.toBeInTheDocument()
  })

  it('sin seguimiento pendiente: aviso, materiales vacíos y «Confirmar» deshabilitado (RF-3)', async () => {
    mPendiente.mockResolvedValue({ seguimiento: null })
    renderPanel()
    expect(
      await screen.findByText(/No hay un seguimiento cerrado pendiente de actividad/),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Sin materiales consumidos en este seguimiento.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
  })

  it('con pendiente: materiales en solo lectura y vínculo al seguimiento (RF-2)', async () => {
    renderPanel()
    expect(await screen.findByText('Cable FO')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('MTS')).toBeInTheDocument()
    expect(screen.getByText(/MXN/)).toBeInTheDocument()
    expect(
      screen.getByText(/Seguimiento #9 cerrado el/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeEnabled()
  })
})

describe('ActividadesPanel — confirmación (REQ-ACT-017)', () => {
  async function capturarYClicConfirmar(
    user: ReturnType<typeof userEvent.setup>,
  ) {
    await user.type(await screen.findByLabelText('Vehículo'), 'Camioneta 12')
    await user.type(screen.getByLabelText('Nombre Cliente(s)'), 'Cliente A')
    await user.type(screen.getByLabelText('Dirección(es)'), 'Calle 1')
    await user.type(
      screen.getByLabelText('Actividad realizada 1'),
      'Tendido de fibra',
    )
    // Botón del formulario (abre el diálogo de confirmación).
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(
      screen.getByRole('heading', { name: 'Confirmar actividades' }),
    ).toBeInTheDocument()
    // Botón del diálogo: el DOM ya tiene dos «Confirmar».
    const botones = screen.getAllByRole('button', { name: 'Confirmar' })
    await user.click(botones[botones.length - 1])
  }

  it('éxito: envía el payload, muestra folio, invalida y re-lee el pendiente', async () => {
    const user = userEvent.setup()
    mCrear.mockResolvedValue(actividad)
    // Primera lectura: hay pendiente. Tras invalidar, ya no hay (RF-3/17).
    mPendiente.mockResolvedValueOnce({ seguimiento: pendiente.seguimiento })
    mPendiente.mockResolvedValue({ seguimiento: null })
    const { claves } = renderPanel()

    await capturarYClicConfirmar(user)

    await waitFor(() => expect(mCrear).toHaveBeenCalledTimes(1))
    expect(mCrear).toHaveBeenCalledWith(4, {
      seguimiento_id: 9,
      vehiculo: 'Camioneta 12',
      clientes: 'Cliente A',
      direcciones: 'Calle 1',
      actividades: ['Tendido de fibra'],
      comentarios: null,
    })

    // Exitosa: toast con folio y aviso verde con folio asignado por el backend.
    expect(await screen.findByText('Actividad R0001 confirmada')).toBeInTheDocument()
    expect(
      await screen.findByText('Actividad confirmada — Folio R0001'),
    ).toBeInTheDocument()

    // Invalidación pendiente + historial + auditoría (sin estado local).
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['actividades', 4, 'pendiente'],
        ['actividades', 4],
        ['auditoria'],
      ]),
    )

    // Relectura del estado persistido: ya no hay seguimiento pendiente.
    expect(
      await screen.findByText(/No hay un seguimiento cerrado pendiente de actividad/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
  })

  it('rechazada: muestra el mensaje del backend y conserva los datos escritos', async () => {
    const user = userEvent.setup()
    mCrear.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          error: { message: 'El seguimiento ya tiene una actividad confirmada.' },
        },
      },
    })
    const { claves } = renderPanel()

    await capturarYClicConfirmar(user)

    expect(
      await screen.findByText(
        'El seguimiento ya tiene una actividad confirmada.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/Actividad confirmada — Folio/),
    ).not.toBeInTheDocument()
    // Los datos se conservan para reintentar (el formulario no se desmonta).
    expect(screen.getByLabelText('Vehículo')).toHaveValue('Camioneta 12')
    expect(screen.getByLabelText('Actividad realizada 1')).toHaveValue(
      'Tendido de fibra',
    )
    // Sin éxito no hay invalidación de pendiente/historial/auditoría.
    expect(claves()).toEqual([])
  })

  it('cancelar el diálogo no llama al backend', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.type(await screen.findByLabelText('Vehículo'), 'Camioneta 12')
    await user.type(screen.getByLabelText('Nombre Cliente(s)'), 'Cliente A')
    await user.type(screen.getByLabelText('Dirección(es)'), 'Calle 1')
    await user.type(screen.getByLabelText('Actividad realizada 1'), 'Tendido')

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(mCrear).not.toHaveBeenCalled()
    expect(
      screen.queryByRole('heading', { name: 'Confirmar actividades' }),
    ).not.toBeInTheDocument()
    // El botón del formulario sigue activo para reintentar.
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeEnabled()
  })
})
