import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  QueryClient,
  QueryClientProvider,
  QueryObserver,
} from '@tanstack/react-query'
import Transferencias from '../../pages/Transferencias'
import { NavigationContext } from '../../hooks/navigationContext'
import { listFibraStock } from '../../services/fibra'
import { stockSeccion } from '../../services/inventory'
import { listEquipos, inventarioEquipo } from '../../services/equipos'
import {
  listMovimientos,
  crearBorrador,
  procesarMovimiento,
  cancelarMovimiento,
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
        nombre: 'Inventario FO',
        tipo: 'FO',
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
  getResumenGeneral: vi
    .fn()
    .mockResolvedValue({ valor_total: 0, moneda: 'MXN' }),
}))

vi.mock('../../services/fibra', () => ({
  listFibraStock: vi.fn().mockResolvedValue([
    {
      material_id: 1,
      codigo: 'FO-1',
      descripcion: 'Cable FO',
      u_m: 'PZ',
      stock_minimo: null,
      stock_actual: 10,
      valor_unitario: 12.5,
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

describe('Transferencias — Inventario FO único (REQ-TRF-001/002)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(listFibraStock as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
          material_id: 1,
        codigo: 'FO-1',
        descripcion: 'Cable FO',
        u_m: 'PZ',
        stock_minimo: null,
        stock_actual: 10,
        valor_unitario: 12.5,
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

  it('direcciona la consulta de inventario de origen a /fibra (sin módulo) al elegir el Inventario FO', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Sección Origen → Inventario FO

    await waitFor(() => {
      expect(listFibraStock).toHaveBeenCalledTimes(1)
    })
    expect(listFibraStock).toHaveBeenCalledWith()
    expect(stockSeccion).not.toHaveBeenCalled()

    // La fila FO llega al listado de materiales disponibles
    expect(await screen.findByText('Cable FO')).toBeInTheDocument()
  })

  it("Inventario FO invalida ['fibra'] tras procesar un TEAMS desde el Inventario FO", async () => {
    const user = userEvent.setup()
    const queryClient = renderConQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Origen Inventario FO
    await user.selectOptions(combos[1], '5') // Equipo destino

    const agregar = await screen.findByRole('button', { name: /Agregar/ })
    await user.click(agregar)

    await user.type(
      screen.getByLabelText(/Motivo \/ Observaciones/),
      'Entrega FO QA',
    )
    await user.click(screen.getByRole('button', { name: 'Confirmar Transferencia' }))

    // procesar → invalidarTrasConfirmarMovimiento → refetch de ['fibra']
    await waitFor(() => {
      expect(listFibraStock).toHaveBeenCalledTimes(2)
    })
    expect(invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)).toContainEqual([
      'fibra',
    ])
    expect(listFibraStock).toHaveBeenLastCalledWith()
  })

  async function confirmarTeams(user: ReturnType<typeof userEvent.setup>) {
    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Origen Inventario FO
    await user.selectOptions(combos[1], '5') // Equipo destino
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))
    await user.type(
      screen.getByLabelText(/Motivo \/ Observaciones/),
      'Entrega QA',
    )
    await user.click(screen.getByRole('button', { name: 'Confirmar Transferencia' }))
  }

  const borradorTeams = {
    id: 1,
    tipo_movimiento: 'TEAMS',
    estado: 'BORRADOR',
    destino_equipo_id: 5,
  }

  it('REQ-P2-REP-003: tras Confirmar Transferencia exitoso informa el Acta de Entrega y ofrece ir a Reportes > Entrega del equipo', async () => {
    const user = userEvent.setup()
    const navigate = vi.fn()
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue(borradorTeams)
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    render(
      <QueryClientProvider client={queryClient}>
        <NavigationContext.Provider value={navigate}>
          <Transferencias />
        </NavigationContext.Provider>
      </QueryClientProvider>,
    )

    expect(
      screen.queryByText('Acta de Entrega generada'),
    ).not.toBeInTheDocument()

    await confirmarTeams(user)

    expect(await screen.findByText('Acta de Entrega generada')).toBeInTheDocument()
    expect(screen.getByText(/hacia Equipo QA/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Ir a Reportes > Entrega' }),
    )
    expect(navigate).toHaveBeenCalledWith({
      page: 'reportes',
      sub: 'entrega',
      equipoId: 5,
    })
  })

  it('no anuncia acta si el servidor rechaza la confirmación', async () => {
    const user = userEvent.setup()
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue(borradorTeams)
    ;(procesarMovimiento as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('stock cambió'),
    )
    renderConQueryClient()

    await confirmarTeams(user)

    await waitFor(() => {
      expect(procesarMovimiento).toHaveBeenCalled()
    })
    expect(
      screen.queryByText('Acta de Entrega generada'),
    ).not.toBeInTheDocument()
  })

  it('REQ-P2-REP-003: tras Confirmar Transferencia invalida las actas de Entrega y recarga el listado montado sin recargar la página', async () => {
    const user = userEvent.setup()
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue(borradorTeams)
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    // «Reportes > Entrega» montado en otra parte de la app: un observer activo
    // sobre la clave del listado de actas de Entrega.
    const listarActas = vi.fn().mockResolvedValue([])
    const observer = new QueryObserver(queryClient, {
      queryKey: ['reportes', 'actas', 'entrega', {}],
      queryFn: listarActas,
    })
    const unsubscribe = observer.subscribe(() => undefined)
    await waitFor(() => expect(listarActas).toHaveBeenCalledTimes(1))

    render(
      <QueryClientProvider client={queryClient}>
        <Transferencias />
      </QueryClientProvider>,
    )
    await confirmarTeams(user)

    await waitFor(() => expect(listarActas).toHaveBeenCalledTimes(2))
    const claves = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)
    expect(claves).toEqual(
      expect.arrayContaining([
        ['movimientos'],
        ['stock'],
        ['fibra'],
        ['equipo'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
        ['reportes', 'actas', 'entrega'],
      ]),
    )
    // El aviso de acta sigue funcionando.
    expect(await screen.findByText('Acta de Entrega generada')).toBeInTheDocument()
    unsubscribe()
  })

  it('no invalida actas ni stocks si el servidor rechaza la confirmación', async () => {
    const user = userEvent.setup()
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue(borradorTeams)
    ;(procesarMovimiento as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('stock cambió'),
    )
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    render(
      <QueryClientProvider client={queryClient}>
        <Transferencias />
      </QueryClientProvider>,
    )

    await confirmarTeams(user)

    await waitFor(() => expect(procesarMovimiento).toHaveBeenCalled())
    await waitFor(() =>
      expect(invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)).toContainEqual([
        'movimientos',
      ]),
    )
    const claves = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)
    expect(claves).not.toContainEqual(['reportes', 'actas', 'entrega'])
    expect(claves).not.toContainEqual(['stock'])
  })

  it('un TEAMS confirmado desde el historial (borrador) también anuncia el acta e invalida las actas de Entrega', async () => {
    const user = userEvent.setup()
    ;(listMovimientos as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 77,
        tipo_movimiento: 'TEAMS',
        estado: 'BORRADOR',
        usuario: 'demo-operador',
        origen_almacen_id: 1,
        destino_almacen_id: null,
        origen_equipo_id: null,
        destino_equipo_id: 5,
        observaciones: 'x',
        detalle: [{ material_id: 1, cantidad: 1 }],
      },
    ])
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    render(
      <QueryClientProvider client={queryClient}>
        <Transferencias />
      </QueryClientProvider>,
    )

    await user.click(await screen.findByRole('button', { name: 'Procesar' }))

    expect(
      (procesarMovimiento as ReturnType<typeof vi.fn>).mock.calls[0][0],
    ).toBe(77)
    expect(await screen.findByText('Acta de Entrega generada')).toBeInTheDocument()
    await waitFor(() =>
      expect(invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)).toContainEqual([
        'reportes',
        'actas',
        'entrega',
      ]),
    )
  })

  it('REQ-ERG-007: Confirmar Transferencia permanece habilitado con el motivo vacío y envía observaciones null', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Origen Inventario FO
    await user.selectOptions(combos[1], '5') // Equipo destino
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))

    const confirmar = screen.getByRole('button', { name: 'Confirmar Transferencia' })
    expect(confirmar).toBeEnabled()
    await user.click(confirmar)

    await waitFor(() => expect(crearBorrador).toHaveBeenCalledTimes(1))
    const payload = (crearBorrador as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(payload.observaciones).toBeNull()
  })

  it('REQ-ERG-007: Confirmar Devolución permanece habilitado con el motivo vacío y envía observaciones null', async () => {
    const user = userEvent.setup()
    ;(inventarioEquipo as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        equipo_id: 5,
        material_id: 1,
        codigo: 'FO-1',
        descripcion: 'Cable FO',
        u_m: 'PZ',
        stock_minimo: null,
        stock_actual: 3,
        valor_unitario: 12.5,
        alerta_stock: false,
        ultimo_movimiento_id: null,
      },
    ])
    renderConQueryClient()

    await user.click(screen.getByRole('button', { name: 'DEVOL' }))
    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '5') // Equipo origen
    await user.selectOptions(combos[1], '1') // Sección destino GENERAL
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))

    const confirmar = screen.getByRole('button', { name: 'Confirmar Devolución' })
    expect(confirmar).toBeEnabled()
    await user.click(confirmar)

    await waitFor(() => expect(crearBorrador).toHaveBeenCalledTimes(1))
    const payload = (crearBorrador as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(payload.tipo_movimiento).toBe('DEVOL')
    expect(payload.observaciones).toBeNull()
  })

  it('REQ-ERG-008: cancelación con motivo vacío permanece habilitada y envía motivo null', async () => {
    const user = userEvent.setup()
    ;(listMovimientos as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 9,
        tipo_movimiento: 'TEAMS',
        estado: 'CONFIRMADO',
        usuario: 'demo-operador',
        origen_almacen_id: 1,
        destino_almacen_id: null,
        origen_equipo_id: null,
        destino_equipo_id: 5,
        observaciones: null,
        detalle: [{ material_id: 1, cantidad: 1 }],
      },
    ])
    ;(cancelarMovimiento as ReturnType<typeof vi.fn>).mockResolvedValue({
      movimiento_id: 9,
      estado: 'CANCELADO',
    })
    renderConQueryClient()

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }))

    const confirmar = screen.getByRole('button', {
      name: 'Confirmar Cancelación',
    })
    expect(confirmar).toBeEnabled()
    await user.click(confirmar)

    await waitFor(() =>
      expect(cancelarMovimiento).toHaveBeenCalledWith(9, null),
    )
  })

  it('RF-9: un movimiento histórico con origen_almacen_id fuera de las secciones transferibles se rotula «Inventario FO»', async () => {
    ;(listMovimientos as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 31,
        tipo_movimiento: 'TEAMS',
        estado: 'CONFIRMADO',
        usuario: 'demo-operador',
        origen_almacen_id: 99, // FO_PAQUETE histórico: no figura en transferibles
        destino_almacen_id: null,
        origen_equipo_id: null,
        destino_equipo_id: 5,
        observaciones: null,
        detalle: [{ material_id: 1, cantidad: 1 }],
      },
    ])
    renderConQueryClient()

    const fila = (await screen.findByText('31')).closest('tr') as HTMLElement
    expect(fila).toHaveTextContent('Inventario FO → Equipo QA')
    expect(fila).not.toHaveTextContent('Sección 99')
  })

  it('RF-9/RF-10: el selector de Sección Origen ofrece solo «Inventario General» e «Inventario FO» (sin «Paquete»/«En Uso»)', async () => {
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    const opciones = Array.from(combos[0].querySelectorAll('option')).map(
      (o) => o.textContent?.trim(),
    )
    expect(opciones.filter((t) => t === 'Inventario FO')).toHaveLength(1)
    expect(opciones).toContain('Inventario General')
    for (const texto of opciones) {
      expect(texto).not.toMatch(/paquete|en uso/i)
    }
    // Ningún selector de la pantalla de TRANSF/Devolución los ofrece.
    for (const combo of combos) {
      for (const o of Array.from(combo.querySelectorAll('option'))) {
        expect(o.textContent).not.toMatch(/paquete|en uso/i)
      }
    }
  })

  it('RF-4/RF-5: tras confirmar una TRANSF se invalida el Valor Total [\'inventario\', \'resumen-general\']', async () => {
    const user = userEvent.setup()
    ;(crearBorrador as ReturnType<typeof vi.fn>).mockResolvedValue(borradorTeams)
    const queryClient = renderConQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await confirmarTeams(user)

    await waitFor(() =>
      expect(invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)).toContainEqual([
        'inventario',
        'resumen-general',
      ]),
    )
  })

  it('RF-4/RF-5: cancelar un movimiento invalida el Valor Total y ["fibra"]', async () => {
    const user = userEvent.setup()
    ;(listMovimientos as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 9,
        tipo_movimiento: 'TEAMS',
        estado: 'CONFIRMADO',
        usuario: 'demo-operador',
        origen_almacen_id: 2,
        destino_almacen_id: null,
        origen_equipo_id: null,
        destino_equipo_id: 5,
        observaciones: null,
        detalle: [{ material_id: 1, cantidad: 1 }],
      },
    ])
    ;(cancelarMovimiento as ReturnType<typeof vi.fn>).mockResolvedValue({
      movimiento_id: 9,
      estado: 'CANCELADO',
    })
    const queryClient = renderConQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await user.click(await screen.findByRole('button', { name: 'Cancelar' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar Cancelación' }))

    await waitFor(() => expect(cancelarMovimiento).toHaveBeenCalled())
    await waitFor(() => {
      const claves = invalidateSpy.mock.calls.map((c) => c[0]?.queryKey)
      expect(claves).toEqual(
        expect.arrayContaining([
          ['movimientos'],
          ['auditoria'],
          ['secciones'],
          ['inventario', 'resumen-general'],
          ['stock', 2],
          ['fibra'],
          ['equipo', 5],
        ]),
      )
    })
  })

  it('RF-6: el carrito acepta una cantidad decimal (2.5) y la envía como cantidad: 2.5 en el borrador', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2') // Origen Inventario FO
    await user.selectOptions(combos[1], '5') // Equipo destino
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))

    const input = screen.getByLabelText('Cantidad de Cable FO')
    expect(input).toHaveAttribute('type', 'number')
    expect(input).toHaveAttribute('step', '0.001')
    expect(input).toHaveAttribute('min', '0.001')
    await user.clear(input)
    await user.type(input, '2.5')
    expect(input).toHaveValue(2.5)

    const confirmar = screen.getByRole('button', { name: 'Confirmar Transferencia' })
    expect(confirmar).toBeEnabled()
    await user.click(confirmar)

    await waitFor(() => expect(crearBorrador).toHaveBeenCalledTimes(1))
    const payload = (crearBorrador as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(payload.detalle).toEqual([
      { material_id: 1, cantidad: 2.5, origen_almacen_id: 2 },
    ])
  })

  it('RF-6: una cantidad con más de 3 decimales deshabilita Confirmar', async () => {
    const user = userEvent.setup()
    renderConQueryClient()

    const combos = await screen.findAllByRole('combobox')
    await user.selectOptions(combos[0], '2')
    await user.selectOptions(combos[1], '5')
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))

    const input = screen.getByLabelText('Cantidad de Cable FO')
    await user.clear(input)
    await user.type(input, '1.2345')
    expect(
      screen.getByRole('button', { name: 'Confirmar Transferencia' }),
    ).toBeDisabled()
  })
})
