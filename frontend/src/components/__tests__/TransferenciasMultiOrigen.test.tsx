import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Transferencias from '../../pages/Transferencias'
import { listFibraStock } from '../../services/fibra'
import { stockSeccion } from '../../services/inventory'
import { listEquipos } from '../../services/equipos'
import {
  cancelarMovimiento,
  crearBorrador,
  listMovimientos,
  procesarMovimiento,
} from '../../services/movimientos'

// RF-1, RF-15, RF-16 (REQ-TRFM-001/015/016): carrito multi-origen.

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))
vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({
    data: [
      { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true },
      { almacen_id: 2, nombre: 'Fibra Optica - Paquete', tipo: 'FO_PAQUETE', transferible: true },
      { almacen_id: 3, nombre: 'Fibra Optica - En Uso', tipo: 'FO_EN_USO', transferible: true },
    ],
  }),
}))
vi.mock('../../services/equipos', () => ({
  listEquipos: vi.fn(),
  inventarioEquipo: vi.fn().mockResolvedValue([]),
}))
vi.mock('../../services/inventory', () => ({ stockSeccion: vi.fn() }))
vi.mock('../../services/fibra', () => ({ listFibraStock: vi.fn() }))
vi.mock('../../services/movimientos', () => ({
  listMovimientos: vi.fn(),
  crearBorrador: vi.fn(),
  procesarMovimiento: vi.fn(),
  eliminarBorrador: vi.fn(),
  cancelarMovimiento: vi.fn(),
}))

const filaGeneral = {
  material_id: 10, codigo: 'GEN-1', descripcion: 'Conector General', u_m: 'PZ',
  stock_minimo: null, stock_actual: 100, alerta_stock: false,
}
const filaPaquete = {
  modulo: 'PAQUETE', material_id: 20, codigo: 'FO-1', descripcion: 'Cable Paquete',
  u_m: 'METRO (M)', stock_minimo: null, stock_actual: 50, alerta_stock: false,
}
const filaEnUso = {
  modulo: 'EN_USO', material_id: 30, codigo: 'FO-2', descripcion: 'Cable En Uso',
  u_m: 'METRO (M)', stock_minimo: null, stock_actual: 30, alerta_stock: false,
}

function renderPagina() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <Transferencias />
    </QueryClientProvider>,
  )
  return queryClient
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(stockSeccion).mockResolvedValue([filaGeneral] as never)
  vi.mocked(listFibraStock).mockImplementation((async (modulo: string) =>
    modulo === 'PAQUETE' ? [filaPaquete] : [filaEnUso]) as never)
  vi.mocked(listEquipos).mockResolvedValue([
    { equipo_id: 5, nombre: 'Unidad QA', descripcion: null, is_active: true, integrantes: [] },
  ])
  vi.mocked(listMovimientos).mockResolvedValue([])
  vi.mocked(crearBorrador).mockResolvedValue({ id: 1, tipo_movimiento: 'TEAMS', destino_equipo_id: 5 } as never)
  vi.mocked(procesarMovimiento).mockResolvedValue(undefined)
})

async function agregarDesde(
  user: ReturnType<typeof userEvent.setup>,
  seccion: string,
  descripcion: string,
) {
  const [selSeccion] = await screen.findAllByRole('combobox')
  await user.selectOptions(selSeccion, seccion)
  const celda = await screen.findByText(descripcion, { selector: 'td' })
  await user.click(within(celda.closest('tr') as HTMLElement).getByRole('button', { name: /Agregar/ }))
}

