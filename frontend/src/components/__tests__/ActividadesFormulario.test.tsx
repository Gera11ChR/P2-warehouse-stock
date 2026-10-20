import { describe, expect, it, vi } from 'vitest'
import type { Mock } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ActividadesFormulario, {
  MAX_CELDAS,
  PLACEHOLDER_CLIENTES,
  PLACEHOLDER_DIRECCIONES,
} from '../ActividadesFormulario'
import type { ActividadCreatePayload } from '../../types'

// ============================================================================
// FORMULARIO — CAPTURA DE ACTIVIDADES (Etapa 1, T10)
// REQ-ACT-005 (cabecera, placeholders, obligatorios), REQ-ACT-006 (celdas,
// "+ Agregar", descarte de vacías), REQ-ACT-007 (comentarios opcionales).
// Validación SOLO de forma: aquí se fija el contrato de captura; el backend
// sigue siendo la autoridad.
// ============================================================================

function renderFormulario(
  props: Partial<{
    seguimientoId: number | null
    enviando: boolean
    onSubmit: (payload: ActividadCreatePayload) => void
  }> = {},
) {
  const onSubmit = (props.onSubmit ?? vi.fn()) as Mock<
    (payload: ActividadCreatePayload) => void
  >
  render(
    <ActividadesFormulario
      seguimientoId={
        props.seguimientoId === undefined ? 9 : props.seguimientoId
      }
      enviando={props.enviando ?? false}
      onSubmit={onSubmit}
    />,
  )
  return { onSubmit }
}

async function llenarCamposObligatorios(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.type(screen.getByLabelText('Vehículo'), 'Camioneta 12')
  await user.type(screen.getByLabelText('Nombre Cliente(s)'), 'Cliente A')
  await user.type(screen.getByLabelText('Dirección(es)'), 'Calle 1')
  await user.type(screen.getByLabelText('Actividad realizada 1'), 'Tendido')
}

describe('ActividadesFormulario — cabecera (REQ-ACT-005)', () => {
  it('Fecha es de solo lectura con la etiqueta «Automatizado»', () => {
    renderFormulario()
    const fecha = screen.getByLabelText('Fecha') as HTMLInputElement
    expect(fecha).toHaveValue('Automatizado')
    expect(fecha.readOnly).toBe(true)
    expect(fecha.disabled).toBe(true)
  })

  it('muestra los placeholders EXACTOS de Cliente(s) y Dirección(es)', () => {
    renderFormulario()
    expect(
      screen.getByPlaceholderText(PLACEHOLDER_CLIENTES),
    ).toBeInTheDocument()
    expect(
      screen.getByPlaceholderText(PLACEHOLDER_DIRECCIONES),
    ).toBeInTheDocument()
  })

  it('RF-3: sin seguimiento pendiente todo el formulario queda deshabilitado', () => {
    const { onSubmit } = renderFormulario({ seguimientoId: null })
    // El bloqueo vive en el <fieldset disabled>: todos los controles quedan
    // inoperantes (incluidos los que no tienen el atributo disabled propio).
    const fieldset = screen.getByLabelText('Vehículo').closest('fieldset')
    expect(fieldset).not.toBeNull()
    expect(fieldset).toHaveAttribute('disabled')
    for (const campo of [
      'Vehículo',
      'Nombre Cliente(s)',
      'Dirección(es)',
      'Comentarios (opcional)',
      'Actividad realizada 1',
    ]) {
      expect(screen.getByLabelText(campo)).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: '+ Agregar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('ActividadesFormulario — celdas de actividades (REQ-ACT-006)', () => {
  it('inicia con UNA celda vacía', () => {
    renderFormulario()
    expect(screen.getByLabelText('Actividad realizada 1')).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Actividad realizada 2'),
    ).not.toBeInTheDocument()
  })

  it('«+ Agregar» añade celdas hasta el máximo de 30 y luego se deshabilita', async () => {
    const user = userEvent.setup()
    renderFormulario()
    const boton = screen.getByRole('button', { name: '+ Agregar' })

    await user.click(boton)
    expect(screen.getByLabelText('Actividad realizada 2')).toBeInTheDocument()

    for (let i = 2; i < MAX_CELDAS; i++) {
      await user.click(boton)
    }
    expect(
      screen.getByLabelText(`Actividad realizada ${MAX_CELDAS}`),
    ).toBeInTheDocument()
    expect(boton).toBeDisabled()
  })

  it('descarta las celdas vacías y recorta las escritas antes de enviar', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFormulario()
    await llenarCamposObligatorios(user)
    await user.clear(screen.getByLabelText('Actividad realizada 1'))
    await user.type(screen.getByLabelText('Actividad realizada 1'), '  Tendido  ')
    await user.click(screen.getByRole('button', { name: '+ Agregar' }))
    await user.click(screen.getByRole('button', { name: '+ Agregar' }))
    await user.type(screen.getByLabelText('Actividad realizada 3'), 'Fusión')

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      seguimiento_id: 9,
      vehiculo: 'Camioneta 12',
      clientes: 'Cliente A',
      direcciones: 'Calle 1',
      actividades: ['Tendido', 'Fusión'],
      comentarios: null,
    })
  })
})

describe('ActividadesFormulario — validación de forma (RF-5/RF-6/RF-7)', () => {
  it('exige Vehículo, Cliente(s), Dirección(es) y al menos una actividad', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFormulario()

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0)
    for (const mensaje of [
      'El vehículo es obligatorio.',
      'El nombre del cliente es obligatorio.',
      'La dirección es obligatoria.',
      'Registre al menos una actividad realizada (máx. 30).',
    ]) {
      expect(screen.getByText(mensaje)).toBeInTheDocument()
    }
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('vehículo de más de 100 caracteres se rechaza con mensaje propio', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFormulario()
    await user.type(screen.getByLabelText('Nombre Cliente(s)'), 'Cliente A')
    await user.type(screen.getByLabelText('Dirección(es)'), 'Calle 1')
    await user.type(screen.getByLabelText('Actividad realizada 1'), 'Tendido')
    // fireEvent salta maxLength del input para ejercitar la regla del schema.
    fireEvent.change(screen.getByLabelText('Vehículo'), {
      target: { value: 'x'.repeat(101) },
    })

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(
      screen.getByText('El vehículo admite máximo 100 caracteres.'),
    ).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('los errores se limpian al volver a escribir', async () => {
    const user = userEvent.setup()
    renderFormulario()
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0)

    await user.type(screen.getByLabelText('Vehículo'), 'C')

    expect(screen.queryAllByRole('alert')).toHaveLength(0)
  })

  it('comentarios vacíos se envían como null; con texto se envían tal cual (REQ-ACT-007)', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderFormulario()
    await llenarCamposObligatorios(user)

    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ comentarios: null }),
    )

    onSubmit.mockClear()
    await user.type(screen.getByLabelText('Comentarios (opcional)'), 'Sin novedad')
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ comentarios: 'Sin novedad' }),
    )
  })

  it('estado «enviando»: botón deshabilitado con texto «Confirmando…» (RF-17)', () => {
    renderFormulario({ enviando: true })
    const boton = screen.getByRole('button', { name: 'Confirmando…' })
    expect(boton).toBeDisabled()
    expect(screen.getByLabelText('Vehículo')).toBeDisabled()
  })
})
