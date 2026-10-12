import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Reportes from '../../pages/Reportes'
import { ToastProvider } from '../../components/ToastProvider'
import { listEquipos } from '../../services/equipos'
import {
  descargarActaXlsx,
  ErrorDescargaReporte,
  listarActas,
} from '../../services/reportes'
import type { Acta } from '../../types'

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
}))
// Capa HTTP mockeada: los hooks y la página son los REALES.
vi.mock('../../services/reportes', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reportes')>()),
  listarActas: vi.fn(),
  descargarActaXlsx: vi.fn(),
}))

const mockedListEquipos = vi.mocked(listEquipos)
const mockedListarActas = vi.mocked(listarActas)
const mockedDescargar = vi.mocked(descargarActaXlsx)

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
  items: [
    {
      material_id: 10,
      codigo: 'CBL-001',
      descripcion: 'Cable UTP Cat 6',
      categoria: 'Cables',
      u_m: 'METRO (M)',
      cantidad: null,
      cantidad_tomada: 5,
      cantidad_consumida: 3,
    },
  ],
}

const actaEntrega: Acta = {
  acta_id: 11,
  tipo: 'ENTREGA',
  movimiento_id: 99,
  seguimiento_id: null,
  equipo_id: 5,
  equipo_nombre: 'Equipo Norte',
  usuario: 'demo-operador',
  observaciones: 'Entrega inicial',
  fecha: '2026-09-30T08:00:00',
  items: [
    {
      material_id: 12,
      codigo: 'CON-001',
      descripcion: 'Conector SC/APC',
      categoria: 'Conectores',
      u_m: 'PZ',
      cantidad: 40,
      cantidad_tomada: null,
      cantidad_consumida: null,
    },
  ],
}

function porTipo(
  entrega: Acta[] = [actaEntrega],
  consumo: Acta[] = [actaConsumo],
) {
  mockedListarActas.mockImplementation(async (tipo) =>
    tipo === 'entrega' ? entrega : consumo,
  )
}

const crearObjectURL = vi.fn(() => 'blob:acta')
const revocarObjectURL = vi.fn()
let clicks: string[] = []

beforeEach(() => {
  vi.clearAllMocks()
  clicks = []
  vi.stubGlobal('URL', {
    createObjectURL: crearObjectURL,
    revokeObjectURL: revocarObjectURL,
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicks.push(this.download)
  })
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
})

afterEach(() => {
  vi.unstubAllGlobals()
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

const botonNormal = () =>
  screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })
const botonExtenso = () =>
  screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })

