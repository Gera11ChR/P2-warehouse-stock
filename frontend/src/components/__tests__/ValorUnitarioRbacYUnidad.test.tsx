import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FibraMaterialForm from '../FibraMaterialForm'
import ConfigLocalForm from '../ConfigLocalForm'
import type {
  Categoria,
  FibraMaterialRowEditable,
  InventarioEquipoRow,
  Ums,
} from '../../types'

// ============================================================================
// T7 (Fase 8) — complementos de trazabilidad en la capa de formularios:
//  · RF-8 (RBAC VISUAL, no seguridad): en el formulario del Inventario FO un
//    no administrador ve el Valor Unitario deshabilitado y NUNCA lo envía.
//  · RF-3 (Option-driven): «Modificar» en el Inventario por Unidad muestra el
//    Valor Unitario en SOLO LECTURA (el valor pertenece al catálogo).
// ============================================================================

const categorias: Categoria[] = [{ id: 1, nombre: 'Fibra', is_active: true }]
const ums: Ums[] = [{ id: 1, nombre: 'PZ', is_active: true }]

const FILA_FO: FibraMaterialRowEditable = {
  material_id: 1,
  codigo: 'FO-1',
  descripcion: 'Cable FO',
  u_m: 'PZ',
  stock_minimo: null,
  valor_unitario: 3.5,
  categoria_id: 1,
  categoria: 'Fibra',
}

describe('FibraMaterialForm — RBAC visual del Valor Unitario (RF-8)', () => {
  it('con esAdmin=false el campo está deshabilitado con su valor y valor_unitario nunca viaja', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <FibraMaterialForm
        initial={FILA_FO}
        stockActual={10}
        alertaStock={false}
        categorias={categorias}
        ums={ums}
        esAdmin={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    )

    const campo = screen.getByLabelText('Valor Unitario (MXN)')
    expect(campo).toBeDisabled()
    expect(campo).toHaveValue('3.5')
    expect(
      screen.getByText('Solo un administrador puede modificar el Valor Unitario.'),
    ).toBeInTheDocument()

    // Otro campo editado sí viaja; el Valor Unitario jamás.
    const desc = screen.getByDisplayValue('Cable FO')
    await user.clear(desc)
    await user.type(desc, 'Cable FO 2')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const payload = onSubmit.mock.calls[0][0]
    expect(payload.descripcion).toBe('Cable FO 2')
    expect(payload).not.toHaveProperty('valor_unitario')
  })
})

const FILA_UNIDAD: InventarioEquipoRow = {
  equipo_id: 1,
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  stock_minimo: 5,
  stock_actual: 42,
  valor_unitario: 12.345,
  alerta_stock: false,
  ultimo_movimiento_id: 7,
  stock_minimo_local: null,
  categoria_local_id: null,
  um_local_id: null,
  stock_minimo_efectivo: 5,
  categoria_efectiva: 'Cables',
  um_efectivo: 'METRO (M)',
}

describe('RF-3 (Option-driven): Modificar en el Inventario por Unidad', () => {
  // RF-3 (Option-driven): «Modificar» en el Inventario por Unidad presenta el
  // Valor Unitario como TEXTO (solo lectura) en su bloque «Material (solo
  // lectura)»; la columna de la tabla también es de solo lectura.
  it('RF-3: el formulario Modificar Unidad muestra el Valor Unitario (12.345 MXN) como texto, sin control editable', () => {
    render(
      <ConfigLocalForm
        material={FILA_UNIDAD}
        categorias={categorias}
        ums={ums}
        onSubmit={vi.fn()}
        onCancel={() => undefined}
      />,
    )

    const etiqueta = screen.getByText('Valor Unitario')
    expect(etiqueta.nextElementSibling).toHaveTextContent('12.345 MXN')
    expect(screen.queryByLabelText(/Valor Unitario/i)).not.toBeInTheDocument()
  })
})