describe('Carrito multi-origen', () => {
  it('RF-1/RF-15 REQ-TRFM-001/015: el carrito conserva líneas de General y FO al cambiar de sección y rotula el origen de cada una', async () => {
    const user = userEvent.setup()
    renderPagina()

    await agregarDesde(user, '1', 'Conector General')
    await agregarDesde(user, '2', 'Cable Paquete')
    await agregarDesde(user, '3', 'Cable En Uso')

    expect(screen.getByText('Carrito (3)')).toBeInTheDocument()
    expect(screen.getByTestId('origen-linea-10')).toHaveTextContent('Inventario General')
    expect(screen.getByTestId('origen-linea-20')).toHaveTextContent('Fibra Óptica - Paquete')
    expect(screen.getByTestId('origen-linea-30')).toHaveTextContent('Fibra Óptica - En Uso')
  })

  it('RF-15: volver a una sección ya usada no duplica ni pierde líneas (material ya agregado deshabilitado)', async () => {
    const user = userEvent.setup()
    renderPagina()

    await agregarDesde(user, '1', 'Conector General')
    await agregarDesde(user, '2', 'Cable Paquete')
    const [selSeccion] = await screen.findAllByRole('combobox')
    await user.selectOptions(selSeccion, '1')
    const celda = await screen.findByText('Conector General', { selector: 'td' })
    expect(within(celda.closest('tr') as HTMLElement).getByRole('button', { name: /Agregar/ })).toBeDisabled()
    expect(screen.getByText('Carrito (2)')).toBeInTheDocument()
  })

  it('RF-16 REQ-TRFM-016: el payload TEAMS envía origen_almacen_id por línea y ninguno en la cabecera', async () => {
    const user = userEvent.setup()
    renderPagina()

    await agregarDesde(user, '1', 'Conector General')
    await agregarDesde(user, '2', 'Cable Paquete')
    await agregarDesde(user, '3', 'Cable En Uso')
    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[1], '5') // Unidad destino
    await user.click(screen.getByRole('button', { name: 'Confirmar TEAMS' }))

    await waitFor(() => expect(crearBorrador).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(crearBorrador).mock.calls[0][0]
    expect(payload).not.toHaveProperty('origen_almacen_id')
    expect(payload.tipo_movimiento).toBe('TEAMS')
    expect(payload.destino_equipo_id).toBe(5)
    expect(payload.detalle).toEqual([
      { material_id: 10, cantidad: 1, origen_almacen_id: 1 },
      { material_id: 20, cantidad: 1, origen_almacen_id: 2 },
      { material_id: 30, cantidad: 1, origen_almacen_id: 3 },
    ])
    await waitFor(() => expect(procesarMovimiento).toHaveBeenCalled())
    expect(vi.mocked(procesarMovimiento).mock.calls[0][0]).toBe(1)
  })

  it('Confirmar permanece deshabilitado sin unidad destino aunque el carrito tenga líneas', async () => {
    const user = userEvent.setup()
    renderPagina()
    await agregarDesde(user, '1', 'Conector General')
    expect(screen.getByRole('button', { name: 'Confirmar TEAMS' })).toBeDisabled()
  })

  it('cambiar de pestaña TEAMS/DEVOL sí vacía el carrito (otro tipo de operación)', async () => {
    const user = userEvent.setup()
    renderPagina()
    await agregarDesde(user, '1', 'Conector General')
    await user.click(screen.getByRole('button', { name: 'DEVOL' }))
    expect(screen.getByText('Carrito (0)')).toBeInTheDocument()
  })

  it('el saldo proyectado de cada línea usa el stock de SU origen', async () => {
    const user = userEvent.setup()
    renderPagina()
    await agregarDesde(user, '1', 'Conector General')
    await agregarDesde(user, '2', 'Cable Paquete')
    const li10 = screen.getByTestId('origen-linea-10').closest('li') as HTMLElement
    const li20 = screen.getByTestId('origen-linea-20').closest('li') as HTMLElement
    expect(li10).toHaveTextContent('Disponible: 100')
    expect(li20).toHaveTextContent('Disponible: 50')
    expect(li10).toHaveTextContent('Saldo estimado después de la operación: 99')
    expect(li20).toHaveTextContent('Saldo estimado después de la operación: 49')
  })
})

describe('Historial e invalidaciones multi-origen', () => {
  const mixto = {
    id: 9, tipo_movimiento: 'TEAMS', estado: 'CONFIRMADO', usuario: 'qa',
    origen_almacen_id: null, destino_almacen_id: null, origen_equipo_id: null,
    destino_equipo_id: 5, observaciones: null,
    detalle: [
      { material_id: 10, cantidad: 1, origen_almacen_id: 1 },
      { material_id: 20, cantidad: 1, origen_almacen_id: 2 },
      { material_id: 30, cantidad: 1, origen_almacen_id: 3 },
    ],
  }

  it('RF-11: una operación mixta es UNA fila con todos sus orígenes', async () => {
    vi.mocked(listMovimientos).mockResolvedValue([mixto] as never)
    renderPagina()
    const fila = (await screen.findByText('9')).closest('tr') as HTMLElement
    expect(fila).toHaveTextContent(
      'Inventario General + Fibra Óptica - Paquete + Fibra Óptica - En Uso → Unidad QA',
    )
    expect(fila).toHaveTextContent('3') // líneas
    expect(screen.getAllByRole('row').filter((r) => r.textContent?.includes('Unidad QA'))).toHaveLength(1)
  })

  it('RF-12: cancelar un mixto invalida el stock de TODOS los orígenes de sus líneas', async () => {
    const user = userEvent.setup()
    vi.mocked(listMovimientos).mockResolvedValue([mixto] as never)
    vi.mocked(cancelarMovimiento).mockResolvedValue({ movimiento_id: 9, estado: 'CANCELADO' } as never)
    const qc = renderPagina()
    const espiar = vi.spyOn(qc, 'invalidateQueries')

    await user.click(await screen.findByRole('button', { name: /Cancelar/ }))
    await user.click(await screen.findByRole('button', { name: 'Confirmar Cancelación' }))

    await waitFor(() => expect(cancelarMovimiento).toHaveBeenCalled())
    await waitFor(() => {
      const claves = espiar.mock.calls.map((c) => JSON.stringify((c[0] as { queryKey: unknown }).queryKey))
      expect(claves).toEqual(
        expect.arrayContaining([
          '["stock",1]', '["stock",2]', '["stock",3]',
          '["fibra","PAQUETE"]', '["fibra","EN_USO"]',
        ]),
      )
    })
  })

  it('un movimiento con origen solo en la cabecera (legado) sigue mostrando su sección', async () => {
    vi.mocked(listMovimientos).mockResolvedValue([
      { ...mixto, id: 4, origen_almacen_id: 2, detalle: [{ material_id: 20, cantidad: 1 }] },
    ] as never)
    renderPagina()
    const fila = (await screen.findByText('4')).closest('tr') as HTMLElement
    expect(fila).toHaveTextContent('Fibra Óptica - Paquete → Unidad QA')
  })
})
