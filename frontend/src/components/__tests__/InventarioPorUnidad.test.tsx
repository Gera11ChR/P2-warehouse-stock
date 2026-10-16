import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InventarioPorEquipos from '../../pages/InventarioPorEquipos'
import Sidebar from '../Sidebar'
import { ToastProvider } from '../ToastProvider'
import {
  listEquipos,
  inventarioEquipo,
  createEquipo,
  updateEquipo,
  deleteEquipo,
  patchInventarioLocal,
} from '../../services/equipos'

// RF-1..RF-3, RF-9..RF-16 (REQ-UNI-001..003, 010..017).

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
  inventarioEquipo: vi.fn(),
  createEquipo: vi.fn(),
  updateEquipo: vi.fn(),
  deleteEquipo: vi.fn(),
  patchInventarioLocal: vi.fn(),
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
    integrantes: ['ELMER VICENTE TIQUET', 'ANA'],
  },
  {
    equipo_id: 2,
    nombre: 'SIN DATOS',
    descripcion: null,
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
  vi.mocked(listEquipos).mockResolvedValue(UNIDADES)
  vi.mocked(inventarioEquipo).mockResolvedValue([FILA])
})

describe('Inventario por Unidad — nomenclatura (RF-1..RF-3)', () => {
  it('RF-2/RF-3 REQ-UNI-002/003: encabezado y controles dicen Unidad', async () => {
    renderPagina()
    expect(
      await screen.findByRole('heading', { name: 'Inventario por Unidad' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Crear Unidad/ })).toBeInTheDocument()
    expect(screen.getByText('Seleccionar Unidad')).toBeInTheDocument()
    expect(await screen.findByText('— Seleccione una unidad —')).toBeInTheDocument()
    expect(screen.queryByText(/equipo/i)).not.toBeInTheDocument()
  })

  it('RF-3 REQ-UNI-003: el modal usa "Modificar Unidad" y "Nombre por Unidad"', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.click(await screen.findByRole('button', { name: /Modificar/ }))
    expect(await screen.findByRole('heading', { name: 'Modificar Unidad' })).toBeInTheDocument()
    expect(screen.getByText(/Nombre por Unidad/)).toBeInTheDocument()
    expect(screen.queryByText(/Nombre de Cuadrilla/)).not.toBeInTheDocument()
  })

  it('RF-1/RF-2 REQ-UNI-001/002: el menú lateral dice "Inventario por Unidad"', () => {
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={vi.fn()} />)
    expect(screen.getByText('Inventario por Unidad')).toBeInTheDocument()
    expect(screen.queryByText(/Inventario por Equipos/)).not.toBeInTheDocument()
  })
})

