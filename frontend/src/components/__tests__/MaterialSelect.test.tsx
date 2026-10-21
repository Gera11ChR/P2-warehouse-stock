import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MaterialSelect from '../MaterialSelect'
import { claveOpcion } from '../../utils/referenciaOrigen'
import type {
  EstadoOrigenOpciones,
  OpcionOrigenFo,
  OpcionOrigenGeneral,
} from '../../hooks/useReferencia'

// REQ-REF-013 (Q5/P-8): selector dependiente del origen con una opción por
// sección GENERAL («DESCRIPCIÓN (stock) · SECCIÓN»), stock copiado tal cual
// (nunca sumado), exclusión de materiales ya presentes y FAIL-CLOSED ante
// error de carga del origen (reintento; jamás origen vacío ni stock 0).

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

function renderSelect(
  props: Partial<Parameters<typeof MaterialSelect>[0]> = {},
) {
  const defaults = {
    id: 'material',
    origen: 'general' as const,
    estado: estadoGeneral([generalOpcion()]),
    excluidos: new Set<number>(),
    value: '',
    onChange: vi.fn(),
  }
  const merged = { ...defaults, ...props }
  return render(<MaterialSelect {...merged} />)
}

describe('MaterialSelect — opciones por origen (REQ-REF-013)', () => {
  it('General: etiqueta «DESCRIPCIÓN (stock) · SECCIÓN», una opción por sección (sin sumar stock)', () => {
    renderSelect({
      estado: estadoGeneral([
        generalOpcion({ almacen_id: 1, stock_actual: 40 }),
        generalOpcion({ almacen_id: 2, nombre_seccion: 'Inventario Norte', stock_actual: 12 }),
      ]),
    })
    const select = screen.getByLabelText('Material')
    const textos = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(textos).toEqual([
      '— Seleccione material —',
      'Cinta aislante (40) · Inventario General',
      'Cinta aislante (12) · Inventario Norte',
    ])
    // El stock NUNCA se suma en el cliente: cada opción conserva su fila.
    expect(select).toHaveTextContent('(12)')
    expect(select).toHaveTextContent('(40)')
    expect(select).not.toHaveTextContent('(52)')
  })

  it('FO: etiqueta «DESCRIPCIÓN (stock)» sin sufijo de sección', () => {
    renderSelect({
      origen: 'fo',
      estado: {
        options: [foOpcion()],
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      },
    })
    const select = screen.getByLabelText('Material')
    expect(
      within(select).getByRole('option', { name: /Fibra drop 1 hilo \(2,?500\)/ }),
    ).toBeInTheDocument()
    expect(select).not.toHaveTextContent('·')
  })

  it('excluye los materiales ya presentes (pero conserva el valor elegido)', () => {
    const elegida = generalOpcion({ material_id: 10 })
    renderSelect({
      value: claveOpcion(elegida),
      excluidos: new Set([10]),
      estado: estadoGeneral([
        elegida,
        generalOpcion({
          material_id: 10,
          almacen_id: 2,
          nombre_seccion: 'Inventario Norte',
        }),
        generalOpcion({ material_id: 11, descripcion: 'Acopladores' }),
      ]),
    })
    const select = screen.getByLabelText('Material')
    const opciones = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    // La opción elegida se conserva; la OTRA opción del material excluido
    // no se ofrece; los materiales no excluidos sí.
    expect(opciones).toEqual([
      '— Seleccione material —',
      'Cinta aislante (40) · Inventario General',
      'Acopladores (40) · Inventario General',
    ])
    expect(
      within(select).queryByRole('option', { name: /Inventario Norte/ }),
    ).not.toBeInTheDocument()
  })

  it('el filtro de texto reduce las opciones sin tocarlas', async () => {
    const user = userEvent.setup()
    renderSelect({
      estado: estadoGeneral([
        generalOpcion({ material_id: 10, descripcion: 'Cinta aislante' }),
        generalOpcion({ material_id: 11, descripcion: 'Acopladores' }),
      ]),
    })
    await user.type(screen.getByLabelText('Filtrar materiales del Inventario General'), 'acopl')
    const select = screen.getByLabelText('Material')
    expect(
      within(select).getByRole('option', { name: /Acopladores/ }),
    ).toBeInTheDocument()
    expect(
      within(select).queryByRole('option', { name: /Cinta aislante/ }),
    ).not.toBeInTheDocument()
  })

  it('elegir una opción entrega el objeto completo de la opción', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const opcion = generalOpcion({ material_id: 11, descripcion: 'Acopladores' })
    renderSelect({
      onChange,
      estado: estadoGeneral([generalOpcion(), opcion]),
    })
    await user.selectOptions(screen.getByLabelText('Material'), claveOpcion(opcion))
    expect(onChange).toHaveBeenCalledWith(opcion)
  })

  it('sin opciones: mensaje explícito, nunca un origen vacío silencioso', () => {
    renderSelect({ estado: estadoGeneral([]) })
    expect(
      screen.getByText(/No hay materiales disponibles en el Inventario General/),
    ).toBeInTheDocument()
  })
})

describe('MaterialSelect — estados fail-closed (C-10, REQ-REF-016)', () => {
  it('carga del origen fallida: alerta con «Reintentar» y SIN selector', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    renderSelect({
      estado: estadoGeneral(undefined, {
        isError: true,
        error: new Error('500'),
        refetch,
      }),
    })
    expect(screen.getByRole('alert')).toHaveTextContent(
      'No se pudo cargar el Inventario General.',
    )
    expect(screen.queryByLabelText('Material')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('mientras carga: estado anunciado y sin opciones válidas', () => {
    renderSelect({
      estado: estadoGeneral(undefined, {
        isLoading: true,
        refetch: vi.fn(),
      }),
    })
    expect(screen.getByRole('status')).toHaveTextContent(
      'Cargando materiales del Inventario General…',
    )
  })
})