describe('Reportes — subsecciones Entrega y Consumo con datos reales (API mockeada)', () => {
  it('muestra las pestañas, los botones XLSX y no el CSV legacy ni "Despliegue"', async () => {
    renderReportes()

    expect(screen.getByRole('tab', { name: 'Entrega' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: 'Consumo' })).toBeInTheDocument()
    expect(botonNormal()).toBeInTheDocument()
    expect(botonExtenso()).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /CSV/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/Despliegue/i)).not.toBeInTheDocument()
    await screen.findByText('Conector SC/APC')
  })

  it('Entrega renderiza las actas de /reportes/entrega', async () => {
    renderReportes()

    expect(await screen.findByText('Conector SC/APC')).toBeInTheDocument()
    expect(screen.getByText('#11')).toBeInTheDocument()
    expect(screen.getByText('Conectores')).toBeInTheDocument()
    expect(screen.getByText('40')).toBeInTheDocument()
    expect(mockedListarActas).toHaveBeenCalledWith('entrega', {})
  })

  it('Consumo renderiza las actas de /reportes/consumo con las cantidades del servidor', async () => {
    const user = userEvent.setup()
    renderReportes()

    await user.click(screen.getByRole('tab', { name: 'Consumo' }))

    expect(await screen.findByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(screen.getByText('Equipo Norte', { selector: 'td' })).toBeInTheDocument()
    expect(screen.getByText('#7')).toBeInTheDocument() // seguimiento
    expect(screen.getByText('Cables')).toBeInTheDocument()
    // tomada / consumida tal cual las registró PostgreSQL (sin columna Sobrante).
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: /sobrante/i })).not.toBeInTheDocument()
    expect(screen.getByText('demo-operador')).toBeInTheDocument()
    expect(mockedListarActas).toHaveBeenCalledWith('consumo', {})
  })

  it('lista vacía: tabla vacía y exportación deshabilitada CON motivo visible', async () => {
    porTipo([], [])
    renderReportes()

    expect(await screen.findByText('Sin actas de entrega')).toBeInTheDocument()
    expect(botonNormal()).toBeDisabled()
    expect(botonExtenso()).toBeDisabled()
    expect(botonNormal()).toHaveAccessibleDescription(/No hay actas para los filtros/)
  })

  it('error al cargar el listado: muestra el error y deshabilita exportar con motivo', async () => {
    mockedListarActas.mockRejectedValue({
      isAxiosError: true,
      response: { status: 500, data: { error: { message: 'BD caída' } } },
    })
    renderReportes()

    expect(
      await screen.findByText('No se pudo cargar el reporte de entrega.'),
    ).toBeInTheDocument()
    expect(botonNormal()).toBeDisabled()
    expect(botonNormal()).toHaveAccessibleDescription(/No se pudo cargar el listado/)
  })

  it('con actas cargadas los botones XLSX están habilitados', async () => {
    renderReportes()
    await screen.findByText('Conector SC/APC')
    expect(botonNormal()).toBeEnabled()
    expect(botonExtenso()).toBeEnabled()
    expect(screen.queryByText(/aún no está habilitada/)).not.toBeInTheDocument()
  })

  it('conserva los filtros equipo / desde / hasta al cambiar de pestaña y los envía al servicio', async () => {
    const user = userEvent.setup()
    renderReportes()

    await screen.findByRole('option', { name: 'Equipo Norte' })
    await user.selectOptions(screen.getByRole('combobox'), '5')
    fireEvent.change(screen.getByLabelText('Desde'), {
      target: { value: '2026-01-01' },
    })
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenLastCalledWith('entrega', {
        equipo_id: 5,
        desde: '2026-01-01',
      }),
    )

    await user.click(screen.getByRole('tab', { name: 'Consumo' }))

    expect(screen.getByRole('combobox')).toHaveValue('5')
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-01-01')
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenLastCalledWith('consumo', {
        equipo_id: 5,
        desde: '2026-01-01',
      }),
    )
  })

  it('abre en la subsección y el equipo indicados (llegada desde un aviso de acta)', async () => {
    renderReportes({ initialSub: 'consumo', initialEquipoId: 5 })

    expect(screen.getByRole('tab', { name: 'Consumo' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await screen.findByRole('option', { name: 'Equipo Norte' })
    expect(screen.getByRole('combobox')).toHaveValue('5')
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenLastCalledWith('consumo', {
        equipo_id: 5,
      }),
    )
  })

  it('un acta nueva aparece sin recargar la página cuando se invalidan las actas de Entrega', async () => {
    mockedListarActas.mockResolvedValueOnce([])
    const { queryClient } = renderReportes()
    expect(await screen.findByText('Sin actas de entrega')).toBeInTheDocument()

    // Simula lo que hace Transferencias tras «Confirmar TEAMS»: el trigger de
    // PostgreSQL ya registró el acta; la UI solo recarga el estado persistido.
    mockedListarActas.mockResolvedValue([actaEntrega])
    await act(() =>
      queryClient.invalidateQueries({
        queryKey: ['reportes', 'actas', 'entrega'],
      }),
    )

    expect(await screen.findByText('Conector SC/APC')).toBeInTheDocument()
    expect(screen.queryByText('Sin actas de entrega')).not.toBeInTheDocument()
  })
})

