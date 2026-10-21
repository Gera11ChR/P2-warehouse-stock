import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Reportes from '../../pages/Reportes'
import { ToastProvider } from '../../components/ToastProvider'
import { listEquipos } from '../../services/equipos'
import {
  descargarActaXlsx,
  descargarReporteActividadesXlsx,
  listarActas,
  listarReporteActividades,
} from '../../services/reportes'
import type { Acta, Actividad } from '../../types'

// ============================================================================
// PÁGINA REPORTES — PESTAÑA «ACTIVIDADES» (T10, REQ-REP-001/012/015)
//
// Integración a nivel de página completa (patrón de Reportes.test.tsx):
// capa HTTP mockeada, página y hooks REALES.
//  - La pestaña «Actividades» está DESPUÉS de «Consumo» (REQ-REP-001).
//  - Al abrirla se monta la sección con su propia consulta (no se reutiliza
//    `listarActas` con un tipo inventado).
//  - `initialSub`/`initialActividadId` preseleccionan pestaña, filtro y folio.
//  - Los filtros compartidos se conservan al cambiar de pestaña.
//  - Invalidar ['reportes','actividades'] (REQ-REP-015) recarga el listado.
// ============================================================================

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
}))
// Capa HTTP mockeada: los hooks y la página son los REALES.
vi.mock('../../services/reportes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reportes')>()),
  listarActas: vi.fn(),
  descargarActaXlsx: vi.fn(),
  listarReporteActividades: vi.fn(),
  descargarReporteActividadesXlsx: vi.fn(),
}))
vi.mock('../../utils/descargaArchivo', () => ({
  guardarBlob: vi.fn(),
  nombreArchivoDescarga: vi.fn(),
}))

const mockedListEquipos = vi.mocked(listEquipos)
const mockedListarActas = vi.mocked(listarActas)
const mockedDescargarActas = vi.mocked(descargarActaXlsx)
const mockedListarActividades = vi.mocked(listarReporteActividades)
const mockedDescargarActividades = vi.mocked(descargarReporteActividadesXlsx)

const actividad: Actividad = {
  actividad_id: 1,
  folio: 'R0001',
  folio_num: 1,
  seguimiento_id: 9,
  equipo_id: 5,
  equipo_nombre: 'Unidad Norte',
  fecha: '2026-10-20T15:00:00Z',
  usuario: 'demo-operador',
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido de fibra'],
  comentarios: null,
  materiales: [],
}

const otra: Actividad = {
  ...actividad,
  actividad_id: 2,
  folio: 'R0002',
  folio_num: 2,
}

const actaConsumo: Acta = {
  acta_id: 21,
  tipo: 'CONSUMO',
  movimiento_id: null,
  seguimiento_id: 7,
  equipo_id: 5,
  equipo_nombre: 'Equipo Norte',
  usuario: 'demo-operador',
  observaciones: null,
  fecha: '2026-10-01T10:00:00',
  items: [],
}

const actaEntrega: Acta = {
  acta_id: 11,
  tipo: 'ENTREGA',
  movimiento_id: 99,
  seguimiento_id: null,
  equipo_id: 5,
  equipo_nombre: 'Equipo Norte',
  usuario: 'demo-operador',
  observaciones: null,
  fecha: '2026-09-30T08:00:00',
  items: [],
}

