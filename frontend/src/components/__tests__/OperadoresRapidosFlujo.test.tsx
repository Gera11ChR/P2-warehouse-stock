import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FibraOptica from '../../pages/FibraOptica'
import SeccionGeneral from '../../pages/SeccionGeneral'
import { ToastProvider } from '../ToastProvider'
import { listFibraStock } from '../../services/fibra'
import {
  listSecciones,
  listSeccionesTransferibles,
  getResumenGeneral,
  moverMaterial,
  stockSeccion,
  sumarCantidad,
} from '../../services/inventory'
import { listCatalog, listCategorias, listUms } from '../../services/catalog'

// ============================================================================
// Flujo +Cantidad / Mover de punta a punta a nivel de componente: páginas,
// hooks y diálogos REALES; solo la capa HTTP (services/*) está mockeada.
// ============================================================================

vi.mock('../../services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/catalog')>()),
  listCatalog: vi.fn(),
  listCategorias: vi.fn(),
  listUms: vi.fn(),
}))
vi.mock('../../services/fibra', () => ({
  listFibraStock: vi.fn(),
  updateFibraMaterial: vi.fn(),
  eliminarFibraMaterial: vi.fn(),
}))
vi.mock('../../services/inventory', () => ({
  listSecciones: vi.fn(),
  stockSeccion: vi.fn(),
  listSeccionesTransferibles: vi.fn(),
  sumarCantidad: vi.fn(),
  moverMaterial: vi.fn(),
  getResumenGeneral: vi.fn(),
}))

const fn = <T extends (...a: never[]) => unknown>(f: T) =>
  f as unknown as ReturnType<typeof vi.fn>

const SECCIONES_TRANSFERIBLES = [
  { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true },
  { almacen_id: 2, nombre: 'Inventario FO', tipo: 'FO', transferible: true },
]

const filaFo = (stock: number) => ({
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: stock,
  valor_unitario: 0,
  alerta_stock: false,
})

const filaGeneral = (stock: number) => ({
  material_id: 4,
  codigo: 'CON-1',
  descripcion: 'ACOPLADORES',
  u_m: 'PZ',
  stock_minimo: null,
  stock_actual: stock,
  valor_unitario: 0,
  alerta_stock: false,
})

/** Error con la forma que entrega axios (response.status + data). */
const httpError = (status: number, message: string) => ({
  isAxiosError: true,
  response: { status, data: { error: { code: 'E', message } } },
})
const redError = () => ({ isAxiosError: true, message: 'Network Error' })

function renderConProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>,
  )
  const claves = () => invalidate.mock.calls.map((c) => c[0]?.queryKey)
  return { queryClient, claves }
}

const drawer = () => screen.getByRole('complementary', { name: 'Detalle del Material' })

