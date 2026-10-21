import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InventarioPorEquipos from '../../pages/InventarioPorEquipos'
import { ToastProvider } from '../ToastProvider'
import {
  inventarioEquipo,
  listEquipos,
} from '../../services/equipos'
import {
  crearReferencia,
  eliminarReferencia,
  listarReferencia,
  modificarReferencia,
} from '../../services/referencia'
import { listSecciones, stockSeccion } from '../../services/inventory'
import { listFibraStock } from '../../services/fibra'
import type { ReferenciaLinea } from '../../types'

// REQ-REF-001/003/004/016 — botón «Referencia» en Inventario por Unidad:
// presente en TODAS las vistas de Consulta y en Configuración (bajo las
// pestañas), ausente en CONSUMO y ACTIVIDADES, con `aria-expanded`; el panel
// conserva su estado al cambiar de Unidad, recarga las líneas de la nueva
// Unidad y descarta formularios pendientes (REQ-REF-004). Consulta es de
// SOLO LECTURA (REQ-REF-003).

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
  inventarioEquipo: vi.fn(),
  createEquipo: vi.fn(),
  updateEquipo: vi.fn(),
  deleteEquipo: vi.fn(),
  patchInventarioLocal: vi.fn(),
}))
vi.mock('../../services/referencia', () => ({
  listarReferencia: vi.fn(),
  crearReferencia: vi.fn(),
  modificarReferencia: vi.fn(),
  eliminarReferencia: vi.fn(),
}))
vi.mock('../../services/inventory', () => ({
  listSecciones: vi.fn(),
  stockSeccion: vi.fn(),
}))
vi.mock('../../services/fibra', () => ({ listFibraStock: vi.fn() }))
vi.mock('../../hooks/useCategorias', () => ({
  useCategorias: () => ({ data: [] }),
}))
vi.mock('../../hooks/useUms', () => ({ useUms: () => ({ data: [] }) }))
vi.mock('../SeguimientoPanel', () => ({ default: () => <div>panel consumo</div> }))
vi.mock('../ActividadesPanel', () => ({
  default: () => <div>panel actividades</div>,
}))