function porTipo(
  entrega: Acta[] = [actaEntrega],
  consumo: Acta[] = [actaConsumo],
) {
  mockedListarActas.mockImplementation(async (tipo) =>
    tipo === 'entrega' ? entrega : consumo,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  porTipo()
  mockedListEquipos.mockResolvedValue([
    {
      equipo_id: 5,
      nombre: 'Equipo Norte',
      descripcion: null,
      is_active: true,
      integrantes: ['operador-a'],
    },
  ])
  mockedListarActividades.mockResolvedValue([actividad, otra])
  mockedDescargarActas.mockResolvedValue({
    blob: new Blob(['x']),
    nombreArchivo: 'acta.xlsx',
  })
  mockedDescargarActividades.mockResolvedValue({
    blob: new Blob(['x']),
    nombreArchivo: 'libro.xlsx',
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function renderReportes(props: React.ComponentProps<typeof Reportes> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Reportes {...props} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { queryClient, ...view }
}

describe('Reportes — pestaña Actividades (REQ-REP-001/012/015)', () => {
  it('la pestaña «Actividades» está DESPUÉS de «Consumo» en el DOM', async () => {
    renderReportes()

    const consumo = await screen.findByRole('tab', { name: 'Consumo' })
    const actividades = screen.getByRole('tab', { name: 'Actividades' })
    // compareDocumentPosition devuelve dónde está `actividades` respecto a
    // `consumo`: FOLLOWING significa que Actividades viene después.
    expect(
      consumo.compareDocumentPosition(actividades) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('al pulsar «Actividades» monta la sección con su propia consulta (nunca listarActas con tipo inventado)', async () => {
    const user = userEvent.setup()
    renderReportes()

    await user.click(screen.getByRole('tab', { name: 'Actividades' }))

    expect(await screen.findByText('R0001')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    ).toBeInTheDocument()
    expect(mockedListarActividades).toHaveBeenCalledWith({})
    expect(mockedListarActas).not.toHaveBeenCalledWith(
      'actividades',
      expect.anything(),
    )
  })

  it('initialSub="actividades" + initialActividadId=2 abre la pestaña con el selector «Actividad» en el folio preseleccionado', async () => {
    mockedListarActividades.mockImplementation(async (params) =>
      params?.actividad_id === 2 ? [otra] : [actividad, otra],
    )
    renderReportes({ initialSub: 'actividades', initialActividadId: 2 })

    expect(screen.getByRole('tab', { name: 'Actividades' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await screen.findByRole('option', { name: /R0002 · / })
    expect(screen.getByLabelText('Actividad')).toHaveValue('2')
    await waitFor(() =>
      expect(mockedListarActividades).toHaveBeenCalledWith({ actividad_id: 2 }),
    )
    // La tabla muestra solo el folio preseleccionado (filtro por servidor).
    expect(await screen.findByText('R0002')).toBeInTheDocument()
    expect(screen.queryByText('R0001')).not.toBeInTheDocument()
  })

  it('cambiar a «Consumo» y volver a «Actividades» conserva los filtros compartidos', async () => {
    const user = userEvent.setup()
    renderReportes()

    await screen.findByRole('option', { name: 'Equipo Norte' })
    await user.selectOptions(screen.getByLabelText('Unidad'), '5')
    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-01-01' },
    })
    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-12-31' },
    })

    await user.click(screen.getByRole('tab', { name: 'Actividades' }))
    await waitFor(() =>
      expect(mockedListarActividades).toHaveBeenCalledWith({
        equipo_id: 5,
        desde: '2026-01-01',
        hasta: '2026-12-31',
      }),
    )

    await user.click(screen.getByRole('tab', { name: 'Consumo' }))
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenLastCalledWith('consumo', {
        equipo_id: 5,
        desde: '2026-01-01',
        hasta: '2026-12-31',
      }),
    )

    await user.click(screen.getByRole('tab', { name: 'Actividades' }))
    expect(screen.getByLabelText('Unidad')).toHaveValue('5')
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-01-01')
    expect(screen.getByLabelText('Hasta')).toHaveValue('2026-12-31')
    await waitFor(() =>
      expect(mockedListarActividades).toHaveBeenLastCalledWith({
        equipo_id: 5,
        desde: '2026-01-01',
        hasta: '2026-12-31',
      }),
    )
  })

  it('invalidar ["reportes","actividades"] tras confirmar recarga el listado y aparece el folio nuevo (REQ-REP-015)', async () => {
    mockedListarActividades.mockResolvedValueOnce([actividad])
    const { queryClient } = renderReportes({ initialSub: 'actividades' })
    expect(await screen.findByText('R0001')).toBeInTheDocument()
    expect(screen.queryByText('R0002')).not.toBeInTheDocument()

    // Simula lo que hace `invalidarActividadesEquipo` tras confirmar una
    // actividad en Inventario por Unidad: PostgreSQL ya registró el folio;
    // la UI solo recarga el estado persistido.
    mockedListarActividades.mockResolvedValue([actividad, otra])
    await act(() =>
      queryClient.invalidateQueries({
        queryKey: ['reportes', 'actividades'],
      }),
    )

    expect(await screen.findByText('R0002')).toBeInTheDocument()
  })
})
