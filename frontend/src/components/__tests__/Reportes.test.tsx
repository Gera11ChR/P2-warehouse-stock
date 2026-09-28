import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Reportes from '../../pages/Reportes'
import { ToastProvider } from '../../components/ToastProvider'
import { useReporteDespliegues } from '../../hooks/useReporteDespliegues'
import { descargarReporteCsv } from '../../services/reportes'
import { listEquipos } from '../../services/equipos'
import type { ReporteDespliegue } from '../../types'

vi.mock('../../hooks/useReporteDespliegues', () => ({
  useReporteDespliegues: vi.fn(),
}))
vi.mock('../../services/reportes', () => ({
  descargarReporteCsv: vi.fn(),
}))
vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
}))

const mockedUseReporteDespliegues = vi.mocked(useReporteDespliegues)
const mockedDescargarReporteCsv = vi.mocked(descargarReporteCsv)
const mockedListEquipos = vi.mocked(listEquipos)

const despliegue: ReporteDespliegue = {
  despliegue_id: 7,
  equipo_id: 5,
  equipo_nombre: 'Equipo Norte',
  fecha: '2026-09-01T10:00:00',
  estado: 'ABIERTA',
  usuario: 'demo-operador',
  observaciones: null,
  created_at: '2026-09-01T10:00:00',
  closed_at: null,
  items: [
    {
      material_id: 10,
      codigo: 'CBL-001',
      descripcion: 'Cable UTP Cat 6',
      categoria: 'Cables',
      um: 'METRO (M)',
      cantidad_tomada: 5,
      cantidad_sobrante: 2,
      cantidad_consumida: 3,
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseReporteDespliegues.mockReturnValue({
    data: [despliegue],
    isLoading: false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useReporteDespliegues>)
  mockedDescargarReporteCsv.mockResolvedValue(undefined)
  mockedListEquipos.mockResolvedValue([
    {
      equipo_id: 5,
      nombre: 'Equipo Norte',
      descripcion: null,
      is_active: true,
      integrantes: ['operador-a'],
    },
  ])
})

function renderReportes() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Reportes />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('Reportes — actividad de despliegues', () => {
  it('renderiza las filas del reporte', async () => {
    renderReportes()

    expect(await screen.findByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(screen.getByText('Equipo Norte')).toBeInTheDocument()
    expect(screen.getByText('ABIERTA')).toBeInTheDocument()
    expect(screen.getByText('Cables')).toBeInTheDocument()
    expect(screen.getByText('demo-operador')).toBeInTheDocument()
  })

  it('Exportar CSV llama a descargarReporteCsv con los filtros actuales', async () => {
    const user = userEvent.setup()
    renderReportes()

    // Esperar a que la query de equipos llene el select antes de elegir.
    await screen.findByRole('option', { name: 'Equipo Norte' })
    const selectEquipo = screen.getByRole('combobox')
    await user.selectOptions(selectEquipo, '5')

    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-01-01' },
    })
    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-01-31' },
    })

    await user.click(screen.getByRole('button', { name: 'Exportar CSV' }))

    await waitFor(() => {
      expect(mockedDescargarReporteCsv).toHaveBeenCalledTimes(1)
      expect(mockedDescargarReporteCsv).toHaveBeenCalledWith({
        equipo_id: 5,
        desde: '2026-01-01',
        hasta: '2026-01-31',
      })
    })
  })
})