const UNIDADES = [
  {
    equipo_id: 1,
    nombre: 'PARTNER 2017',
    descripcion: 'Cuadrilla de pruebas',
    is_active: true,
    integrantes: ['ELMER VICENTE TIQUET'],
  },
  {
    equipo_id: 2,
    nombre: 'PARTNER 2018',
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

const linea = (overrides: Partial<ReferenciaLinea> = {}): ReferenciaLinea => ({
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  cantidad_semanal: 2.5,
  ...overrides,
})

function renderPagina() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
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
  vi.mocked(listarReferencia).mockImplementation((id: number) =>
    Promise.resolve(
      id === 1
        ? [linea()]
        : [linea({ material_id: 20, descripcion: 'Fibra drop 1 hilo', u_m: 'METRO (M)' })],
    ),
  )
  vi.mocked(listSecciones).mockResolvedValue([
    { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', is_active: true },
  ])
  vi.mocked(stockSeccion).mockResolvedValue([
    {
      material_id: 10,
      codigo: 'CBL-001',
      descripcion: 'Cable UTP Cat 6',
      u_m: 'METRO (M)',
      stock_minimo: null,
      stock_actual: 40,
      valor_unitario: 1,
      alerta_stock: false,
    },
  ])
  vi.mocked(listFibraStock).mockResolvedValue([])
})

describe('botón «Referencia» (REQ-REF-001)', () => {
  it('presente en Consulta, alterna el panel y actualiza aria-expanded', async () => {
    const user = userEvent.setup()
    renderPagina()

    const boton = await screen.findByRole('button', { name: 'Referencia' })
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    expect(boton).toHaveAttribute('aria-controls', 'referencia-panel')

    await user.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    expect(
      await screen.findByRole('heading', { name: 'Materiales Referencia' }),
    ).toBeInTheDocument()

    await user.click(boton)
    expect(boton).toHaveAttribute('aria-expanded', 'false')
    expect(
      screen.queryByRole('heading', { name: 'Materiales Referencia' }),
    ).not.toBeInTheDocument()
  })

  it('presente en las TRES vistas de Consulta y en Configuración', async () => {
    const user = userEvent.setup()
    renderPagina()

    const boton = await screen.findByRole('button', { name: 'Referencia' })
    const consulta = screen.getByLabelText('Consulta')
    for (const vista of ['inventario', 'descripcion', 'integrantes']) {
      await user.selectOptions(consulta, vista)
      expect(boton).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Configuración' }))
    expect(
      screen.getByRole('button', { name: 'Referencia' }),
    ).toBeInTheDocument()
  })

  it('AUSENTE en CONSUMO y ACTIVIDADES', async () => {
    const user = userEvent.setup()
    renderPagina()

    await screen.findByRole('button', { name: 'Referencia' })
    await user.click(screen.getByRole('button', { name: 'CONSUMO' }))
    expect(
      screen.queryByRole('button', { name: 'Referencia' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'ACTIVIDADES' }))
    expect(
      screen.queryByRole('button', { name: 'Referencia' }),
    ).not.toBeInTheDocument()
  })
})

describe('Consulta SOLO LECTURA (REQ-REF-003)', () => {
  it('el panel no ofrece acciones de escritura y solo lista la Referencia', async () => {
    const user = userEvent.setup()
    renderPagina()

    await user.click(await screen.findByRole('button', { name: 'Referencia' }))
    await screen.findByText('Cable UTP Cat 6')

    const panel = screen
      .getByRole('heading', { name: 'Materiales Referencia' })
      .closest('section')!
    expect(
      within(panel).queryByRole('button', { name: /Agregar/ }),
    ).not.toBeInTheDocument()
    expect(
      within(panel).queryByRole('button', { name: /Modificar/ }),
    ).not.toBeInTheDocument()
    expect(
      within(panel).queryByRole('button', { name: /Eliminar/ }),
    ).not.toBeInTheDocument()

    expect(listarReferencia).toHaveBeenCalledWith(1)
    expect(crearReferencia).not.toHaveBeenCalled()
    expect(modificarReferencia).not.toHaveBeenCalled()
    expect(eliminarReferencia).not.toHaveBeenCalled()
  })

  it('en Configuración el panel SÍ ofrece Agregar, Modificar y Eliminar', async () => {
    const user = userEvent.setup()
    renderPagina()

    await user.click(screen.getByRole('button', { name: 'Configuración' }))
    await user.click(await screen.findByRole('button', { name: 'Referencia' }))
    await screen.findByText('Cable UTP Cat 6')

    const panel = screen
      .getByRole('heading', { name: 'Materiales Referencia' })
      .closest('section')!
    expect(
      within(panel).getByRole('button', { name: /Agregar/ }),
    ).toBeInTheDocument()
    expect(
      within(panel).getByRole('button', { name: 'Modificar Cable UTP Cat 6' }),
    ).toBeInTheDocument()
    expect(
      within(panel).getByRole('button', { name: 'Eliminar Cable UTP Cat 6' }),
    ).toBeInTheDocument()
  })
})

describe('cambio de Unidad (REQ-REF-004)', () => {
  it('el panel conserva su estado abierto, recarga la nueva Unidad y descarta el formulario', async () => {
    const user = userEvent.setup()
    renderPagina()

    await user.click(screen.getByRole('button', { name: 'Configuración' }))
    const boton = await screen.findByRole('button', { name: 'Referencia' })
    await user.click(boton)
    await screen.findByText('Cable UTP Cat 6')

    await user.click(screen.getByRole('button', { name: /Agregar/ }))
    expect(
      await screen.findByRole('form', { name: 'Agregar materiales a la Referencia' }),
    ).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '2')

    // El panel sigue abierto (mismo estado) para la NUEVA Unidad…
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    // …muestra las líneas de la Unidad 2…
    await screen.findByText('Fibra drop 1 hilo')
    expect(screen.queryByText('Cable UTP Cat 6')).not.toBeInTheDocument()
    // …y el formulario pendiente quedó descartado (remontaje por Unidad).
    expect(
      screen.queryByRole('form', { name: 'Agregar materiales a la Referencia' }),
    ).not.toBeInTheDocument()
    await waitFor(() => expect(listarReferencia).toHaveBeenCalledWith(2))
  })

  it('el listado distingue líneas por Unidad (nada se mezcla entre Unidades)', async () => {
    const user = userEvent.setup()
    renderPagina()

    await user.click(await screen.findByRole('button', { name: 'Referencia' }))
    await screen.findByText('Cable UTP Cat 6')

    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '2')
    await screen.findByText('Fibra drop 1 hilo')

    await user.selectOptions(screen.getByLabelText('Seleccionar Unidad'), '1')
    await screen.findByText('Cable UTP Cat 6')
    const panel = screen.getByRole('heading', { name: 'Materiales Referencia' }).closest('section')!
    expect(within(panel).queryByText('Fibra drop 1 hilo')).not.toBeInTheDocument()
  })
})
