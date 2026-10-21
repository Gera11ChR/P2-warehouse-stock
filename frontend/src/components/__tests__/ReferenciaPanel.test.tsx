import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReferenciaPanel from '../ReferenciaPanel'
import {
  useEliminarReferencia,
  useModificarReferencia,
  useReferencia,
} from '../../hooks/useReferencia'
import type { ReferenciaLinea } from '../../types'

// REQ-REF-002/003/004/008/009/014/016 — panel «Materiales Referencia»:
// tabla con exactamente Descripción / U.M. / Cantidad Semanal, estados de
// carga/error (con reintento)/vacío, SOLO LECTURA en Consulta, acciones en
// Configuración (Modificar edita solo la cantidad; Eliminar con confirmación)
// y refresco de la tabla ante 404 REFERENCIA_NO_ENCONTRADA.

vi.mock('../../hooks/useReferencia', () => ({
  useReferencia: vi.fn(),
  useModificarReferencia: vi.fn(),
  useEliminarReferencia: vi.fn(),
  useCrearReferencia: vi.fn(),
  useOpcionesOrigenReferencia: vi.fn(),
}))

const mockedUseReferencia = vi.mocked(useReferencia)
const mockedUseModificarReferencia = vi.mocked(useModificarReferencia)
const mockedUseEliminarReferencia = vi.mocked(useEliminarReferencia)

const linea = (overrides: Partial<ReferenciaLinea> = {}): ReferenciaLinea => ({
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  cantidad_semanal: 2.5,
  ...overrides,
})

const modificarMutate = vi.fn()
const eliminarMutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseReferencia.mockReturnValue({
    data: [linea()],
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useReferencia>)
  mockedUseModificarReferencia.mockReturnValue({
    mutate: modificarMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useModificarReferencia>)
  mockedUseEliminarReferencia.mockReturnValue({
    mutate: eliminarMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useEliminarReferencia>)
})

function renderPanel(modo: 'consulta' | 'configuracion') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ReferenciaPanel equipoId={1} equipoNombre="PARTNER 2017" modo={modo} />
    </QueryClientProvider>,
  )
  return { ...view, invalidate }
}

