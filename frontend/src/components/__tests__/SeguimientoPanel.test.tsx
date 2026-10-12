import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SeguimientoPanel from '../SeguimientoPanel'
import { ToastProvider } from '../ToastProvider'
import { NavigationContext } from '../../hooks/navigationContext'
import type { AppNavigate } from '../../hooks/navigationContext'
import { useSeguimientos } from '../../hooks/useSeguimientos'
import { useEquipoInventario } from '../../hooks/useEquipoInventario'
import { useCrearSeguimiento } from '../../hooks/useCrearSeguimiento'
import { useCerrarSeguimiento } from '../../hooks/useCerrarSeguimiento'
import type { Seguimiento, InventarioEquipoRow } from '../../types'

vi.mock('../../hooks/useSeguimientos', () => ({ useSeguimientos: vi.fn() }))
vi.mock('../../hooks/useEquipoInventario', () => ({
  useEquipoInventario: vi.fn(),
}))
vi.mock('../../hooks/useCrearSeguimiento', () => ({
  useCrearSeguimiento: vi.fn(),
}))
vi.mock('../../hooks/useCerrarSeguimiento', () => ({
  useCerrarSeguimiento: vi.fn(),
}))

const mockedUseSeguimientos = vi.mocked(useSeguimientos)
const mockedUseEquipoInventario = vi.mocked(useEquipoInventario)
const mockedUseCrearSeguimiento = vi.mocked(useCrearSeguimiento)
const mockedUseCerrarSeguimiento = vi.mocked(useCerrarSeguimiento)

function fila(overrides: Partial<InventarioEquipoRow>): InventarioEquipoRow {
  return {
    equipo_id: 1,
    material_id: 10,
    codigo: 'CBL-001',
    descripcion: 'Cable UTP Cat 6',
    u_m: 'METRO (M)',
    stock_minimo: 5,
    stock_actual: 5,
    alerta_stock: false,
    ultimo_movimiento_id: null,
    stock_minimo_local: null,
    categoria_local_id: null,
    um_local_id: null,
    stock_minimo_efectivo: 5,
    categoria_efectiva: 'Cables',
    um_efectivo: 'METRO (M)',
    ...overrides,
  }
}

function querySeguimientos(
  overrides: Partial<ReturnType<typeof useSeguimientos>> = {},
): ReturnType<typeof useSeguimientos> {
  return {
    data: [],
    isLoading: false,
    isError: false,
    error: null,
    abierta: null,
    ...overrides,
  } as ReturnType<typeof useSeguimientos>
}

const crearMutate = vi.fn()
const cerrarMutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseCrearSeguimiento.mockReturnValue({
    mutate: crearMutate,
  } as unknown as ReturnType<typeof useCrearSeguimiento>)
  mockedUseCerrarSeguimiento.mockReturnValue({
    mutate: cerrarMutate,
  } as unknown as ReturnType<typeof useCerrarSeguimiento>)
  mockedUseEquipoInventario.mockReturnValue({
    data: [fila({})],
    isLoading: false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useEquipoInventario>)
})

function renderPanel() {
  return render(
    <ToastProvider>
      <SeguimientoPanel equipoId={1} />
    </ToastProvider>,
  )
}

const seguimientoAbierto: Seguimiento = {
  id: 3,
  equipo_id: 1,
  fecha: '2026-09-28T10:00:00',
  observaciones: 'Obra zona norte',
  usuario: 'demo-operador',
  estado: 'ABIERTA',
  created_at: '2026-09-28T10:00:00',
  updated_at: '2026-09-28T10:00:00',
  closed_at: null,
  items: [
    {
      id: 1,
      material_id: 10,
      cantidad_tomada: 5,
      cantidad_consumida: null,
    },
  ],
}

