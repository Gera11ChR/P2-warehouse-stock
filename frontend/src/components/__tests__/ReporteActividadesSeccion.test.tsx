import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReporteActividadesSeccion from '../ReporteActividadesSeccion'
import {
  descargarReporteActividadesXlsx,
  ErrorDescargaReporte,
  listarReporteActividades,
} from '../../services/reportes'
import type { Actividad } from '../../types'

// ============================================================================
// SUBSECCIÓN REPORTES › ACTIVIDADES — smoke de integración (T9)
// REQ-REP-012/013: desglose por folio con inspección individual, selector de
// operación, descarga consolidada e individual con los filtros correctos,
// motivo visible y reseteo de la selección al cambiar filtros.
// Hooks REALES y capa HTTP mockeada (patrón de Reportes.test.tsx).
// ============================================================================

vi.mock('../../services/reportes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reportes')>()),
  listarReporteActividades: vi.fn(),
  descargarReporteActividadesXlsx: vi.fn(),
}))
vi.mock('../../utils/descargaArchivo', () => ({
  guardarBlob: vi.fn(),
  nombreArchivoDescarga: vi.fn(),
}))

const mockedListar = vi.mocked(listarReporteActividades)
const mockedDescargar = vi.mocked(descargarReporteActividadesXlsx)

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
  actividades: ['Tendido de fibra', 'Fusión de conectores'],
  comentarios: 'Sin novedad',
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
}

const otra: Actividad = { ...actividad, actividad_id: 2, folio: 'R0002', folio_num: 2 }

const EQUIPOS = [{ equipo_id: 5, nombre: 'Unidad Norte' }]

function renderSeccion(props: Partial<Parameters<typeof ReporteActividadesSeccion>[0]> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <ReporteActividadesSeccion
        equipos={EQUIPOS}
        equipoId={5}
        desde=""
        hasta=""
        onEquipoChange={vi.fn()}
        onDesdeChange={vi.fn()}
        onHastaChange={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { queryClient }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedListar.mockResolvedValue([actividad, otra])
})

describe('ReporteActividadesSeccion — desglose e inspección (REQ-REP-012)', () => {
  it('lista una fila por folio y expande el detalle con materiales, actividades y comentarios', async () => {
    const user = userEvent.setup()
    renderSeccion()

    expect(await screen.findByText('R0001')).toBeInTheDocument()
    expect(screen.getByText('R0002')).toBeInTheDocument()
    expect(mockedListar).toHaveBeenCalledWith({ equipo_id: 5 })

    await user.click(screen.getAllByRole('button', { name: 'Ver detalle' })[0])

    expect(await screen.findByText('Cable FO')).toBeInTheDocument()
    expect(screen.getByText('Tendido de fibra')).toBeInTheDocument()
    expect(screen.getByText('Sin novedad')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ocultar detalle' }),
    ).toHaveAttribute('aria-expanded', 'true')
  })

  it('el selector de operación filtra por actividad_id en el servidor', async () => {
    const user = userEvent.setup()
    mockedListar.mockImplementation(async (params) =>
      params?.actividad_id === 2 ? [otra] : [actividad, otra],
    )
    renderSeccion()

    await screen.findByRole('option', { name: /R0002 · / })
    await user.selectOptions(screen.getByLabelText('Actividad'), '2')

    await waitFor(() =>
      expect(mockedListar).toHaveBeenCalledWith({ equipo_id: 5, actividad_id: 2 }),
    )
    await waitFor(() => expect(screen.queryByText('R0001')).not.toBeInTheDocument())
    expect(screen.getByText('R0002')).toBeInTheDocument()
  })

  it('cambiar la Unidad resetea la selección de operación', async () => {
    const user = userEvent.setup()
    mockedListar.mockImplementation(async (params) =>
      params?.actividad_id === 2 ? [otra] : [actividad, otra],
    )
    renderSeccion()

    await screen.findByRole('option', { name: /R0002 · / })
    await user.selectOptions(screen.getByLabelText('Actividad'), '2')
    expect(screen.getByLabelText('Actividad')).toHaveValue('2')

    await user.selectOptions(screen.getByLabelText('Unidad'), '')

    expect(screen.getByLabelText('Actividad')).toHaveValue('')
  })
})

