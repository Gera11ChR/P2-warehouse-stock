import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReferenciaAgregarForm from '../ReferenciaAgregarForm'
import {
  useCrearReferencia,
  useOpcionesOrigenReferencia,
} from '../../hooks/useReferencia'
import { claveOpcion } from '../../utils/referenciaOrigen'
import type {
  EstadoOrigenOpciones,
  OpcionOrigenFo,
  OpcionOrigenGeneral,
} from '../../hooks/useReferencia'

// REQ-REF-006/007/013 — alta con selección dependiente: origen POR LÍNEA →
// material dependiente (cambiar el origen reinicia el material), una opción
// por sección, exclusión de materiales ya presentes, validación local,
// lote en UNA petición, datos CONSERVADOS ante rechazo (y refresco ante
// 409 REFERENCIA_DUPLICADA) y error de origen con reintento (C-10).

vi.mock('../../hooks/useReferencia', () => ({
  useCrearReferencia: vi.fn(),
  useOpcionesOrigenReferencia: vi.fn(),
}))

const mockedUseCrearReferencia = vi.mocked(useCrearReferencia)
const mockedUseOpcionesOrigenReferencia = vi.mocked(useOpcionesOrigenReferencia)

const crearMutate = vi.fn()

const generalOpcion = (
  overrides: Partial<OpcionOrigenGeneral> = {},
): OpcionOrigenGeneral => ({
  origen: 'general',
  almacen_id: 1,
  nombre_seccion: 'Inventario General',
  material_id: 10,
  descripcion: 'Cinta aislante',
  u_m: 'PZ',
  stock_actual: 40,
  ...overrides,
})

const foOpcion = (overrides: Partial<OpcionOrigenFo> = {}): OpcionOrigenFo => ({
  origen: 'fo',
  material_id: 20,
  descripcion: 'Fibra drop 1 hilo',
  u_m: 'METRO (M)',
  stock_actual: 2500,
  ...overrides,
})

function estadoGeneral(
  options: OpcionOrigenGeneral[] | undefined,
  extra: Partial<EstadoOrigenOpciones<OpcionOrigenGeneral>> = {},
): EstadoOrigenOpciones<OpcionOrigenGeneral> {
  return {
    options,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...extra,
  }
}

function estadoFo(
  options: OpcionOrigenFo[] | undefined,
  extra: Partial<EstadoOrigenOpciones<OpcionOrigenFo>> = {},
): EstadoOrigenOpciones<OpcionOrigenFo> {
  return {
    options,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...extra,
  }
}

const GENERAL_OPCIONES = [
  generalOpcion({ material_id: 10, descripcion: 'Cinta aislante', stock_actual: 40 }),
  generalOpcion({
    material_id: 10,
    almacen_id: 2,
    nombre_seccion: 'Inventario Norte',
    stock_actual: 12,
  }),
  generalOpcion({ material_id: 11, descripcion: 'Acopladores', stock_actual: 3 }),
]

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseCrearReferencia.mockReturnValue({
    mutate: crearMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useCrearReferencia>)
  mockedUseOpcionesOrigenReferencia.mockReturnValue({
    general: estadoGeneral(GENERAL_OPCIONES),
    fo: estadoFo([foOpcion()]),
  })
})

function renderForm(existentes: ReadonlySet<number> = new Set(), onCerrar = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ReferenciaAgregarForm
        equipoId={1}
        existentes={existentes}
        onCerrar={onCerrar}
      />
    </QueryClientProvider>,
  )
  return { ...view, invalidate }
}

const errorHttp = (status: number, code: string) => ({
  response: { status, data: { error: { code, message: `mensaje ${code}` } } },
})

describe('ReferenciaAgregarForm — selección dependiente (REQ-REF-013)', () => {
  it('arranca con UNA línea: origen «Inventario General», material vacío y cantidad vacía', () => {
    renderForm()
    expect(screen.getByLabelText('Origen')).toHaveValue('general')
    expect(screen.getByLabelText('Material')).toHaveValue('')
    expect(screen.getByLabelText('Cantidad')).toHaveValue('')
    expect(screen.getByText('Línea 1')).toBeInTheDocument()
  })

  it('cambiar el origen REINICIA el material de la línea', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.selectOptions(
      screen.getByLabelText('Material'),
      claveOpcion(GENERAL_OPCIONES[2]),
    )
    expect(screen.getByLabelText('Material')).not.toHaveValue('')

    await user.selectOptions(screen.getByLabelText('Origen'), 'fo')
    expect(screen.getByLabelText('Material')).toHaveValue('')
    expect(
      within(screen.getByLabelText('Material')).getByRole('option', {
        name: /Fibra drop 1 hilo/,
      }),
    ).toBeInTheDocument()
  })

  it('NO ofrece materiales ya presentes en la Referencia (existentes)', () => {
    renderForm(new Set([10]))
    const select = screen.getByLabelText('Material')
    expect(
      within(select).queryByRole('option', { name: /Cinta aislante/ }),
    ).not.toBeInTheDocument()
    expect(
      within(select).getByRole('option', { name: /Acopladores/ }),
    ).toBeInTheDocument()
  })

  it('NO ofrece en una línea el material ya elegido en otra', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.selectOptions(
      screen.getByLabelText('Material'),
      claveOpcion(GENERAL_OPCIONES[2]),
    )
    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))

    const linea2 = screen.getByText('Línea 2').closest('[role="group"]') as HTMLElement
    expect(within(linea2).getByLabelText('Material')).toHaveValue('')
    expect(
      within(within(linea2).getByLabelText('Material')).queryByRole('option', {
        name: /Acopladores/,
      }),
    ).not.toBeInTheDocument()
  })
})