describe('SeguimientoPanel — sin seguimiento abierto', () => {
  it('renderiza el formulario de nueva lista', () => {
    mockedUseSeguimientos.mockReturnValue(querySeguimientos())
    renderPanel()

    expect(screen.getByText('Nueva lista de seguimiento')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Crear Seguimiento' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Agregar línea' }),
    ).toBeInTheDocument()
  })

  it('enviar la lista → crear mutación con el payload', async () => {
    const user = userEvent.setup()
    mockedUseSeguimientos.mockReturnValue(querySeguimientos())
    renderPanel()

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.click(screen.getByRole('button', { name: 'Crear Seguimiento' }))

    expect(crearMutate).toHaveBeenCalledTimes(1)
    expect(crearMutate).toHaveBeenCalledWith(
      { items: [{ material_id: 10, cantidad_tomada: 1 }] },
      expect.any(Object),
    )
  })
})

describe('SeguimientoPanel — con seguimiento abierto', () => {
  it('renderiza el cierre y abre el ConfirmDialog al enviar', async () => {
    const user = userEvent.setup()
    mockedUseSeguimientos.mockReturnValue(
      querySeguimientos({ abierta: seguimientoAbierto }),
    )
    renderPanel()

    expect(screen.getByText(/Seguimiento abierto — /)).toBeInTheDocument()
    expect(screen.getByText('Obra zona norte')).toBeInTheDocument()
    // Descripción presente en resumen y en el formulario de cierre.
    expect(screen.getAllByText('Cable UTP Cat 6').length).toBeGreaterThan(0)

    await user.type(screen.getByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))

    expect(screen.getByText('Cerrar seguimiento')).toBeInTheDocument()
    expect(
      screen.getByText(/Se registrará lo consumido/),
    ).toBeInTheDocument()
    expect(cerrarMutate).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(cerrarMutate).toHaveBeenCalledTimes(1)
    expect(cerrarMutate).toHaveBeenCalledWith(
      {
        seguimientoId: 3,
        payload: { consumidos: [{ material_id: 10, cantidad_consumida: 2 }] },
      },
      expect.any(Object),
    )
  })
})


describe('SeguimientoPanel — Acta de Consumo tras el cierre (REQ-P2-CON-005)', () => {
  function abrirConfirmacionDeCierre() {
    cerrarMutate.mockReset()
    mockedUseSeguimientos.mockReturnValue(
      querySeguimientos({ abierta: seguimientoAbierto }),
    )
  }

  it('no muestra el aviso hasta que el servidor acepta el cierre', async () => {
    const user = userEvent.setup()
    abrirConfirmacionDeCierre()
    renderPanel()

    await user.type(screen.getByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(cerrarMutate).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Acta de Consumo generada')).not.toBeInTheDocument()
  })

  it('tras el cierre exitoso informa el Acta de Consumo y navega a Reportes > Consumo del equipo', async () => {
    const user = userEvent.setup()
    const navigate = vi.fn<AppNavigate>()
    abrirConfirmacionDeCierre()
    cerrarMutate.mockImplementation((_vars, opts) => opts.onSuccess())
    render(
      <NavigationContext.Provider value={navigate}>
        <ToastProvider>
          <SeguimientoPanel equipoId={1} equipoNombre="PARTNER 2017" />
        </ToastProvider>
      </NavigationContext.Provider>,
    )

    await user.type(screen.getByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(screen.getByText('Acta de Consumo generada')).toBeInTheDocument()
    expect(screen.getByText(/PARTNER 2017/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Ir a Reportes > Consumo' }),
    )
    expect(navigate).toHaveBeenCalledWith({
      page: 'reportes',
      sub: 'consumo',
      equipoId: 1,
    })
  })

  it('sin navegación disponible no ofrece una acción muerta', async () => {
    const user = userEvent.setup()
    abrirConfirmacionDeCierre()
    cerrarMutate.mockImplementation((_vars, opts) => opts.onSuccess())
    renderPanel()

    await user.type(screen.getByLabelText('Consumido'), '2')
    await user.click(screen.getByRole('button', { name: 'Cerrar Seguimiento' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(screen.getByText('Acta de Consumo generada')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Ir a Reportes/ }),
    ).not.toBeInTheDocument()
  })
})
