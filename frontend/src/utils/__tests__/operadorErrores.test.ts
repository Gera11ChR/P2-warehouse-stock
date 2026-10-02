import { describe, expect, it } from 'vitest'
import {
  extraerRespuestaError,
  traducirErrorOperador,
} from '../operadorErrores'

const mover = { operacion: 'mover', stockActual: 12, um: 'PZ' } as const
const sumar = { operacion: 'sumar', stockActual: 12, um: 'PZ' } as const

const cuerpo = (message: string, code = 'BUSINESS_RULE_VIOLATION') => ({
  error: { code, message, coordinates: [] },
})

/** Texto técnico que jamás debe llegar al usuario. */
const TECNICO =
  'Stock insuficiente en Origen (Sección ID 7) para el material ID LISTA 55. Disponible: 3, Solicitado: 12'

describe('traducirErrorOperador — por código HTTP', () => {
  it('400 stock insuficiente (mover): apunta a cantidad, cita el stock y no filtra el texto crudo', () => {
    const r = traducirErrorOperador(400, cuerpo(TECNICO), mover)
    expect(r.campo).toBe('cantidad')
    expect(r.resultado).toBe('rechazada')
    expect(r.reintentable).toBe(false)
    expect(r.mensaje).toMatch(/supera el stock disponible/)
    expect(r.mensaje).toContain('12 PZ')
    expect(r.mensaje).toMatch(/No se modificó ningún inventario/)
    expect(r.mensaje).not.toContain('Sección ID')
    expect(r.mensaje).not.toContain('LISTA')
  })

  it('400 cantidad <= 0: mensaje de cantidad mayor que 0', () => {
    const r = traducirErrorOperador(
      400,
      cuerpo('La cantidad a sumar debe ser mayor que cero'),
      sumar,
    )
    expect(r.campo).toBe('cantidad')
    expect(r.mensaje).toMatch(/mayor que 0/)
    expect(r.mensaje).not.toMatch(/cero/)
  })

  it('400 desborde (fuera de rango): cota INT4', () => {
    const r = traducirErrorOperador(
      400,
      cuerpo('integer out of range'),
      sumar,
    )
    expect(r.campo).toBe('cantidad')
    expect(r.mensaje).toContain('2,147,483,647')
  })

  it('400 sin cuerpo reconocible: cae al mensaje de cantidad', () => {
    const r = traducirErrorOperador(400, undefined, sumar)
    expect(r.campo).toBe('cantidad')
    expect(r.mensaje).toMatch(/mayor que 0/)
  })

  it('403: sin alcance, nivel diálogo, sin filtrar actor/ámbito', () => {
    const r = traducirErrorOperador(
      403,
      {
        error: {
          code: 'AUTHORIZATION_FAILED',
          message: 'Actor demo sin scope',
          actor: 'demo-operador',
          required_scope: ['seccion:7'],
        },
      },
      mover,
    )
    expect(r.campo).toBe('dialogo')
    expect(r.mensaje).toMatch(/No tienes permiso/)
    expect(r.mensaje).not.toContain('demo-operador')
    expect(r.mensaje).not.toContain('seccion:7')
    expect(r.codigoServidor).toBe('AUTHORIZATION_FAILED')
  })

  it('404 sumar: sugiere carga inicial; 404 mover: no', () => {
    const body = cuerpo('No se encuentra registro de inventario para el material ID 5')
    const s = traducirErrorOperador(404, body, sumar)
    const m = traducirErrorOperador(404, body, mover)
    expect(s.campo).toBe('dialogo')
    expect(s.mensaje).toMatch(/carga inicial/)
    expect(m.mensaje).toMatch(/inventario de origen/)
    expect(m.mensaje).not.toMatch(/carga inicial/)
    expect(s.mensaje).not.toContain('material ID 5')
  })

  it('409 más de una sección GENERAL activa', () => {
    const r = traducirErrorOperador(
      409,
      cuerpo(
        'Existen 2 filas de inventario del material ID 5 en secciones activas de tipo GENERAL; no es posible determinar un destino único',
      ),
      sumar,
    )
    expect(r.mensaje).toMatch(/más de un Inventario General activo/)
    expect(r.campo).toBe('dialogo')
  })

  it('409 ninguna sección GENERAL activa', () => {
    const r = traducirErrorOperador(
      409,
      cuerpo('No existe una sección GENERAL activa'),
      mover,
    )
    expect(r.mensaje).toMatch(/No hay un Inventario General activo/)
  })

  it('409 clave de idempotencia de otro actor: pide reabrir el diálogo', () => {
    const r = traducirErrorOperador(
      409,
      cuerpo('La clave de idempotencia abc ya fue utilizada por otro actor'),
      mover,
    )
    expect(r.mensaje).toMatch(/vuelve a abrirlo/)
    expect(r.mensaje).not.toContain('abc')
    expect(r.reintentable).toBe(false)
  })

  it('409 IDEMPOTENT_REPLAY: operación ya registrada', () => {
    const r = traducirErrorOperador(
      409,
      cuerpo('Operación ya fue ejecutada (idempotencia)', 'IDEMPOTENT_REPLAY'),
      mover,
    )
    expect(r.mensaje).toMatch(/ya fue registrada/)
    expect(r.codigoServidor).toBe('IDEMPOTENT_REPLAY')
  })

  it('409 genérico: conflicto con el estado actual', () => {
    const r = traducirErrorOperador(409, cuerpo('algo interno raro'), mover)
    expect(r.mensaje).toMatch(/conflicto con el estado actual/)
    expect(r.mensaje).not.toContain('algo interno raro')
  })

  it('422 destino = origen: apunta al destino (solo en mover)', () => {
    const body = cuerpo('El destino debe ser distinto del origen')
    const m = traducirErrorOperador(422, body, mover)
    expect(m.campo).toBe('destino')
    expect(m.mensaje).toMatch(/distinto del origen/)
  })

  it('422 módulo FO ausente (Pydantic): apunta al destino', () => {
    const r = traducirErrorOperador(
      422,
      {
        detail: [
          {
            type: 'value_error',
            loc: ['body'],
            msg: 'Value error, destino_modulo es obligatorio cuando destino = FO.',
          },
        ],
      },
      mover,
    )
    expect(r.campo).toBe('destino')
    expect(r.mensaje).toMatch(/módulo de Fibra Óptica/)
    expect(r.mensaje).not.toContain('destino_modulo')
  })

  it('422 cantidad fuera de INT4 (detail Pydantic less_than_equal)', () => {
    const r = traducirErrorOperador(
      422,
      {
        detail: [
          {
            type: 'less_than_equal',
            loc: ['body', 'cantidad'],
            msg: 'Input should be less than or equal to 2147483647',
          },
        ],
      },
      sumar,
    )
    expect(r.campo).toBe('cantidad')
    expect(r.mensaje).toContain('2,147,483,647')
  })

  it('422 cantidad con tipo inválido: pide entero válido', () => {
    const r = traducirErrorOperador(
      422,
      {
        detail: [
          { type: 'int_parsing', loc: ['body', 'cantidad'], msg: 'bad int' },
        ],
      },
      sumar,
    )
    expect(r.campo).toBe('cantidad')
    expect(r.mensaje).toMatch(/entero válido/)
  })

  it('422 con forma {detail:{error:{...}}} y sin pistas: mensaje genérico', () => {
    const r = traducirErrorOperador(
      422,
      { detail: { error: { code: 'X', message: 'regla genérica' } } },
      mover,
    )
    expect(r.campo).toBe('dialogo')
    expect(r.mensaje).toMatch(/no son válidos/)
    expect(r.mensaje).not.toContain('regla genérica')
    expect(r.codigoServidor).toBe('X')
  })

  it.each([undefined, null, 0])(
    'sin respuesta (status %s): resultado desconocido, reintentable con la misma clave',
    (status) => {
      const r = traducirErrorOperador(status, undefined, mover)
      expect(r.resultado).toBe('desconocido')
      expect(r.reintentable).toBe(true)
      expect(r.mensaje).toMatch(/no duplica/)
    },
  )

  it('5xx: resultado desconocido y reintentable, sin filtrar el cuerpo', () => {
    const r = traducirErrorOperador(
      500,
      { error: { code: 'INTERNAL', message: 'psycopg2 traceback ...' } },
      sumar,
    )
    expect(r.resultado).toBe('desconocido')
    expect(r.reintentable).toBe(true)
    expect(r.mensaje).not.toContain('psycopg2')
  })

  it('otro 4xx (p. ej. 401): rechazo genérico', () => {
    const r = traducirErrorOperador(401, cuerpo('token'), mover)
    expect(r.resultado).toBe('rechazada')
    expect(r.campo).toBe('dialogo')
  })

  it('cuerpo no objeto (string/HTML de proxy) no rompe', () => {
    expect(() =>
      traducirErrorOperador(409, '<html>Bad gateway</html>', mover),
    ).not.toThrow()
    expect(
      traducirErrorOperador(409, '<html>Bad gateway</html>', mover).mensaje,
    ).not.toContain('html')
  })
})

describe('extraerRespuestaError', () => {
  it('extrae status y cuerpo de un error tipo axios', () => {
    expect(
      extraerRespuestaError({
        response: { status: 409, data: { error: { code: 'X' } } },
      }),
    ).toEqual({ status: 409, cuerpo: { error: { code: 'X' } } })
  })

  it('sin response (red/timeout/otros) devuelve status undefined', () => {
    expect(extraerRespuestaError(new Error('Network Error'))).toEqual({
      status: undefined,
      cuerpo: undefined,
    })
    expect(extraerRespuestaError(null)).toEqual({
      status: undefined,
      cuerpo: undefined,
    })
  })
})