describe('ReferenciaPanel — tabla (REQ-REF-002)', () => {
  it('columnas EXACTAS «Descripción», «U.M.» y «Cantidad Semanal» con una fila por línea', () => {
    mockedUseReferencia.mockReturnValue({
      data: [
        linea(),
        linea({
          material_id: 11,
          descripcion: 'Acopladores',
          u_m: 'PZ',
          cantidad_semanal: 3,
        }),
      ],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('consulta')

    expect(screen.getByRole('heading', { name: 'Materiales Referencia' })).toBeInTheDocument()
    const columnas = screen.getAllByRole('columnheader').map((c) => c.textContent)
    expect(columnas).toEqual(['Descripción', 'U.M.', 'Cantidad Semanal'])
    const filas = screen.getAllByRole('row').slice(1)
    expect(filas).toHaveLength(2)
    expect(filas[0]).toHaveTextContent('Cable UTP Cat 6')
    expect(filas[0]).toHaveTextContent('METRO (M)')
    expect(filas[0]).toHaveTextContent('2.5')
    // Sin columnas de stock, valor ni alerta (REQ-REF-002).
    expect(screen.queryByText(/stock/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/valor/i)).not.toBeInTheDocument()
  })

  it('U.M. nula → guion largo', () => {
    mockedUseReferencia.mockReturnValue({
      data: [linea({ u_m: null })],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('consulta')
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('—')
  })

  it('aviso permanente: la cantidad NO afecta el inventario (RN-5)', () => {
    renderPanel('consulta')
    expect(
      screen.getByText(/la cantidad no afecta el inventario/i),
    ).toBeInTheDocument()
  })
})

describe('ReferenciaPanel — estados (REQ-REF-016)', () => {
  it('vacío en Consulta: mensaje sin instrucción de agregar', () => {
    mockedUseReferencia.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('consulta')
    const estado = screen.getByRole('status')
    expect(estado).toHaveTextContent('La Referencia de esta Unidad está vacía.')
    expect(estado).not.toHaveTextContent('Usa «Agregar»')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('vacío en Configuración: mensaje con cómo agregar', () => {
    mockedUseReferencia.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('configuracion')
    expect(screen.getByRole('status')).toHaveTextContent(
      'Usa «Agregar» para elegir los materiales que maneja.',
    )
  })

  it('carga: estado anunciado, sin tabla ni estado vacío', () => {
    mockedUseReferencia.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('consulta')
    expect(screen.getByRole('status')).toHaveTextContent(
      'Cargando la Referencia…',
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('error de carga: alerta con «Reintentar» y FAIL-CLOSED (nunca lista vacía)', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    mockedUseReferencia.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('403'),
      refetch,
    } as unknown as ReturnType<typeof useReferencia>)
    renderPanel('consulta')
    expect(screen.getByRole('alert')).toHaveTextContent(
      'No se pudo cargar la Referencia de la Unidad.',
    )
    expect(screen.queryByText(/vacía/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })
})

describe('ReferenciaPanel — Consulta es SOLO LECTURA (REQ-REF-003)', () => {
  it('sin «Agregar», «Modificar» ni «Eliminar» (y sin columna Acciones)', () => {
    renderPanel('consulta')
    expect(
      screen.queryByRole('button', { name: /Agregar/ }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Modificar/ }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Eliminar/ }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Acciones')).not.toBeInTheDocument()
  })
})

describe('ReferenciaPanel — Configuración (REQ-REF-014)', () => {
  it('ofrece «Agregar» y «Modificar»/«Eliminar» en cada fila', () => {
    renderPanel('configuracion')
    expect(
      screen.getByRole('button', { name: /Agregar/ }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Modificar Cable UTP Cat 6' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Eliminar Cable UTP Cat 6' }),
    ).toBeInTheDocument()
  })

  it('Modificar: cantidad inválida → error en línea y SIN mutación; válida → PATCH solo de la cantidad', async () => {
    const user = userEvent.setup()
    modificarMutate.mockImplementation((_p, opciones) => opciones?.onSuccess?.())
    renderPanel('configuracion')

    await user.click(screen.getByRole('button', { name: 'Modificar Cable UTP Cat 6' }))
    const campo = screen.getByLabelText('Cantidad Semanal de Cable UTP Cat 6')
    expect(campo).toHaveValue('2.5')

    await user.clear(campo)
    await user.type(campo, '0')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(
      screen.getByText('La cantidad debe ser mayor que 0.'),
    ).toBeInTheDocument()
    expect(modificarMutate).not.toHaveBeenCalled()

    await user.clear(campo)
    await user.type(campo, '7')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(modificarMutate).toHaveBeenCalledWith(
      { materialId: 10, payload: { cantidad_semanal: 7 } },
      expect.anything(),
    )
    expect(
      screen.queryByLabelText('Cantidad Semanal de Cable UTP Cat 6'),
    ).not.toBeInTheDocument()
  })

  it('Modificar con 404 REFERENCIA_NO_ENCONTRADA: cierra la edición, refresca y avisa', async () => {
    const user = userEvent.setup()
    const error = {
      response: {
        status: 404,
        data: { error: { code: 'REFERENCIA_NO_ENCONTRADA', message: 'no existe' } },
      },
    }
    modificarMutate.mockImplementation((_p, opciones) => opciones?.onError?.(error))
    const { invalidate } = renderPanel('configuracion')

    await user.click(screen.getByRole('button', { name: 'Modificar Cable UTP Cat 6' }))
    const campo = screen.getByLabelText('Cantidad Semanal de Cable UTP Cat 6')
    await user.clear(campo)
    await user.type(campo, '7')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(
      screen.queryByLabelText('Cantidad Semanal de Cable UTP Cat 6'),
    ).not.toBeInTheDocument()
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['referencia', 1],
    })
    expect(
      screen.getByText('La línea ya no existe en la Referencia; se actualizó la tabla.'),
    ).toBeInTheDocument()
  })

  it('Eliminar: exige confirmación; Cancelar conserva la fila', async () => {
    const user = userEvent.setup()
    renderPanel('configuracion')

    await user.click(screen.getByRole('button', { name: 'Eliminar Cable UTP Cat 6' }))
    expect(
      screen.getByText(/¿Seguro que deseas quitar "Cable UTP Cat 6"/),
    ).toBeInTheDocument()
    expect(eliminarMutate).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.getByText('Cable UTP Cat 6')).toBeInTheDocument()
    expect(eliminarMutate).not.toHaveBeenCalled()
  })

  it('Eliminar: la confirmación es un diálogo accesible con foco gestionado (REQ-REF-016)', async () => {
    const user = userEvent.setup()
    renderPanel('configuracion')
    const disparador = screen.getByRole('button', {
      name: 'Eliminar Cable UTP Cat 6',
    })

    await user.click(disparador)
    const dialogo = screen.getByRole('dialog', { name: 'Eliminar de la Referencia' })
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus()

    // Esc cancela, no elimina y devuelve el foco a «Eliminar» de la fila.
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(eliminarMutate).not.toHaveBeenCalled()
    expect(disparador).toHaveFocus()
  })

  it('Eliminar: confirmar elimina la línea y aclara que inventarios no cambian', async () => {
    const user = userEvent.setup()
    eliminarMutate.mockImplementation((_id, opciones) => opciones?.onSuccess?.())
    renderPanel('configuracion')

    await user.click(screen.getByRole('button', { name: 'Eliminar Cable UTP Cat 6' }))
    expect(
      screen.getByText(/El material y los inventarios no se modifican/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Eliminar' }))
    expect(eliminarMutate).toHaveBeenCalledWith(10, expect.anything())
    expect(
      screen.queryByText(/¿Seguro que deseas quitar/),
    ).not.toBeInTheDocument()
  })

  it('Eliminar con 404 REFERENCIA_NO_ENCONTRADA: refresca la tabla y avisa', async () => {
    const user = userEvent.setup()
    const error = {
      response: {
        status: 404,
        data: { error: { code: 'REFERENCIA_NO_ENCONTRADA', message: 'no existe' } },
      },
    }
    eliminarMutate.mockImplementation((_id, opciones) => opciones?.onError?.(error))
    const { invalidate } = renderPanel('configuracion')

    await user.click(screen.getByRole('button', { name: 'Eliminar Cable UTP Cat 6' }))
    await user.click(screen.getByRole('button', { name: 'Eliminar' }))

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['referencia', 1] })
    expect(
      screen.getByText('La línea ya no existe en la Referencia; se actualizó la tabla.'),
    ).toBeInTheDocument()
  })
})
