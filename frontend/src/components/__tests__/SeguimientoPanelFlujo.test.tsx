import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SeguimientoPanel from '../SeguimientoPanel'
import { ToastProvider } from '../ToastProvider'
import { inventarioEquipo } from '../../services/equipos'
import {
  agregarTodoSeguimiento,
  cerrarSeguimiento,
  crearSeguimiento,
  listSeguimientos,
} from '../../services/seguimientos'
import type { InventarioEquipoRow, Seguimiento } from '../../types'

// Flujo del panel con hooks REALES y la capa HTTP mockeada.
vi.mock('../../services/equipos', () => ({ inventarioEquipo: vi.fn() }))
vi.mock('../../services/seguimientos', () => ({
  listSeguimientos: vi.fn(),
  getSeguimiento: vi.fn(),
  crearSeguimiento: vi.fn(),
  cerrarSeguimiento: vi.fn(),
  agregarTodoSeguimiento: vi.fn(),
}))

const mInventario = vi.mocked(inventarioEquipo)
const mLista = vi.mocked(listSeguimientos)
const mCrear = vi.mocked(crearSeguimiento)
const mCerrar = vi.mocked(cerrarSeguimiento)

const fila: InventarioEquipoRow = {
  equipo_id: 1,
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  stock_minimo: 5,
  stock_actual: 5,
  valor_unitario: 1,
  alerta_stock: false,
  ultimo_movimiento_id: null,
  stock_minimo_local: null,
  categoria_local_id: null,
  um_local_id: null,
  stock_minimo_efectivo: 5,
  categoria_efectiva: 'Cables',
  um_efectivo: 'METRO (M)',
}

const abierto: Seguimiento = {
  id: 3,
  equipo_id: 1,
  fecha: '2026-10-01',
  observaciones: null,
  usuario: 'demo-operador',
  estado: 'ABIERTA',
  created_at: '',
  updated_at: '',
  closed_at: null,
  items: [
    { id: 1, material_id: 10, cantidad_tomada: 5, cantidad_consumida: null },
  ],
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <SeguimientoPanel equipoId={1} equipoNombre="PARTNER 2017" />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { claves: () => invalidate.mock.calls.map((c) => c[0]?.queryKey) }
}

beforeEach(() => {
  vi.clearAllMocks()
  mInventario.mockResolvedValue([fila])
})

describe('SeguimientoPanel — flujo con hooks reales (/equipos/{id}/seguimientos)', () => {
  it('cierre: llama a cerrar con { seguimientoId } y payload, invalida seguimientos/equipo/actas de consumo y anuncia el Acta de Consumo', async () => {
    const user = userEvent.setup()
    mLista
      .mockResolvedValueOnce([abierto])
      .mockResolvedValue([{ ...abierto, estado: 'CERRADA' }])
    mCerrar.mockResolvedValue({ ...abierto, estado: 'CERRADA' })
    const { claves } = renderPanel()

    await user.type(await screen.findByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(mCerrar).toHaveBeenCalledTimes(1))
    expect(mCerrar).toHaveBeenCalledWith(1, 3, {
      consumidos: [{ material_id: 10, cantidad_consumida: 2 }],
    })
    expect(await screen.findByText('Acta de Consumo generada')).toBeInTheDocument()
    expect(claves()).toEqual(
      expect.arrayContaining([
        ['seguimientos', 1],
        ['equipo', 1],
        ['reportes', 'actas', 'consumo'],
      ]),
    )
    // Recarga del estado persistido: la lista se vuelve a pedir y ya no hay ABIERTA.
    await waitFor(() => expect(mLista).toHaveBeenCalledTimes(2))
    expect(
      await screen.findByText('Nueva lista de seguimiento'),
    ).toBeInTheDocument()
  })

  it('cierre rechazado (409): sin aviso de acta ni invalidación de actas', async () => {
    const user = userEvent.setup()
    mLista.mockResolvedValue([abierto])
    mCerrar.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { error: { message: 'Seguimiento no ABIERTA' } } },
    })
    const { claves } = renderPanel()

    await user.type(await screen.findByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(mCerrar).toHaveBeenCalled())
    expect(screen.queryByText('Acta de Consumo generada')).not.toBeInTheDocument()
    expect(claves()).not.toContainEqual(['reportes', 'actas', 'consumo'])
  })

  it('apertura: POST con el payload y recarga de seguimientos + inventario del equipo', async () => {
    const user = userEvent.setup()
    mLista.mockResolvedValueOnce([]).mockResolvedValue([abierto])
    mCrear.mockResolvedValue(abierto)
    const { claves } = renderPanel()

    await user.click(await screen.findByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

    await waitFor(() => expect(mCrear).toHaveBeenCalledTimes(1))
    expect(mCrear).toHaveBeenCalledWith(1, {
      items: [{ material_id: 10, cantidad_tomada: 1 }],
    })
    expect(claves()).toEqual(
      expect.arrayContaining([['seguimientos', 1], ['equipo', 1]]),
    )
    expect(await screen.findByText(/Seguimiento abierto — /)).toBeInTheDocument()
  })

  it('"Agregar todo" precarga LOCALMENTE: no llama al endpoint agregar-todo', async () => {
    const user = userEvent.setup()
    mLista.mockResolvedValue([])
    renderPanel()

    await user.click(await screen.findByRole('button', { name: /Agregar todo/ }))

    expect(agregarTodoSeguimiento).not.toHaveBeenCalled()
    expect(mCrear).not.toHaveBeenCalled()
  })
})