describe('ReferenciaAgregarForm — validación (REQ-REF-006/007)', () => {
  it('vacío: errores por campo y SIN mutación', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(screen.getByText('Seleccione un material.')).toBeInTheDocument()
    expect(screen.getByText('Ingresa la cantidad.')).toBeInTheDocument()
    expect(
      screen.getByText('Revisa las líneas marcadas antes de confirmar.'),
    ).toBeInTheDocument()
    expect(crearMutate).not.toHaveBeenCalled()
  })

  it('cantidad 0 o con más de 3 decimales: rechazada sin mutación', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.selectOptions(
      screen.getByLabelText('Material'),
      claveOpcion(GENERAL_OPCIONES[2]),
    )
    const cantidad = screen.getByLabelText('Cantidad')
    await user.type(cantidad, '0')
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(
      screen.getByText('La cantidad debe ser mayor que 0.'),
    ).toBeInTheDocument()
    expect(crearMutate).not.toHaveBeenCalled()

    await user.clear(cantidad)
    await user.type(cantidad, '1.2345')
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(screen.getByText(/Máximo 3 decimales/)).toBeInTheDocument()
    expect(crearMutate).not.toHaveBeenCalled()
  })

  it('lote válido: UNA petición con TODAS las líneas (todo-o-nada)', async () => {
    const user = userEvent.setup()
    const onCerrar = vi.fn()
    crearMutate.mockImplementation((_p, opciones) => opciones?.onSuccess?.())
    renderForm(new Set(), onCerrar)

    await user.selectOptions(
      screen.getByLabelText('Material'),
      claveOpcion(GENERAL_OPCIONES[2]),
    )
    await user.type(screen.getByLabelText('Cantidad'), '2.5')

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    const linea2 = screen.getByText('Línea 2').closest('[role="group"]') as HTMLElement
    await user.selectOptions(within(linea2).getByLabelText('Origen'), 'fo')
    await user.selectOptions(
      within(linea2).getByLabelText('Material'),
      claveOpcion(foOpcion()),
    )
    await user.type(within(linea2).getByLabelText('Cantidad'), '300')

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(crearMutate).toHaveBeenCalledTimes(1)
    expect(crearMutate.mock.calls[0][0]).toEqual({
      lineas: [
        { material_id: 11, cantidad_semanal: 2.5 },
        { material_id: 20, cantidad_semanal: 300 },
      ],
    })
    expect(onCerrar).toHaveBeenCalled()
  })

  it('quitar una línea: mínimo UNA línea (botón deshabilitado)', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByRole('button', { name: 'Agregar línea' }))
    expect(screen.getByText('Línea 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Quitar línea 2' }))
    expect(screen.queryByText('Línea 2')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Quitar línea 1' }),
    ).toBeDisabled()
  })
})

describe('ReferenciaAgregarForm — rechazos (REQ-REF-013)', () => {
  const llenarLinea = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.selectOptions(
      screen.getByLabelText('Material'),
      claveOpcion(GENERAL_OPCIONES[2]),
    )
    await user.type(screen.getByLabelText('Cantidad'), '2.5')
  }

  it('409 REFERENCIA_DUPLICADA: refresca la lista y CONSERVA los datos', async () => {
    const user = userEvent.setup()
    crearMutate.mockImplementation((_p, opciones) =>
      opciones?.onError?.(errorHttp(409, 'REFERENCIA_DUPLICADA')),
    )
    const { invalidate } = renderForm()

    await llenarLinea(user)
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['referencia', 1] })
    expect(screen.getByRole('alert')).toHaveTextContent(
      /ya está en la Referencia; se actualizó la lista/,
    )
    expect(screen.getByLabelText('Material')).not.toHaveValue('')
    expect(screen.getByLabelText('Cantidad')).toHaveValue('2.5')
  })

  it('otro rechazo (p. ej. 404 MATERIAL_NO_ENCONTRADO): mensaje y datos conservados, SIN refrescar', async () => {
    const user = userEvent.setup()
    crearMutate.mockImplementation((_p, opciones) =>
      opciones?.onError?.(errorHttp(404, 'MATERIAL_NO_ENCONTRADO')),
    )
    const { invalidate } = renderForm()

    await llenarLinea(user)
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(invalidate).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Material')).not.toHaveValue('')
    expect(screen.getByLabelText('Cantidad')).toHaveValue('2.5')
  })

  it('error de carga del origen: alerta con «Reintentar» (C-10, nunca origen vacío)', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    mockedUseOpcionesOrigenReferencia.mockReturnValue({
      general: estadoGeneral(undefined, {
        isError: true,
        error: new Error('500'),
        refetch,
      }),
      fo: estadoFo([foOpcion()]),
    })
    renderForm()

    expect(screen.getByRole('alert')).toHaveTextContent(
      'No se pudo cargar el Inventario General.',
    )
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })
})
