import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
import type { Acta } from '../../types'

// ============================================================================
// PÁGINA REPORTES — SELECTORES DE OPERACIÓN DE ENTREGA Y CONSUMO
// (T10, REQ-REP-014)
//
// Página completa con capa HTTP mockeada (patrón de Reportes.test.tsx):
//  - Entrega: el selector «Acta» lista las actas del listado SIN filtrar y al
//    elegir una se consulta/exporta con `acta_id`.
//  - Consumo: el selector «Seguimiento» muestra el identificador visible
//    (Seguimiento #n · Acta #n) y envía `acta_id` al listado y a la
//    exportación Extensa.
//  - Cambiar la Unidad resetea la selección de operación (vuelve a «Todas»)
//    y no se envían más consultas con `acta_id`.
// Sin cambios de backend: el parámetro `acta_id` ya existía en el contrato
// de Entrega/Consumo; aquí solo se envía desde la UI.
// ============================================================================

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
}))
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
  observaciones: 'Entrega inicial',
  fecha: '2026-09-30T08:00:00',
  items: [],
}

/** Listado base por tipo; con `acta_id` devuelve solo esa acta (como el
 *  backend, que filtra por el servidor). */
function porTipo(
  entrega: Acta[] = [actaEntrega],
  consumo: Acta[] = [actaConsumo],
) {
  mockedListarActas.mockImplementation(async (tipo, params) => {
    const base = tipo === 'entrega' ? entrega : consumo
    if (params?.acta_id !== undefined) {
      return base.filter((a) => a.acta_id === params.acta_id)
    }
    return base
  })
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
  vi.mocked(listarReporteActividades).mockResolvedValue([])
  vi.mocked(descargarReporteActividadesXlsx).mockResolvedValue({
    blob: new Blob(['x']),
    nombreArchivo: 'libro.xlsx',
  })
  mockedDescargar.mockResolvedValue({
    blob: new Blob(['x']),
    nombreArchivo: 'acta.xlsx',
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function renderReportes(props: React.ComponentProps<typeof Reportes> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Reportes {...props} />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

const botonNormal = () =>
  screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })
const botonExtenso = () =>
  screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })

describe('Reportes — selectores de operación de Entrega y Consumo (REQ-REP-014)', () => {
  it('Entrega: el selector «Acta» lista las actas sin filtrar y envía acta_id al listado y a la exportación Normal', async () => {
    const user = userEvent.setup()
    renderReportes()

    // La opción sale del listado base (sin filtro de operación).
    await screen.findByRole('option', {
      name: /Acta #11 · .+ · Equipo Norte/,
    })
    await user.selectOptions(screen.getByLabelText('Acta'), '11')

    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenCalledWith('entrega', {
        acta_id: 11,
      }),
    )
    await waitFor(() => expect(botonNormal()).toBeEnabled())

    await user.click(botonNormal())

    await waitFor(() =>
      expect(mockedDescargar).toHaveBeenCalledWith('entrega', 'normal', {
        acta_id: 11,
      }),
    )
  })

  it('Consumo: el selector «Seguimiento» muestra su identificador visible y envía acta_id al listado y a la exportación Extensa', async () => {
    const user = userEvent.setup()
    renderReportes()

    await user.click(screen.getByRole('tab', { name: 'Consumo' }))

    await screen.findByRole('option', {
      name: /Seguimiento #7 · Acta #21 · /,
    })
    await user.selectOptions(screen.getByLabelText('Seguimiento'), '21')

    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenCalledWith('consumo', {
        acta_id: 21,
      }),
    )
    await waitFor(() => expect(botonExtenso()).toBeEnabled())

    await user.click(botonExtenso())

    await waitFor(() =>
      expect(mockedDescargar).toHaveBeenCalledWith('consumo', 'extenso', {
        acta_id: 21,
      }),
    )
  })

  it('cambiar la Unidad resetea la selección de operación y la siguiente consulta no lleva acta_id', async () => {
    const user = userEvent.setup()
    renderReportes()

    await screen.findByRole('option', {
      name: /Acta #11 · .+ · Equipo Norte/,
    })
    await user.selectOptions(screen.getByLabelText('Acta'), '11')
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenCalledWith('entrega', {
        acta_id: 11,
      }),
    )
    expect(screen.getByLabelText('Acta')).toHaveValue('11')

    await screen.findByRole('option', { name: 'Equipo Norte' })
    await user.selectOptions(screen.getByLabelText('Unidad'), '5')

    expect(screen.getByLabelText('Acta')).toHaveValue('')
    await waitFor(() =>
      expect(mockedListarActas).toHaveBeenLastCalledWith('entrega', {
        equipo_id: 5,
      }),
    )
  })
})
