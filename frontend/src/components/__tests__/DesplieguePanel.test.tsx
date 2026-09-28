import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DesplieguePanel from '../DesplieguePanel'
import { ToastProvider } from '../ToastProvider'
import { useDespliegues } from '../../hooks/useDespliegues'
import { useEquipoInventario } from '../../hooks/useEquipoInventario'
import { useCrearDespliegue } from '../../hooks/useCrearDespliegue'
import { useCerrarDespliegue } from '../../hooks/useCerrarDespliegue'
import type { Despliegue, InventarioEquipoRow } from '../../types'

vi.mock('../../hooks/useDespliegues', () => ({ useDespliegues: vi.fn() }))
vi.mock('../../hooks/useEquipoInventario', () => ({
  useEquipoInventario: vi.fn(),
}))
vi.mock('../../hooks/useCrearDespliegue', () => ({
  useCrearDespliegue: vi.fn(),
}))
vi.mock('../../hooks/useCerrarDespliegue', () => ({
  useCerrarDespliegue: vi.fn(),
}))

const mockedUseDespliegues = vi.mocked(useDespliegues)
const mockedUseEquipoInventario = vi.mocked(useEquipoInventario)
const mockedUseCrearDespliegue = vi.mocked(useCrearDespliegue)
const mockedUseCerrarDespliegue = vi.mocked(useCerrarDespliegue)

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

function queryDespliegues(
  overrides: Partial<ReturnType<typeof useDespliegues>> = {},
): ReturnType<typeof useDespliegues> {
  return {
    data: [],
    isLoading: false,
    isError: false,
    error: null,
    abierta: null,
    ...overrides,
  } as ReturnType<typeof useDespliegues>
}

const crearMutate = vi.fn()
const cerrarMutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseCrearDespliegue.mockReturnValue({
    mutate: crearMutate,
  } as unknown as ReturnType<typeof useCrearDespliegue>)
  mockedUseCerrarDespliegue.mockReturnValue({
    mutate: cerrarMutate,
  } as unknown as ReturnType<typeof useCerrarDespliegue>)
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
      <DesplieguePanel equipoId={1} />
    </ToastProvider>,
  )
}

const despliegueAbierto: Despliegue = {
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
      cantidad_sobrante: null,
      cantidad_consumida: null,
    },
  ],
}

describe('DesplieguePanel — sin despliegue abierto', () => {
  it('renderiza el formulario de nueva lista', () => {
    mockedUseDespliegues.mockReturnValue(queryDespliegues())
    renderPanel()

    expect(screen.getByText('Nueva lista de despliegue')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Crear Despliegue' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Agregar línea' }),
    ).toBeInTheDocument()
  })

  it('enviar la lista → crear mutación con el payload', async () => {
    const user = userEvent.setup()
    mockedUseDespliegues.mockReturnValue(queryDespliegues())
    renderPanel()

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    await user.selectOptions(screen.getByRole('combobox'), '10')
    await user.click(screen.getByRole('button', { name: 'Crear Despliegue' }))

    expect(crearMutate).toHaveBeenCalledTimes(1)
    expect(crearMutate).toHaveBeenCalledWith(
      { items: [{ material_id: 10, cantidad_tomada: 1 }] },
      expect.any(Object),
    )
  })
})

describe('DesplieguePanel — con despliegue abierto', () => {
  it('renderiza el cierre y abre el ConfirmDialog al enviar', async () => {
    const user = userEvent.setup()
    mockedUseDespliegues.mockReturnValue(
      queryDespliegues({ abierta: despliegueAbierto }),
    )
    renderPanel()

    expect(screen.getByText(/Despliegue abierto — /)).toBeInTheDocument()
    expect(screen.getByText('Obra zona norte')).toBeInTheDocument()
    // Descripción presente en resumen y en el formulario de cierre.
    expect(screen.getAllByText('Cable UTP Cat 6').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Cerrar Despliegue' }))

    expect(screen.getByText('Cerrar despliegue')).toBeInTheDocument()
    expect(
      screen.getByText(/Se registrarán los sobrantes/),
    ).toBeInTheDocument()
    expect(cerrarMutate).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(cerrarMutate).toHaveBeenCalledTimes(1)
    expect(cerrarMutate).toHaveBeenCalledWith(
      {
        despliegueId: 3,
        payload: { sobrantes: [{ material_id: 10, cantidad_sobrante: 0 }] },
      },
      expect.any(Object),
    )
  })
})