beforeEach(() => {
  vi.clearAllMocks()
  fn(listCatalog).mockResolvedValue({ start_index: 1, materiales: [] })
  fn(listCategorias).mockResolvedValue([])
  fn(listUms).mockResolvedValue([{ id: 1, nombre: 'PZ', is_active: true }])
  fn(getResumenGeneral).mockResolvedValue({ valor_total: 0, moneda: 'MXN' })
  fn(listSeccionesTransferibles).mockResolvedValue(SECCIONES_TRANSFERIBLES)
  fn(listSecciones).mockResolvedValue([
    { almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', is_active: true },
  ])
})

// ----------------------------------------------------------------------------
// INVENTARIO FO (único, sin módulos)
// ----------------------------------------------------------------------------

describe('Flujo +Cantidad en Inventario FO', () => {
  async function abrirSumar(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    return screen.findByRole('dialog', { name: '+ Cantidad' })
  }

  it('éxito: envía el payload del contrato con clave de idempotencia, cierra tras 200, toast con el stock del SERVIDOR y recarga la fila', async () => {
    const user = userEvent.setup()
    fn(listFibraStock)
      .mockResolvedValueOnce([filaFo(10)])
      .mockResolvedValue([filaFo(17)])
    // El servidor responde 17 (≠ 10 + 5): la UI debe mostrar lo que dice el servidor.
    fn(sumarCantidad).mockResolvedValue({
      destino: 'FO',
      material_id: 1,
      stock_nuevo: 17,
      reenvio_idempotente: false,
    })
    const { claves } = renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '5')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 5 PZ a FO-1/ }))

    await waitFor(() => expect(sumarCantidad).toHaveBeenCalledTimes(1))
    const payload = fn(sumarCantidad).mock.calls[0][0]
    expect(payload).toEqual({
      destino: 'FO',
      material_id: 1,
      cantidad: 5,
      clave_idempotencia: expect.stringMatching(/^sumar-.{8,}/),
    })
    // Cierra solo tras la respuesta 200.
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '+ Cantidad' })).not.toBeInTheDocument(),
    )
    // Toast con el stock devuelto por el servidor.
    expect(await screen.findByText(/Stock en Inventario FO: 17 PZ/)).toBeInTheDocument()
    // Recarga automática de stock (y auditoría) tras la operación.
    expect(claves()).toEqual(
      expect.arrayContaining([['fibra'], ['auditoria'], ['inventario', 'resumen-general']]),
    )
    await waitFor(() => expect(listFibraStock).toHaveBeenCalledTimes(2))
    // El panel de detalle refleja el stock PERSISTIDO recargado.
    await waitFor(() =>
      expect(within(drawer()).getByText('17')).toBeInTheDocument(),
    )
  })

  it('mientras espera la respuesta bloquea el envío (sin doble submit) y no cierra', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    let resolver!: (v: unknown) => void
    fn(sumarCantidad).mockReturnValue(
      new Promise((r) => {
        resolver = r
      }),
    )
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '2')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 2 PZ/ }))

    const procesando = await within(dialogo).findByRole('button', { name: /Procesando/ })
    expect(procesando).toBeDisabled()
    expect(screen.getByRole('dialog', { name: '+ Cantidad' })).toBeInTheDocument()
    expect(sumarCantidad).toHaveBeenCalledTimes(1)

    resolver({ destino: 'FO', material_id: 1, stock_nuevo: 12, reenvio_idempotente: false })
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '+ Cantidad' })).not.toBeInTheDocument(),
    )
  })

  it('400: el diálogo permanece abierto con el error traducido y onEditar lo limpia', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(sumarCantidad).mockRejectedValue(httpError(400, 'cantidad debe ser mayor que cero'))
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '3')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 3 PZ/ }))

    const alerta = await within(dialogo).findByRole('alert')
    expect(alerta).toHaveTextContent(/La cantidad debe ser un número mayor que 0/)
    // El mensaje crudo del servidor nunca se muestra.
    expect(alerta).not.toHaveTextContent('cantidad debe ser mayor que cero')
    expect(screen.getByRole('dialog', { name: '+ Cantidad' })).toBeInTheDocument()

    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '1')
    await waitFor(() =>
      expect(within(dialogo).queryByRole('alert')).not.toBeInTheDocument(),
    )
  })

  it.each([
    [404, /no existe, está inactivo o aún no tiene registro/],
    [409, /entra en conflicto con el estado actual|Hay más de un Inventario General/],
    [422, /datos de la operación no son válidos|no es válida/],
    [403, /No tienes permiso/],
  ])('%i: muestra el error traducido y mantiene el diálogo', async (status, patron) => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(sumarCantidad).mockRejectedValue(httpError(status, 'detalle interno'))
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '1')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 1 PZ/ }))

    expect(await within(dialogo).findByRole('alert')).toHaveTextContent(patron)
    expect(screen.getByRole('dialog', { name: '+ Cantidad' })).toBeInTheDocument()
  })

  it('error "desconocido" (sin respuesta): el reintento reutiliza LA MISMA clave; reabrir genera una nueva', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(sumarCantidad)
      .mockRejectedValueOnce(redError())
      .mockResolvedValueOnce({
        destino: 'FO',
          material_id: 1,
        stock_nuevo: 15,
        reenvio_idempotente: true,
      })
      .mockResolvedValue({
        destino: 'FO',
          material_id: 1,
        stock_nuevo: 20,
        reenvio_idempotente: false,
      })
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '5')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 5 PZ/ }))

    expect(await within(dialogo).findByRole('alert')).toHaveTextContent(
      /no sabemos si la operación se aplicó/,
    )
    // Reintento sin cambiar nada.
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 5 PZ/ }))

    await waitFor(() => expect(sumarCantidad).toHaveBeenCalledTimes(2))
    const [p1, p2] = fn(sumarCantidad).mock.calls.map((c) => c[0])
    expect(p2.clave_idempotencia).toBe(p1.clave_idempotencia)
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '+ Cantidad' })).not.toBeInTheDocument(),
    )
    // Reenvío idempotente informado como tal (con el stock del servidor).
    expect(await screen.findByText(/ya estaba registrada \(no se duplicó\)/)).toBeInTheDocument()

    // Nueva apertura → nueva clave.
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    const nuevo = await screen.findByRole('dialog', { name: '+ Cantidad' })
    await user.type(within(nuevo).getByLabelText('Cantidad a sumar'), '5')
    await user.click(within(nuevo).getByRole('button', { name: /Sumar 5 PZ/ }))
    await waitFor(() => expect(sumarCantidad).toHaveBeenCalledTimes(3))
    const p3 = fn(sumarCantidad).mock.calls[2][0]
    expect(p3.clave_idempotencia).not.toBe(p1.clave_idempotencia)
  })

  it('un rechazo definitivo (400) también recarga el stock (pantalla posiblemente obsoleta)', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(sumarCantidad).mockRejectedValue(httpError(400, 'x'))
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirSumar(user)
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '3')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 3 PZ/ }))

    await within(dialogo).findByRole('alert')
    await waitFor(() => expect(listFibraStock).toHaveBeenCalledTimes(2))
  })
})