describe('Reportes — exportación XLSX (descarga de blob)', () => {
  it('Normal: descarga con los filtros, usa el nombre del servidor, libera el object URL y confirma', async () => {
    const user = userEvent.setup()
    const blob = new Blob(['xlsx'])
    mockedDescargar.mockResolvedValue({
      blob,
      nombreArchivo: 'ACTA_ENTREGA_2026-10-02.xlsx',
    })
    renderReportes()
    await screen.findByRole('option', { name: 'Equipo Norte' })
    await user.selectOptions(screen.getByRole('combobox'), '5')
    await waitFor(() => expect(botonNormal()).toBeEnabled())

    await user.click(botonNormal())

    await waitFor(() => expect(clicks).toEqual(['ACTA_ENTREGA_2026-10-02.xlsx']))
    expect(mockedDescargar).toHaveBeenCalledWith('entrega', 'normal', {
      equipo_id: 5,
    })
    expect(crearObjectURL).toHaveBeenCalledWith(blob)
    expect(revocarObjectURL).toHaveBeenCalledWith('blob:acta')
    expect(
      await screen.findByText(/Archivo generado: ACTA_ENTREGA_2026-10-02\.xlsx/),
    ).toBeInTheDocument()
  })

  it('Extenso en Consumo: pide /reportes/consumo formato extenso', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockResolvedValue({
      blob: new Blob(['x']),
      nombreArchivo: 'acta-consumo-extenso.xlsx',
    })
    renderReportes({ initialSub: 'consumo' })
    await screen.findByText('Cable UTP Cat 6')

    await user.click(botonExtenso())

    await waitFor(() =>
      expect(mockedDescargar).toHaveBeenCalledWith('consumo', 'extenso', {}),
    )
    await waitFor(() => expect(clicks).toEqual(['acta-consumo-extenso.xlsx']))
  })

  it('mientras descarga muestra "Generando" y bloquea ambos botones', async () => {
    const user = userEvent.setup()
    let resolver!: (v: { blob: Blob; nombreArchivo: string }) => void
    mockedDescargar.mockReturnValue(
      new Promise((r) => {
        resolver = r
      }),
    )
    renderReportes()
    await screen.findByText('Conector SC/APC')

    await user.click(botonNormal())

    expect(await screen.findByText(/Generando Acta de Entrega/)).toBeInTheDocument()
    expect(botonNormal()).toBeDisabled()
    expect(botonExtenso()).toBeDisabled()

    await act(async () => resolver({ blob: new Blob(['x']), nombreArchivo: 'a.xlsx' }))
    await waitFor(() => expect(botonNormal()).toBeEnabled())
  })

  it('404: mensaje accionable de "sin actas" con el detalle del servidor y sin descarga', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(
      new ErrorDescargaReporte(404, 'No hay actas para los filtros indicados'),
    )
    renderReportes()
    await screen.findByText('Conector SC/APC')

    await user.click(botonNormal())

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/No hay actas de Entrega para los filtros/)
    expect(alerta).toHaveTextContent(
      'Detalle del servidor: No hay actas para los filtros indicados',
    )
    expect(clicks).toEqual([])
    expect(revocarObjectURL).not.toHaveBeenCalled()
  })

  it('422: informa filtros inválidos', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(new ErrorDescargaReporte(422))
    renderReportes()
    await screen.findByText('Conector SC/APC')

    await user.click(botonExtenso())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Los filtros no son válidos/,
    )
  })

  it('403: informa falta de permiso (equipo ajeno)', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(new ErrorDescargaReporte(403))
    renderReportes()
    await screen.findByText('Conector SC/APC')

    await user.click(botonNormal())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /No tienes permiso para exportar/,
    )
  })

  it('error de red (sin status): mensaje genérico y se puede reintentar', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValueOnce(new ErrorDescargaReporte())
    renderReportes()
    await screen.findByText('Conector SC/APC')

    await user.click(botonNormal())
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /No se pudo generar el archivo/,
    )

    mockedDescargar.mockResolvedValue({
      blob: new Blob(['x']),
      nombreArchivo: 'ok.xlsx',
    })
    await user.click(botonNormal())
    await waitFor(() => expect(clicks).toEqual(['ok.xlsx']))
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    )
  })

  it('cambiar un filtro limpia el resultado anterior de exportación', async () => {
    const user = userEvent.setup()
    mockedDescargar.mockRejectedValue(new ErrorDescargaReporte(404))
    renderReportes()
    await screen.findByText('Conector SC/APC')
    await user.click(botonNormal())
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Hasta'), {
      target: { value: '2026-12-31' },
    })

    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    )
  })
})