describe('Consulta de Unidad (RF-9..RF-16)', () => {
  it('RF-3: la tabla muestra la columna Valor Unitario de solo lectura con cifra y MXN', async () => {
    vi.mocked(inventarioEquipo).mockResolvedValue([
      FILA,
      { ...FILA, material_id: 8, codigo: 'CON-ACO-002', valor_unitario: 12.345 },
    ])
    renderPagina()

    const fila1 = (await screen.findByText('CON-ACO-001')).closest('tr')!
    const fila2 = screen.getByText('CON-ACO-002').closest('tr')!
    expect(
      screen.getByRole('columnheader', { name: 'Valor Unitario' }),
    ).toBeInTheDocument()
    expect(fila1).toHaveTextContent(/1\.00\s*MXN/)
    expect(fila2).toHaveTextContent(/12\.345\s*MXN/)
    // Solo lectura: la celda no contiene controles editables.
    expect(within(fila1).queryByRole('textbox')).not.toBeInTheDocument()
    expect(within(fila1).queryByRole('spinbutton')).not.toBeInTheDocument()
  })

  it('RF-9/RF-10 REQ-UNI-010/011: select con 3 opciones y "Inventario Unidad" por defecto', async () => {
    renderPagina()
    const select = await screen.findByLabelText('Consulta')
    const opciones = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(opciones).toEqual(['Inventario Unidad', 'Descripción', 'Integrantes'])
    expect(select).toHaveValue('inventario')
    expect(await screen.findByText('CON-ACO-001')).toBeInTheDocument()
  })

  it('RF-11 REQ-UNI-012: muestra la descripción de la unidad', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.selectOptions(await screen.findByLabelText('Consulta'), 'descripcion')
    expect(screen.getByTestId('unidad-descripcion')).toHaveTextContent(
      'Cuadrilla de pruebas',
    )
    expect(screen.queryByText('CON-ACO-001')).not.toBeInTheDocument()
  })

  it('RF-11 REQ-UNI-012: descripción nula o en blanco -> apartado vacío sin error', async () => {
    const user = userEvent.setup()
    vi.mocked(listEquipos).mockResolvedValue([
      { ...UNIDADES[0], descripcion: '   ' },
      UNIDADES[1],
    ])
    renderPagina()
    await user.selectOptions(await screen.findByLabelText('Consulta'), 'descripcion')
    expect(screen.getByTestId('unidad-descripcion')).toBeEmptyDOMElement()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '2')
    await user.selectOptions(screen.getByLabelText('Consulta'), 'descripcion')
    expect(screen.getByTestId('unidad-descripcion')).toBeEmptyDOMElement()
  })

  it('RF-12 REQ-UNI-013: lista integrantes y cantidad; vacío si no hay', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.selectOptions(await screen.findByLabelText('Consulta'), 'integrantes')
    const lista = screen.getByTestId('unidad-integrantes')
    expect(within(lista).getAllByRole('listitem').map((l) => l.textContent)).toEqual([
      'ELMER VICENTE TIQUET',
      'ANA',
    ])
    expect(screen.getByText('Cantidad: 2')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '2')
    await user.selectOptions(screen.getByLabelText('Consulta'), 'integrantes')
    expect(screen.getByTestId('unidad-integrantes')).toBeEmptyDOMElement()
    expect(screen.getByText('Cantidad: 0')).toBeInTheDocument()
  })

  it('RF-13 REQ-UNI-014: al cambiar de unidad el select vuelve a "Inventario Unidad"', async () => {
    const user = userEvent.setup()
    renderPagina()
    await user.selectOptions(await screen.findByLabelText('Consulta'), 'integrantes')
    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '2')
    expect(screen.getByLabelText('Consulta')).toHaveValue('inventario')
    expect(screen.queryByTestId('unidad-integrantes')).not.toBeInTheDocument()
  })

  it('RF-14 REQ-UNI-015: sin unidad seleccionada no hay select y se pide seleccionar', async () => {
    vi.mocked(listEquipos).mockResolvedValue([])
    renderPagina()
    expect(
      await screen.findByText('Seleccione una unidad para ver su inventario'),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
  })

  it('RF-15 REQ-UNI-016: Consulta es de solo lectura (sin escrituras ni acciones por fila)', async () => {
    const user = userEvent.setup()
    renderPagina()
    await screen.findByText('CON-ACO-001')
    for (const v of ['descripcion', 'integrantes', 'inventario']) {
      await user.selectOptions(screen.getByLabelText('Consulta'), v)
    }
    expect(createEquipo).not.toHaveBeenCalled()
    expect(updateEquipo).not.toHaveBeenCalled()
    expect(deleteEquipo).not.toHaveBeenCalled()
    expect(patchInventarioLocal).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /Configurar/i })).not.toBeInTheDocument()
  })

  it('RF-16 REQ-UNI-017: Modificar/Eliminar visibles con cualquier opción del select', async () => {
    const user = userEvent.setup()
    renderPagina()
    const select = await screen.findByLabelText('Consulta')
    for (const v of ['inventario', 'descripcion', 'integrantes']) {
      await user.selectOptions(select, v)
      expect(screen.getByRole('button', { name: /Modificar/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Eliminar/ })).toBeInTheDocument()
    }
    await waitFor(() => expect(inventarioEquipo).toHaveBeenCalledTimes(1))
  })

  it('el select de Consulta no aparece en la pestaña Configuración', async () => {
    const user = userEvent.setup()
    renderPagina()
    await screen.findByLabelText('Consulta')
    await user.click(screen.getByRole('button', { name: 'Configuración' }))
    expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
  })
})
