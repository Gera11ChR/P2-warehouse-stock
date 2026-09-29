import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Transferencias from '../../pages/Transferencias'
import { listFibraStock } from '../../services/fibra'
import { stockSeccion } from '../../services/inventory'
import { listEquipos, inventarioEquipo } from '../../services/equipos'
import {
  listMovimientos,
  crearBorrador,
  procesarMovimiento,
} from '../../services/movimientos'

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))

vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({
    data: [
      {
        almacen_id: 1,
        nombre: 'Inventario General',
        tipo: 'GENERAL',
        transferible: true,
      },
      {
        almacen_id: 2,
        nombre: 'Fibra Optica - Paquete',
        tipo: 'FO_PAQUETE',
        transferible: true,
      },
      {
        almacen_id: 3,
        nombre: 'Fibra Optica - En Uso',
        tipo: 'FO_EN_USO',
        transferible: true,
      },
    ],
  }),
}))

vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn().mockResolvedValue([
    {
      equipo_id: 5,
      nombre: 'Equipo QA',
      descripcion: null,
      is_active: true,
      integrantes: [],
    },
  ]),
  inventarioEquipo: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../services/inventory', () => ({
  stockSeccion: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../services/fibra', () => ({
  listFibraStock: vi.fn().mockResolvedValue([
    {
      modulo: 'PAQUETE',
      material_id: 1,
      codigo: 'FO-1',
      descripcion: 'Cable FO',
      u_m: 'PZ',
      stock_minimo: null,
      stock_actual: 10,
      alerta_stock: false,
    },
  ]),
}))

vi.mock('../../services/movimientos', () => ({
  listMovimientos: vi.fn().mockResolvedValue([]),
  crearBorrador: vi.fn().mockResolvedValue({ id: 1 }),
  procesarMovimiento: vi.fn().mockResolvedValue(undefined),
  eliminarBorrador: vi.fn(),
  cancelarMovimiento: vi.fn(),
}))

function renderConQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <Transferencias />
    </QueryClientProvider>,
  )
  return queryClient
}

describe('Transferencias — origen FO (REQ-TRF-001/002)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        modulo: 'PAQUETE',
        material_id: 1,
        codigo: 'FO-1',
        descripcion: 'Cable FO',
        u_m: 'PZ',
        stock_minimo: null,
        stock_actual: 10,
        alerta_stock: false,
      },
    ])
    ;(stockSeccion as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(listEquipos as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        equipo_id: 5,
        nombre: 'Equipo QA',
        descripcion: null,
        is_active: true,
        integrantes: [],
      },
    ])
    ;(inventarioEquipo as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(listMovimientos as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue({ id: 1 })
    ;(procesarMovimiento as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    )
  })

  it('direcciona la consulta de inventario de origen a /fibra/{modulo} al elegir una raíz FO', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Sección Origen → FO_PAQUETE

    await waitFor(() => {
      expect(listFibraStock).toHaveBeenCalledWith('PAQUETE')
    })
    expect(stockSeccion).not.toHaveBeenCalled()

    // La fila FO llega al listado de materiales disponibles
    expect(await screen.findByText('Cable FO')).toBeInTheDocument()
  })

  it('invalida la vista FO tras procesar un TEAMS desde FO', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Origen FO_PAQUETE
    await user.selectOptions(combos[1], '5') // Equipo destino

    const agregar = await screen.findByRole('button', { name: /Agregar/ })
    await user.click(agregar)

    await user.type(
      screen.getByLabelText(/Motivo \/ Observaciones/),
      'Despliegue FO QA',
    )
    await user.click(screen.getByRole('button', { name: 'Confirmar TEAMS' }))

    // procesar → invalidarInventarios → refetch de ['fibra', 'PAQUETE']
    await waitFor(() => {
      expect(listFibraStock).toHaveBeenCalledTimes(2)
    })
  })
})