describe('ReporteActividadesSeccion — descargas (REQ-REP-013)', () => {
  it('descarga consolidada con los filtros vigentes y confirma el nombre', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockResolvedValue({
      blob: new Blob(['xlsx']),
      nombreArchivo: 'reporte-actividades-2026-10-20.xlsx',
    })
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    await waitFor(() =>
      expect(mockedDescargar).toHaveBeenCalledWith({ equipo_id: 5 }),
    )
    expect(
      await screen.findByText(/reporte-actividades-2026-10-20\.xlsx/),
    ).toBeInTheDocument()
  })

  it('descarga individual envía actividad_id de ese folio', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockResolvedValue({
      blob: new Blob(['xlsx']),
      nombreArchivo: 'reporte-actividades-R0002.xlsx',
    })
    renderSeccion()

    await screen.findByText('R0002')
    await user.click(screen.getAllByRole('button', { name: 'Descargar XLSX' })[1])

    await waitFor(() =>
      expect(mockedDescargar).toHaveBeenCalledWith({
        equipo_id: 5,
        actividad_id: 2,
      }),
    )
  })

  it('éxito individual: feedback con el nombre del archivo y el alcance «del folio»', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockResolvedValue({
      blob: new Blob(['xlsx']),
      nombreArchivo: 'reporte-actividades-R0002.xlsx',
    })
    renderSeccion()

    await screen.findByText('R0002')
    await user.click(screen.getAllByRole('button', { name: 'Descargar XLSX' })[1])

    expect(
      await screen.findByText(
        /reporte-actividades-R0002\.xlsx \(del folio\)\. Revisa la descarga de tu navegador\./,
      ),
    ).toBeInTheDocument()
  })

  it('404: alerta accionable «No hay actividades…» con el detalle del servidor', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(
        404,
        'Sin actividades para los filtros indicados',
      ),
    )
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(
      /No hay actividades para los filtros seleccionados/,
    )
    expect(alerta).toHaveTextContent(
      'Detalle del servidor: Sin actividades para los filtros indicados',
    )
  })

  it('422 por tope de folios: mensaje que menciona el tope de 100 folios por libro', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(
        422,
        'La consulta excede el tope de 100 folios por libro',
      ),
    )
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/tope de 100 folios por libro/)
    expect(alerta).toHaveTextContent('Detalle del servidor: La consulta excede el tope de 100 folios por libro')
  })

  it('422 LIMITE_HOJAS_EXCEDIDO (mensaje real del backend): menciona el tope de 100 folios', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(
        422,
        'El libro excede el tope de 100 folios; acote los filtros (Unidad, fechas u operación) e intente de nuevo',
        'LIMITE_HOJAS_EXCEDIDO',
      ),
    )
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/tope de 100 folios por libro/)
  })

  it('422 LIMITE_FILAS_EXCEDIDO (mensaje real del backend): mensaje propio del límite de filas, no «revisa las fechas»', async () => {
    const user = userEvent.setup()
    const detalle =
      'El libro excede el límite de 10000 filas inyectadas (materiales + actividades); acote los filtros e intente de nuevo'
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(422, detalle, 'LIMITE_FILAS_EXCEDIDO'),
    )
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/límite de 10 000 filas/)
    expect(alerta).not.toHaveTextContent(/Revisa las fechas/)
    expect(alerta).toHaveTextContent(`Detalle del servidor: ${detalle}`)
  })

  it('422 RANGO_FECHAS_INVALIDO: conserva el mensaje genérico de filtros inválidos', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(
        422,
        'El rango de fechas es inválido: desde no puede ser posterior a hasta.',
        'RANGO_FECHAS_INVALIDO',
      ),
    )
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/Los filtros no son válidos/)
  })

  it('durante la descarga consolidada el botón queda deshabilitado y el estado en curso es visible', async () => {
    const user = userEvent.setup()
    // Promesa diferida que nunca resuelve: la descarga queda en curso.
    mockedDescargar.mockReturnValue(new Promise(() => {}))
    renderSeccion()

    await screen.findByText('R0001')
    await user.click(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    )

    expect(
      await screen.findByText(/Descargando el libro consolidado…/),
    ).toBeInTheDocument()
    const boton = screen.getByRole('button', { name: 'Descargar libro (XLSX)' })
    expect(boton).toBeDisabled()
    expect(boton).toHaveAttribute('aria-busy', 'true')
  })

  it('listado vacío: descarga deshabilitada CON motivo visible', async () => {
    mockedListar.mockResolvedValue([])
    renderSeccion()

    expect(await screen.findByText(/No hay actividades para los filtros/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Descargar libro (XLSX)' }),
    ).toBeDisabled()
  })
})
