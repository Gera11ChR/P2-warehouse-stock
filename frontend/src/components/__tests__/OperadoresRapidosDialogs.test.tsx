import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SumarCantidadDialog from '../SumarCantidadDialog'
import type { MaterialOperacionContexto } from '../SumarCantidadDialog'
import MoverMaterialDialog from '../MoverMaterialDialog'
import type {
  DestinoMover,
  MoverMaterialDialogProps,
} from '../MoverMaterialDialog'
import {
  construirPayloadMover,
  construirPayloadSumar,
} from '../../utils/operadorPayload'

const material: MaterialOperacionContexto = {
  codigo: 'CON-ACO-001',
  descripcion: 'ACOPLADORES',
  um: 'PZ',
  stockActual: 12,
  origenLabel: 'Inventario General',
}

const destinos: DestinoMover[] = [
  { value: '1', label: 'Inventario General', tipo: 'GENERAL' },
  { value: '2', label: 'Inventario FO', tipo: 'FO' },
]

/** Host con un botón disparador para verificar el retorno de foco. */
function SumarHost(props: {
  onSubmit?: (c: number) => void
  onEditar?: () => void
  isSubmitting?: boolean
  errorMessage?: string | null
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        abrir
      </button>
      <SumarCantidadDialog
        open={open}
        material={material}
        onClose={() => setOpen(false)}
        {...props}
      />
    </>
  )
}

function MoverHost(
  props: Partial<Omit<MoverMaterialDialogProps, 'open' | 'onClose' | 'material'>>,
) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        abrir
      </button>
      <MoverMaterialDialog
        open={open}
        material={material}
        destinos={destinos}
        origenValue="1"
        onClose={() => setOpen(false)}
        {...props}
      />
    </>
  )
}

