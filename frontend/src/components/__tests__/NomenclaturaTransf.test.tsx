import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Transferencias from '../../pages/Transferencias'
import ActaGeneradaAviso from '../ActaGeneradaAviso'
import { listFibraStock } from '../../services/fibra'
import { stockSeccion } from '../../services/inventory'
import { listEquipos } from '../../services/equipos'
import { crearBorrador, listMovimientos, procesarMovimiento } from '../../services/movimientos'
import { TIPOS_ACCION_AUDITORIA, etiquetaTipoMovimiento } from '../../types'

// RF-1..RF-7 (REQ-NOM-001..007): TRANSF / Confirmar Devolución.

vi.mock('../../hooks/useToasts', () => ({
  useToast: () => ({ pushToast: vi.fn(), pushError: vi.fn() }),
}))
vi.mock('../../hooks/useSeccionesTransferibles', () => ({
  useSeccionesTransferibles: () => ({
    data: [{ almacen_id: 1, nombre: 'Inventario General', tipo: 'GENERAL', transferible: true }],
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

const mov = (id: number, tipo: 'TEAMS' | 'DEVOL', estado = 'CONFIRMADO') => ({
  id, tipo_movimiento: tipo, estado, usuario: 'qa',
  origen_almacen_id: tipo === 'TEAMS' ? 1 : null,
  destino_almacen_id: tipo === 'DEVOL' ? 1 : null,
  origen_equipo_id: tipo === 'DEVOL' ? 5 : null,
  destino_equipo_id: tipo === 'TEAMS' ? 5 : null,
  observaciones: null,
  detalle: [{ material_id: 10, cantidad: 1, origen_almacen_id: tipo === 'TEAMS' ? 1 : null }],
})

function renderPagina() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <Transferencias />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(stockSeccion).mockResolvedValue([
    { material_id: 10, codigo: 'G-1', descripcion: 'Conector', u_m: 'PZ', stock_minimo: null, stock_actual: 9, alerta_stock: false },
  ] as never)
  vi.mocked(listFibraStock).mockResolvedValue([])
  vi.mocked(listEquipos).mockResolvedValue([
    { equipo_id: 5, nombre: 'Unidad QA', descripcion: null, is_active: true, integrantes: [] },
  ])
  vi.mocked(listMovimientos).mockResolvedValue([mov(7, 'TEAMS'), mov(8, 'DEVOL')] as never)
  vi.mocked(crearBorrador).mockResolvedValue({ id: 1, tipo_movimiento: 'TEAMS', destino_equipo_id: 5 } as never)
  vi.mocked(procesarMovimiento).mockResolvedValue(undefined)
})

describe('Pestañas y botones', () => {
  it('RF-1 REQ-NOM-001: la pestaña de transferencia se llama TRANSF; la de devolución sigue DEVOL', async () => {
    renderPagina()
    expect(await screen.findByRole('button', { name: 'TRANSF' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'DEVOL' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'TEAMS' })).not.toBeInTheDocument()
  })

  it('RF-2/RF-3 REQ-NOM-002/003: el botón del carrito sigue a la pestaña activa', async () => {
    const user = userEvent.setup()
    renderPagina()
    expect(await screen.findByRole('button', { name: 'Confirmar Transferencia' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirmar (TEAMS|DEVOL)/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'DEVOL' }))
    expect(screen.getByRole('button', { name: 'Confirmar Devolución' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirmar Transferencia' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirmar (TEAMS|DEVOL)/ })).not.toBeInTheDocument()
  })
})

describe('Historial y modal', () => {
  it('RF-4 REQ-NOM-004: la columna TIPO muestra TRANSF para TEAMS y DEVOL para devoluciones', async () => {
    renderPagina()
    const filaTransf = (await screen.findByText('7')).closest('tr') as HTMLElement
    const filaDevol = screen.getByText('8').closest('tr') as HTMLElement
    expect(within(filaTransf).getByText('TRANSF')).toBeInTheDocument()
    expect(within(filaDevol).getByText('DEVOL')).toBeInTheDocument()
    expect(within(filaTransf).queryByText('TEAMS')).not.toBeInTheDocument()
  })

  it('RF-4 REQ-NOM-004: el modal de cancelación nombra la operación como TRANSF', async () => {
    const user = userEvent.setup()
    renderPagina()
    const fila = (await screen.findByText('7')).closest('tr') as HTMLElement
    await user.click(within(fila).getByRole('button', { name: /Cancelar/ }))
    expect(await screen.findByText(/#7\s+TRANSF/)).toBeInTheDocument()
  })
})

describe('Etiquetas centralizadas y textos secundarios', () => {
  it('RF-6 REQ-NOM-006: etiquetaTipoMovimiento es la única fuente del texto visible', () => {
    expect(etiquetaTipoMovimiento('TEAMS')).toBe('TRANSF')
    expect(etiquetaTipoMovimiento('DEVOL')).toBe('DEVOL')
  })

  it('RF-5 REQ-NOM-005: aviso del acta y etiqueta de Auditoría usan la nomenclatura oficial', () => {
    render(<ActaGeneradaAviso tipo="ENTREGA" equipoNombre="PARTNER" onDismiss={() => undefined} />)
    expect(screen.getByRole('status')).toHaveTextContent(/transferencia hacia PARTNER/i)
    expect(screen.getByRole('status')).not.toHaveTextContent(/TEAMS/)
    expect(TIPOS_ACCION_AUDITORIA.TEAMS_TRANSFERENCIA).toBe('TRANSF — transferencia')
    expect(TIPOS_ACCION_AUDITORIA.DEVOL_DEVOLUCION).toBe('DEVOL — devolución')
  })
})

describe('Contrato intacto', () => {
  it('RF-7 REQ-NOM-007: el payload sigue enviando tipo_movimiento TEAMS', async () => {
    const user = userEvent.setup()
    renderPagina()
    const [seccion, unidad] = await screen.findAllByRole('combobox')
    await user.selectOptions(seccion, '1')
    await user.selectOptions(unidad, '5')
    await user.click(await screen.findByRole('button', { name: /Agregar/ }))
    await user.click(screen.getByRole('button', { name: 'Confirmar Transferencia' }))
    await waitFor(() => expect(crearBorrador).toHaveBeenCalledTimes(1))
    expect(vi.mocked(crearBorrador).mock.calls[0][0].tipo_movimiento).toBe('TEAMS')
  })
})