describe('Flujo Mover en Inventario FO (FO → General)', () => {
  async function abrirMover(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByText('Cable FO'))
    await user.click(screen.getByRole('button', { name: /Mover/ }))
    return screen.findByRole('dialog', { name: 'Mover' })
  }

  it('éxito: payload origen FO → GENERAL, toast con stock_origen y stock_destino del servidor, recarga de ambos extremos', async () => {
    const user = userEvent.setup()
    fn(listFibraStock)
      .mockResolvedValueOnce([filaFo(10)])
      .mockResolvedValue([filaFo(6)])
    fn(moverMaterial).mockResolvedValue({
      material_id: 1,
      origen: 'FO',
      destino: 'GENERAL',
      stock_origen: 6,
      stock_destino: 31,
      reenvio_idempotente: false,
    })
    const { claves } = renderConProviders(<FibraOptica />)

    const dialogo = await abrirMover(user)
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '1')
    const cantidad = within(dialogo).getByLabelText('Cantidad a mover')
    await user.clear(cantidad)
    await user.type(cantidad, '4')
    await user.click(
      within(dialogo).getByRole('button', { name: /Mover 4 PZ a Inventario General/ }),
    )

    await waitFor(() => expect(moverMaterial).toHaveBeenCalledTimes(1))
    expect(fn(moverMaterial).mock.calls[0][0]).toEqual({
      origen: 'FO',
      destino: 'GENERAL',
      material_id: 1,
      cantidad: 4,
      clave_idempotencia: expect.stringMatching(/^mover-.{8,}/),
    })
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Mover' })).not.toBeInTheDocument(),
    )
    expect(
      await screen.findByText(
        /Stock en Inventario FO: 6 PZ; en Inventario General: 31 PZ/,
      ),
    ).toBeInTheDocument()
    // Origen (Inventario FO) y destino (General) se recargan + auditoría + Valor Total.
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['fibra'],
        ['stock'],
        ['auditoria'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['fibra', 'PAQUETE'])
    await waitFor(() => expect(listFibraStock).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(within(drawer()).getByText('6')).toBeInTheDocument())
  })

  it('FO → FO no se ofrece: desde Inventario FO solo se puede elegir Inventario General', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirMover(user)
    const opciones = within(within(dialogo).getByLabelText('Inventario destino'))
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['— Selecciona destino —', 'Inventario General'])
    expect(within(dialogo).getByText(/Origen: Inventario FO/)).toBeInTheDocument()
    expect(moverMaterial).not.toHaveBeenCalled()
  })

  it('Mover con cantidad decimal parcial (2.5) envía cantidad 2.5 y muestra el stock decimal del servidor', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10.5)])
    fn(moverMaterial).mockResolvedValue({
      material_id: 1,
      origen: 'FO',
      destino: 'GENERAL',
      stock_origen: 8,
      stock_destino: 2.5,
      reenvio_idempotente: false,
    })
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirMover(user)
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '1')
    const cantidad = within(dialogo).getByLabelText('Cantidad a mover')
    expect(cantidad).toHaveValue('10.5')
    await user.clear(cantidad)
    await user.type(cantidad, '2.5')
    await user.click(
      within(dialogo).getByRole('button', { name: /Mover 2.5 PZ a Inventario General/ }),
    )

    await waitFor(() => expect(moverMaterial).toHaveBeenCalledTimes(1))
    expect(fn(moverMaterial).mock.calls[0][0]).toMatchObject({
      origen: 'FO',
      destino: 'GENERAL',
      cantidad: 2.5,
    })
    expect(
      await screen.findByText(/Stock en Inventario FO: 8 PZ; en Inventario General: 2.5 PZ/),
    ).toBeInTheDocument()
  })

  it.each([
    [400, /supera el stock disponible en el inventario de origen/],
    [409, /entra en conflicto|Hay más de un Inventario General|No hay un Inventario General activo/],
    [422, /datos de la operación no son válidos|inventario destino debe ser distinto/],
  ])('%i: error traducido en el diálogo, sin cerrarlo', async (status, patron) => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(moverMaterial).mockRejectedValue(
      httpError(status, status === 400 ? 'stock insuficiente en origen' : 'detalle'),
    )
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirMover(user)
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '1')
    await user.click(within(dialogo).getByRole('button', { name: /Mover 10 PZ/ }))

    expect(await within(dialogo).findByRole('alert')).toHaveTextContent(patron)
    expect(screen.getByRole('dialog', { name: 'Mover' })).toBeInTheDocument()

    // Cambiar el destino (onEditar) limpia el error obsoleto.
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '')
    await waitFor(() =>
      expect(within(dialogo).queryByRole('alert')).not.toBeInTheDocument(),
    )
  })

  it('error de red → reintento con la MISMA clave', async () => {
    const user = userEvent.setup()
    fn(listFibraStock).mockResolvedValue([filaFo(10)])
    fn(moverMaterial)
      .mockRejectedValueOnce(redError())
      .mockResolvedValue({
        material_id: 1,
        origen: 'FO',
          destino: 'GENERAL',
        stock_origen: 0,
        stock_destino: 10,
        reenvio_idempotente: true,
      })
    renderConProviders(<FibraOptica />)

    const dialogo = await abrirMover(user)
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '1')
    await user.click(within(dialogo).getByRole('button', { name: /Mover 10 PZ/ }))
    await within(dialogo).findByRole('alert')
    await user.click(within(dialogo).getByRole('button', { name: /Mover 10 PZ/ }))

    await waitFor(() => expect(moverMaterial).toHaveBeenCalledTimes(2))
    const [p1, p2] = fn(moverMaterial).mock.calls.map((c) => c[0])
    expect(p2.clave_idempotencia).toBe(p1.clave_idempotencia)
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Mover' })).not.toBeInTheDocument(),
    )
  })
})

