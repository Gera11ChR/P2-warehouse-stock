import { describe, expect, it } from 'vitest'
import { AxiosError } from 'axios'
import { mensajeErrorApi } from '../errorMensaje'

// RF-6 / RF-8 (capa UX): mensajes operativos para 400/403/422 de mutaciones.

function errorHttp(status: number, data: unknown): AxiosError {
  return new AxiosError('x', 'ERR', undefined, undefined, {
    status,
    data,
    statusText: '',
    headers: {},
    config: {} as never,
  })
}

describe('mensajeErrorApi', () => {
  it('RF-8: 403 muestra el mensaje canónico del backend (rol administrador)', () => {
    expect(
      mensajeErrorApi(
        errorHttp(403, {
          error: { code: 'AUTHORIZATION_FAILED', message: 'Se requiere rol administrador' },
        }),
      ),
    ).toBe('Se requiere rol administrador')
  })

  it('RF-6: 400 canónico se muestra tal cual', () => {
    expect(
      mensajeErrorApi(
        errorHttp(400, {
          error: { code: 'X', message: 'La cantidad o el stock resultante excede el rango soportado' },
        }),
      ),
    ).toMatch(/excede el rango/)
  })

  it.each([
    ['decimal_max_places', 'valor_unitario', /Valor Unitario admite máximo 3 decimales/],
    ['decimal_max_places', 'stock_actual', /Stock Actual admite máximo 3 decimales/],
    ['decimal_max_digits', 'cantidad', /excede el máximo permitido \(999,999,999\.999\)/],
    ['greater_than_equal', 'valor_unitario', /Valor Unitario no puede ser negativo/],
    ['greater_than', 'cantidad', /debe ser mayor que 0/],
    ['decimal_parsing', 'nuevo_stock', /no es un número válido/],
  ])('RF-6/RF-8: 422 %s en %s', (type, campo, esperado) => {
    expect(
      mensajeErrorApi(
        errorHttp(422, { detail: [{ type, loc: ['body', campo], msg: 'x' }] }),
      ),
    ).toMatch(esperado)
  })

  it('RF-1: 422 por campo no declarado (p. ej. modulo) no filtra el nombre técnico', () => {
    const m = mensajeErrorApi(
      errorHttp(422, {
        detail: [{ type: 'extra_forbidden', loc: ['body', 'modulo'], msg: 'x' }],
      }),
    )
    expect(m).toMatch(/campo no permitido/)
    expect(m).not.toContain('modulo')
  })

  it('usa el fallback cuando el error no es reconocible', () => {
    expect(mensajeErrorApi(new Error('boom'))).toBe('Ocurrió un error')
    expect(mensajeErrorApi(errorHttp(500, {}), 'Falló')).toBe('Falló')
    expect(
      mensajeErrorApi(errorHttp(422, { detail: [{ type: 'x', loc: ['body', 'otro'], msg: '' }] })),
    ).toBe('Ocurrió un error')
  })
})