describe('SumarCantidadDialog (REQ-P2-INV-001)', () => {
  it('es modal, nombrado, enfoca la cantidad y muestra el contexto de la operación', async () => {
    const user = userEvent.setup()
    render(<SumarHost onSubmit={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))

    const dialogo = screen.getByRole('dialog', { name: '+ Cantidad' })
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByLabelText('Cantidad a sumar')).toHaveFocus()

    const resumen = within(screen.getByLabelText('Resumen de la operación'))
    expect(resumen.getByText('CON-ACO-001')).toBeInTheDocument()
    expect(resumen.getByText('Inventario General')).toBeInTheDocument()
    expect(resumen.getByText('12 PZ')).toBeInTheDocument()
  })

  it('Esc cierra y devuelve el foco al elemento que lo abrió', async () => {
    const user = userEvent.setup()
    render(<SumarHost onSubmit={vi.fn()} />)
    const abrir = screen.getByRole('button', { name: 'abrir' })
    await user.click(abrir)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(abrir).toHaveFocus()
  })

  it('atrapa el foco: Tab desde el último control vuelve al primero y Shift+Tab al último', async () => {
    const user = userEvent.setup()
    render(<SumarHost onSubmit={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))
    const cerrar = screen.getByRole('button', { name: 'Cerrar' })
    const input = screen.getByLabelText('Cantidad a sumar')

    // Con cantidad inválida el botón de confirmar está deshabilitado: el
    // último enfocable es «Cancelar».
    const cancelar = screen.getByRole('button', { name: 'Cancelar' })
    cancelar.focus()
    await user.tab()
    expect(cerrar).toHaveFocus()

    await user.tab({ shift: true })
    expect(cancelar).toHaveFocus()
    expect(input).not.toHaveFocus()
  })

  it('valida decimal > 0, proyecta el stock como «Proyección visual» y nombra la acción', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<SumarHost onSubmit={onSubmit} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))

    const confirmar = screen.getByRole('button', { name: 'Sumar cantidad' })
    expect(confirmar).toBeDisabled()

    const input = screen.getByLabelText('Cantidad a sumar')
    await user.type(input, '0')
    await user.tab()
    expect(
      screen.getAllByText('La cantidad debe ser mayor que 0.').length,
    ).toBeGreaterThan(0)
    expect(confirmar).toBeDisabled()

    await user.clear(input)
    await user.type(input, '5')
    expect(screen.getByText('Proyección visual')).toBeInTheDocument()
    expect(screen.getByText(/El saldo definitivo lo confirma el servidor/)).toBeInTheDocument()
    expect(screen.getByText('17')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Sumar 5 PZ a CON-ACO-001' }),
    )
    expect(onSubmit).toHaveBeenCalledWith(5)
  })

  it('sin onSubmit deja Confirmar deshabilitado con motivo visible', async () => {
    const user = userEvent.setup()
    render(<SumarHost />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))
    await user.type(screen.getByLabelText('Cantidad a sumar'), '5')
    expect(
      screen.getByRole('button', { name: 'Sumar 5 PZ a CON-ACO-001' }),
    ).toBeDisabled()
    expect(screen.getByText(/aún no está habilitada/)).toBeInTheDocument()
  })

  it('mientras envía bloquea el doble envío y Esc; muestra el error traducido con role=alert', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <SumarCantidadDialog
        open
        material={material}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting
        errorMessage="No fue posible completar la operación. Actualiza la información e intenta nuevamente."
      />,
    )
    expect(screen.getByRole('button', { name: 'Procesando…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent(/No fue posible completar/)
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    rerender(
      <SumarCantidadDialog
        open={false}
        material={material}
        onClose={vi.fn()}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('MoverMaterialDialog (REQ-P2-INV-003/004/005)', () => {
  it('el destino NO tiene valor por defecto, excluye el origen y la cantidad por defecto es el stock completo', async () => {
    const user = userEvent.setup()
    render(<MoverHost onSubmit={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))

    expect(screen.getByRole('dialog', { name: 'Mover' })).toBeInTheDocument()
    const select = screen.getByLabelText('Inventario destino')
    expect(select).toHaveFocus()
    expect(select).toHaveValue('')
    const opciones = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['— Selecciona destino —', 'Inventario FO'])
    expect(screen.getByLabelText('Cantidad a mover')).toHaveValue('12')
    expect(
      screen.getByRole('button', { name: 'Mover material' }),
    ).toBeDisabled()
  })

  it('confirmación explícita: nombra cantidad, material y destino; envía {destino, cantidad}', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<MoverHost onSubmit={onSubmit} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))

    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    const cantidad = screen.getByLabelText('Cantidad a mover')
    await user.clear(cantidad)
    await user.type(cantidad, '4')

    const resumen = within(screen.getByLabelText('Resumen de la operación'))
    expect(resumen.getByText('Inventario FO')).toBeInTheDocument()
    expect(resumen.getByText('4 PZ')).toBeInTheDocument()
    expect(screen.getByText('Proyección visual')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Mover 4 PZ a Inventario FO' }),
    )
    expect(onSubmit).toHaveBeenCalledWith({
      destino: '2',
      destinoTipo: 'FO',
      cantidad: 4,
    })
  })

  it('bloquea cantidades que exceden el stock visible con mensaje y sin enviar', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<MoverHost onSubmit={onSubmit} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))

    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    const cantidad = screen.getByLabelText('Cantidad a mover')
    await user.clear(cantidad)
    await user.type(cantidad, '13')

    expect(
      screen.getByText('No puedes mover más del stock disponible (12).'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mover material' })).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('sin destinos disponibles lo explica y deshabilita el select', async () => {
    const user = userEvent.setup()
    render(
      <MoverHost destinos={[{ value: '1', label: 'Inventario General' }]} />,
    )
    await user.click(screen.getByRole('button', { name: 'abrir' }))
    expect(
      screen.getByText('No hay otros inventarios disponibles como destino.'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Inventario destino')).toBeDisabled()
  })
})

// ============================================================================
// T4.3 — Formularios: validaciones, accesibilidad y contrato con el builder
// ============================================================================

async function abrirSumar(onSubmit: ((c: number) => void) | undefined = vi.fn()) {
  const user = userEvent.setup()
  render(<SumarHost onSubmit={onSubmit} />)
  await user.click(screen.getByRole('button', { name: 'abrir' }))
  return { user, onSubmit, input: screen.getByLabelText('Cantidad a sumar') }
}

describe('+Cantidad — validación estricta del campo (REQ-P2-INV-001)', () => {
  it('es un campo de texto decimal (inputMode=decimal) con ayuda asociada', async () => {
    const { input } = await abrirSumar()
    expect(input).toHaveAttribute('inputmode', 'decimal')
    expect(input).toHaveAttribute('type', 'text')
    expect(input).toHaveAttribute('aria-invalid', 'false')
    const ayuda = document.getElementById(
      input.getAttribute('aria-describedby') ?? '',
    )
    expect(ayuda).toHaveTextContent('Número mayor que 0, hasta 3 decimales')
  })

  it.each([
    ['0', 'La cantidad debe ser mayor que 0.'],
    ['-5', 'La cantidad no puede ser negativa.'],
    ['1,5', 'Usa punto como separador decimal (por ejemplo 2.5).'],
    ['1.0005', 'Máximo 3 decimales; no se redondea automáticamente.'],
    ['1e3', 'No uses notación científica; escribe el número completo.'],
    ['1e-4', 'No uses notación científica; escribe el número completo.'],
    [
      'abc',
      'Ingresa solo dígitos y, si aplica, un punto decimal (por ejemplo 0.5).',
    ],
    ['5 ', 'La cantidad no debe contener espacios.'],
    ['  ', 'La cantidad no debe contener espacios.'],
    ['1000000000', 'La cantidad máxima permitida es 999,999,999.999.'],
  ])('rechaza «%s» con mensaje en línea, aria-invalid y botón deshabilitado con motivo', async (texto, mensaje) => {
    const { user, input } = await abrirSumar()
    await user.type(input, texto)

    expect(input).toHaveAttribute('aria-invalid', 'true')
    const descripcion = document.getElementById(
      input.getAttribute('aria-describedby') ?? '',
    )
    expect(descripcion).toHaveTextContent(mensaje)
    expect(screen.getByRole('button', { name: 'Sumar cantidad' })).toBeDisabled()
    // Motivo visible junto al botón deshabilitado.
    expect(screen.getByText(`Confirmar deshabilitado: ${mensaje}`)).toBeInTheDocument()
    expect(screen.queryByText('Proyección visual')).not.toBeInTheDocument()
  })

  it('el campo vacío no regaña al abrir; sí tras salir del campo', async () => {
    const { user, input } = await abrirSumar()
    expect(input).toHaveAttribute('aria-invalid', 'false')
    expect(screen.getByRole('button', { name: 'Sumar cantidad' })).toBeDisabled()
    expect(screen.getByText('Confirmar deshabilitado: Ingresa la cantidad.')).toBeInTheDocument()
    await user.tab()
    expect(input).toHaveAttribute('aria-invalid', 'true')
  })

  it.each([
    ['2.5', 2.5],
    ['1.5', 1.5],
    ['0.001', 0.001],
    ['1.250', 1.25],
  ])('acepta la cantidad decimal «%s» y envía %d', async (texto, esperado) => {
    const { user, input, onSubmit } = await abrirSumar()
    await user.type(input, `${texto}{Enter}`)
    expect(input).toHaveAttribute('aria-invalid', 'false')
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith(esperado)
  })

  it('con decimales proyecta el stock formateado (12 + 2.5 = 14.5) y nombra la acción', async () => {
    const { user, input } = await abrirSumar()
    await user.type(input, '2.5')
    expect(screen.getByText('Proyección visual')).toBeInTheDocument()
    expect(screen.getByText('14.5')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Sumar 2.5 PZ a CON-ACO-001' }),
    ).toBeEnabled()
  })

  it('acepta el máximo decimal cuando el stock resultante no lo desborda', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <SumarCantidadDialog
        open
        material={{ ...material, stockActual: 0 }}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    )
    await user.type(
      screen.getByLabelText('Cantidad a sumar'),
      '999999999.999{Enter}',
    )
    expect(onSubmit).toHaveBeenCalledWith(999_999_999.999)
  })

  it('bloquea si el stock resultante superaría el máximo decimal (preliminar)', async () => {
    const { user, input } = await abrirSumar()
    await user.type(input, '999999999.999')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(
      screen.getAllByText(/stock resultante superaría el máximo permitido/).length,
    ).toBeGreaterThan(0)
  })

  it('Enter envía con cantidad válida', async () => {
    const { user, input, onSubmit } = await abrirSumar()
    await user.type(input, '7{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith(7)
  })

  it('Enter con cantidad inválida no envía, muestra el error y mantiene el foco en el campo', async () => {
    const { user, input, onSubmit } = await abrirSumar()
    await user.click(input)
    await user.keyboard('{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveFocus()
    expect(document.getElementById(input.getAttribute('aria-describedby') ?? '')).toHaveTextContent(
      'Ingresa la cantidad.',
    )
  })

  it('la proyección es visual: rotulada, con el stock del servidor y sin cambiar el «Stock actual»', async () => {
    const { user, input } = await abrirSumar()
    await user.type(input, '8')
    expect(screen.getByText('Proyección visual')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    // El resumen sigue mostrando el stock confirmado, no el proyectado.
    const resumen = within(screen.getByLabelText('Resumen de la operación'))
    expect(resumen.getByText('12 PZ')).toBeInTheDocument()
    expect(resumen.queryByText('20 PZ')).not.toBeInTheDocument()
  })

  it('notifica la edición para que el padre limpie el error del servidor', async () => {
    const onEditar = vi.fn()
    const user = userEvent.setup()
    render(<SumarHost onSubmit={vi.fn()} onEditar={onEditar} />)
    await user.click(screen.getByRole('button', { name: 'abrir' }))
    await user.type(screen.getByLabelText('Cantidad a sumar'), '12')
    expect(onEditar).toHaveBeenCalledTimes(2)
  })

  it('muestra en el slot de error el texto traducido y no cierra el diálogo', async () => {
    render(
      <SumarCantidadDialog
        open
        material={material}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        errorMessage="El material no existe, está inactivo o aún no tiene registro en este inventario."
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/aún no tiene registro/)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('integración con el builder: la cantidad capturada produce el payload del contrato', async () => {
    const onSubmit = vi.fn()
    const { user, input } = await abrirSumar(onSubmit)
    await user.type(input, '5{Enter}')
    const [cantidad] = onSubmit.mock.calls[0] as [number]
    expect(
      construirPayloadSumar({
        inventario: 'GENERAL',
        materialId: 99,
        cantidad,
        claveIdempotencia: 'sumar-k1',
      }),
    ).toEqual({
      ok: true,
      payload: {
        destino: 'GENERAL',
        material_id: 99,
        cantidad: 5,
        clave_idempotencia: 'sumar-k1',
      },
    })
  })
})

async function abrirMover(
  props: Parameters<typeof MoverHost>[0] = { onSubmit: vi.fn() },
) {
  const user = userEvent.setup()
  render(<MoverHost {...props} />)
  await user.click(screen.getByRole('button', { name: 'abrir' }))
  return {
    user,
    select: screen.getByLabelText('Inventario destino'),
    cantidad: screen.getByLabelText('Cantidad a mover'),
  }
}

describe('Mover — destino y cantidad (REQ-P2-INV-003/004/005)', () => {
  it('el select es obligatorio y nace vacío; aria-required', async () => {
    const { select } = await abrirMover()
    expect(select).toHaveValue('')
    expect(select).toHaveAttribute('aria-required', 'true')
  })

  it('excluye el origen por tipo: desde GENERAL solo ofrece Inventario FO (aunque otra sección sea GENERAL)', async () => {
    const { select } = await abrirMover({
      onSubmit: vi.fn(),
      origenValue: '1',
      origenTipo: 'GENERAL',
      destinos: [
        ...destinos,
        { value: '9', label: 'Almacén Norte', tipo: 'GENERAL' },
      ],
    })
    const opciones = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['— Selecciona destino —', 'Inventario FO'])
  })

  it('desde Inventario FO solo ofrece Inventario General: FO → FO no se ofrece (DESTINO_IGUAL_ORIGEN)', async () => {
    const { select } = await abrirMover({
      onSubmit: vi.fn(),
      origenValue: '2',
      origenTipo: 'FO',
      destinos: [
        ...destinos,
        // Otro destino FO (p. ej. duplicado) tampoco puede ofrecerse.
        { value: '8', label: 'Inventario FO (otro)', tipo: 'FO' },
      ],
    })
    const opciones = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['— Selecciona destino —', 'Inventario General'])
  })

  it('deduce el tipo del origen a partir de origenValue cuando no se informa origenTipo', async () => {
    const { select } = await abrirMover({ onSubmit: vi.fn(), origenValue: '2' })
    const opciones = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['— Selecciona destino —', 'Inventario General'])
    expect(opciones).not.toContain('Inventario FO')
  })

  it('el destino es obligatorio: sin elegirlo no se puede confirmar y el motivo lo dice', async () => {
    const { select } = await abrirMover()
    expect(screen.getByRole('button', { name: 'Mover material' })).toBeDisabled()
    expect(
      screen.getByText('Confirmar deshabilitado: Selecciona el inventario destino.'),
    ).toBeInTheDocument()
    expect(select).toHaveAttribute('aria-invalid', 'false')
  })

  it('la cantidad por defecto es el stock completo y se puede enviar tal cual', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({ onSubmit })
    expect(cantidad).toHaveValue('12')
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.click(
      screen.getByRole('button', { name: 'Mover 12 PZ a Inventario FO' }),
    )
    expect(onSubmit).toHaveBeenCalledWith({
      destino: '2',
      destinoTipo: 'FO',
      cantidad: 12,
    })
    expect(screen.getByText(/El origen quedaría en 0/)).toBeInTheDocument()
  })

  it.each([
    ['0', 'La cantidad debe ser mayor que 0.'],
    ['-1', 'La cantidad no puede ser negativa.'],
    ['2,5', 'Usa punto como separador decimal (por ejemplo 2.5).'],
    ['1.0005', 'Máximo 3 decimales; no se redondea automáticamente.'],
    ['1e1', 'No uses notación científica; escribe el número completo.'],
    [
      'doce',
      'Ingresa solo dígitos y, si aplica, un punto decimal (por ejemplo 0.5).',
    ],
    ['1 2', 'La cantidad no debe contener espacios.'],
    ['13', 'No puedes mover más del stock disponible (12).'],
  ])('cantidad «%s» inválida: error en línea y sin habilitar el envío', async (texto, mensaje) => {
    const { user, cantidad } = await abrirMover()
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.type(cantidad, texto)

    expect(cantidad).toHaveAttribute('aria-invalid', 'true')
    expect(
      document.getElementById(cantidad.getAttribute('aria-describedby') ?? ''),
    ).toHaveTextContent(mensaje)
    expect(screen.getByRole('button', { name: 'Mover material' })).toBeDisabled()
    expect(screen.getByText(`Confirmar deshabilitado: ${mensaje}`)).toBeInTheDocument()
  })

  it('acepta el borde 1 y el stock completo', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({ onSubmit })
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.type(cantidad, '1{Enter}')
    expect(onSubmit).toHaveBeenLastCalledWith({
      destino: '2',
      destinoTipo: 'FO',
      cantidad: 1,
    })
  })

  it('acepta cantidades decimales parciales (2.5) y las envía como número', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({ onSubmit })
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.type(cantidad, '2.5')
    expect(cantidad).toHaveAttribute('aria-invalid', 'false')
    await user.click(
      screen.getByRole('button', { name: 'Mover 2.5 PZ a Inventario FO' }),
    )
    expect(onSubmit).toHaveBeenCalledWith({
      destino: '2',
      destinoTipo: 'FO',
      cantidad: 2.5,
    })
    // Proyección con decimales: 12 − 2.5 = 9.5
    expect(screen.getByText('9.5')).toBeInTheDocument()
  })

  it('el stock decimal del origen se muestra y se propone completo (12.75)', async () => {
    render(
      <MoverMaterialDialog
        open
        material={{ ...material, stockActual: 12.75 }}
        destinos={destinos}
        origenValue="1"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )
    expect(screen.getByLabelText('Cantidad a mover')).toHaveValue('12.75')
    const resumen = within(screen.getByLabelText('Resumen de la operación'))
    expect(resumen.getByText('12.75 PZ')).toBeInTheDocument()
  })

  it('el tope por stock compara decimales sin error de coma flotante (12.001 > 12.000)', async () => {
    const { user, cantidad } = await abrirMover()
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.type(cantidad, '12.001')
    expect(cantidad).toHaveAttribute('aria-invalid', 'true')
    expect(
      screen.getByText('No puedes mover más del stock disponible (12).'),
    ).toBeInTheDocument()
  })

  it('Enter con el destino sin elegir mueve el foco al select (primer campo inválido) y no envía', async () => {
    const onSubmit = vi.fn()
    const { user, select, cantidad } = await abrirMover({ onSubmit })
    await user.click(cantidad)
    await user.keyboard('{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
    expect(select).toHaveFocus()
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(
      document.getElementById(select.getAttribute('aria-describedby') ?? ''),
    ).toHaveTextContent('Selecciona el inventario destino.')
  })

  it('Enter con destino válido y cantidad inválida mantiene el foco en la cantidad', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({ onSubmit })
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.keyboard('{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
    expect(cantidad).toHaveFocus()
    expect(cantidad).toHaveAttribute('aria-invalid', 'true')
  })

  it('Enter con todo válido envía una sola vez', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({ onSubmit })
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.click(cantidad)
    await user.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('sin stock en el origen: cantidad vacía y mensaje claro, sin poder enviar', async () => {
    const user = userEvent.setup()
    render(
      <MoverMaterialDialog
        open
        material={{ ...material, stockActual: 0 }}
        destinos={destinos}
        origenValue="1"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    )
    const cantidad = screen.getByLabelText('Cantidad a mover')
    expect(cantidad).toHaveValue('')
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.type(cantidad, '1')
    expect(
      screen.getAllByText('No hay stock disponible en el origen para mover.').length,
    ).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Mover material' })).toBeDisabled()
  })

  it('muestra el error del servidor en el slot de error y notifica la edición', async () => {
    const onEditar = vi.fn()
    const user = userEvent.setup()
    render(
      <MoverMaterialDialog
        open
        material={material}
        destinos={destinos}
        origenValue="1"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        onEditar={onEditar}
        errorMessage="La cantidad supera el stock disponible en el inventario de origen."
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/supera el stock disponible/)
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    expect(onEditar).toHaveBeenCalled()
  })

  it('integración con el builder GENERAL -> Inventario FO (sin módulo)', async () => {
    const onSubmit = vi.fn()
    const { user, cantidad } = await abrirMover({
      onSubmit,
      origenValue: '1',
      origenTipo: 'GENERAL',
    })
    await user.selectOptions(screen.getByLabelText('Inventario destino'), '2')
    await user.clear(cantidad)
    await user.type(cantidad, '4{Enter}')
    const [datos] = onSubmit.mock.calls[0] as [
      { destinoTipo: 'GENERAL' | 'FO'; cantidad: number },
    ]
    expect(
      construirPayloadMover({
        origen: 'GENERAL',
        destino: datos.destinoTipo,
        materialId: 5,
        cantidad: datos.cantidad,
      }),
    ).toEqual({
      ok: true,
      payload: {
        origen: 'GENERAL',
        destino: 'FO',
        material_id: 5,
        cantidad: 4,
      },
    })
  })

  it('el payload no contiene campos de módulo y FO → FO / GENERAL → GENERAL son DESTINO_IGUAL_ORIGEN', () => {
    const r = construirPayloadMover({
      origen: 'GENERAL',
      destino: 'FO',
      materialId: 5,
      cantidad: 1.5,
    })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(Object.keys(r.payload).sort()).toEqual([
        'cantidad',
        'destino',
        'material_id',
        'origen',
      ])
    }
    for (const t of ['FO', 'GENERAL'] as const) {
      expect(
        construirPayloadMover({
          origen: t,
          destino: t,
          materialId: 5,
          cantidad: 1,
        }),
      ).toMatchObject({ ok: false, codigo: 'DESTINO_IGUAL_ORIGEN' })
    }
  })

  it('el builder de +Cantidad acepta decimales (2.5) y rechaza más de 3 decimales', () => {
    expect(
      construirPayloadSumar({ inventario: 'FO', materialId: 3, cantidad: 2.5 }),
    ).toEqual({
      ok: true,
      payload: { destino: 'FO', material_id: 3, cantidad: 2.5 },
    })
    expect(
      construirPayloadSumar({
        inventario: 'GENERAL',
        materialId: 3,
        cantidad: 1.0005,
      }),
    ).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
  })
})