// ----------------------------------------------------------------------------
// INVENTARIO GENERAL
// ----------------------------------------------------------------------------

describe('Flujo +Cantidad / Mover en Inventario General', () => {
  it('+Cantidad: payload GENERAL (sin módulo), toast del servidor y recarga de ["stock"]', async () => {
    const user = userEvent.setup()
    fn(stockSeccion)
      .mockResolvedValueOnce([filaGeneral(12)])
      .mockResolvedValue([filaGeneral(25)])
    fn(sumarCantidad).mockResolvedValue({
      destino: 'GENERAL',
      material_id: 4,
      stock_nuevo: 25,
      reenvio_idempotente: false,
    })
    const { claves } = renderConProviders(<SeccionGeneral globalSearch="" />)

    await user.click(await screen.findByText('ACOPLADORES'))
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Cantidad' })
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '13')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 13 PZ a CON-1/ }))

    await waitFor(() => expect(sumarCantidad).toHaveBeenCalledTimes(1))
    const payload = fn(sumarCantidad).mock.calls[0][0]
    expect(payload).toEqual({
      destino: 'GENERAL',
      material_id: 4,
      cantidad: 13,
      clave_idempotencia: expect.stringMatching(/^sumar-/),
    })
    expect(payload).not.toHaveProperty('modulo')
    expect(payload).not.toHaveProperty('destino_modulo')
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '+ Cantidad' })).not.toBeInTheDocument(),
    )
    expect(await screen.findByText(/Stock en Inventario General: 25 PZ/)).toBeInTheDocument()
    expect(claves()).toContainEqual(['stock'])
    await waitFor(() => expect(stockSeccion).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(within(drawer()).getByText('25')).toBeInTheDocument())
  })

  it('Mover General → Inventario FO: recarga ["stock"] y ["fibra"]; 409 mantiene el diálogo', async () => {
    const user = userEvent.setup()
    fn(stockSeccion).mockResolvedValue([filaGeneral(12)])
    fn(moverMaterial)
      .mockRejectedValueOnce(httpError(409, 'Existe más de una sección GENERAL activa'))
      .mockResolvedValue({
        material_id: 4,
        origen: 'GENERAL',
        destino: 'FO',
        stock_origen: 2,
        stock_destino: 10,
        reenvio_idempotente: false,
      })
    const { claves } = renderConProviders(<SeccionGeneral globalSearch="" />)

    await user.click(await screen.findByText('ACOPLADORES'))
    await user.click(screen.getByRole('button', { name: /Mover/ }))
    const dialogo = await screen.findByRole('dialog', { name: 'Mover' })
    await user.selectOptions(within(dialogo).getByLabelText('Inventario destino'), '2')
    const cantidad = within(dialogo).getByLabelText('Cantidad a mover')
    await user.clear(cantidad)
    await user.type(cantidad, '10')
    await user.click(within(dialogo).getByRole('button', { name: /Mover 10 PZ/ }))

    expect(await within(dialogo).findByRole('alert')).toHaveTextContent(
      /más de un Inventario General activo/,
    )
    await user.click(within(dialogo).getByRole('button', { name: /Mover 10 PZ/ }))

    await waitFor(() => expect(moverMaterial).toHaveBeenCalledTimes(2))
    expect(fn(moverMaterial).mock.calls[1][0]).toEqual({
      origen: 'GENERAL',
      destino: 'FO',
      material_id: 4,
      cantidad: 10,
      clave_idempotencia: fn(moverMaterial).mock.calls[0][0].clave_idempotencia,
    })
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Mover' })).not.toBeInTheDocument(),
    )
    expect(
      await screen.findByText(/en Inventario General: 2 PZ; en Inventario FO: 10 PZ/),
    ).toBeInTheDocument()
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['stock'],
        ['fibra'],
        ['inventario', 'resumen-general'],
      ]),
    )
    expect(claves()).not.toContainEqual(['fibra', 'PAQUETE'])
  })

  it('+Cantidad decimal (2.5): envía cantidad 2.5 y el toast usa el stock decimal del servidor', async () => {
    const user = userEvent.setup()
    fn(stockSeccion).mockResolvedValue([filaGeneral(12)])
    fn(sumarCantidad).mockResolvedValue({
      destino: 'GENERAL',
      material_id: 4,
      stock_nuevo: 14.5,
      reenvio_idempotente: false,
    })
    renderConProviders(<SeccionGeneral globalSearch="" />)

    await user.click(await screen.findByText('ACOPLADORES'))
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Cantidad' })
    await user.type(within(dialogo).getByLabelText('Cantidad a sumar'), '2.5')
    await user.click(within(dialogo).getByRole('button', { name: /Sumar 2.5 PZ a CON-1/ }))

    await waitFor(() => expect(sumarCantidad).toHaveBeenCalledTimes(1))
    expect(fn(sumarCantidad).mock.calls[0][0]).toMatchObject({
      destino: 'GENERAL',
      material_id: 4,
      cantidad: 2.5,
    })
    expect(await screen.findByText(/Stock en Inventario General: 14.5 PZ/)).toBeInTheDocument()
  })

  it('+Cantidad con 1.0005 muestra el error de exceso de decimales y no llama al servicio', async () => {
    const user = userEvent.setup()
    fn(stockSeccion).mockResolvedValue([filaGeneral(12)])
    renderConProviders(<SeccionGeneral globalSearch="" />)

    await user.click(await screen.findByText('ACOPLADORES'))
    await user.click(screen.getByRole('button', { name: '+ Cantidad' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Cantidad' })
    const input = within(dialogo).getByLabelText('Cantidad a sumar')
    await user.type(input, '1.0005{Enter}')

    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(
      within(dialogo).getAllByText(/Máximo 3 decimales; no se redondea/).length,
    ).toBeGreaterThan(0)
    expect(sumarCantidad).not.toHaveBeenCalled()
  })
})
