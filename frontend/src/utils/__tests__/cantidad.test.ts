import { describe, expect, it } from 'vitest'
import {
  CANTIDAD_MAX_DECIMAL,
  esCantidadDecimalValida,
  formatearCantidad,
  mensajeCantidadInvalida,
  validarCantidad,
} from '../cantidad'
import type { MotivoCantidadInvalida } from '../cantidad'

describe('validarCantidad — cantidades decimales (RF-6)', () => {
  it.each(['1', '5', '007', '0.1', '2.5', '2.675', '0.001', '7.250', '999999999.999'])(
    'acepta la cantidad válida %s',
    (v) => {
      expect(validarCantidad(v).ok).toBe(true)
    },
  )

  it('devuelve el número parseado sin artefactos de coma flotante', () => {
    expect(validarCantidad('007')).toEqual({ ok: true, cantidad: 7 })
    expect(validarCantidad('0.1')).toEqual({ ok: true, cantidad: 0.1 })
    expect(validarCantidad('2.675')).toEqual({ ok: true, cantidad: 2.675 })
    expect(validarCantidad('7.250')).toEqual({ ok: true, cantidad: 7.25 })
    expect(validarCantidad('999999999.999')).toEqual({
      ok: true,
      cantidad: CANTIDAD_MAX_DECIMAL,
    })
  })

  it.each<[string, string, MotivoCantidadInvalida]>([
    ['vacío', '', 'vacio'],
    ['solo espacios', '   ', 'espacios'],
    ['espacio al final', '5 ', 'espacios'],
    ['espacio al inicio', ' 5', 'espacios'],
    ['espacio intermedio', '1 000', 'espacios'],
    ['cero', '0', 'cero'],
    ['ceros', '000', 'cero'],
    ['cero decimal', '0.000', 'cero'],
    ['negativo', '-5', 'negativo'],
    ['negativo decimal', '-1.5', 'negativo'],
    ['coma decimal', '1,5', 'coma'],
    ['sobre-precisión (4 decimales)', '1.0005', 'exceso_decimales'],
    ['sobre-precisión larga', '0.1234567', 'exceso_decimales'],
    ['notación científica', '1e3', 'cientifica'],
    ['notación científica negativa (E5)', '1e-4', 'cientifica'],
    ['notación científica con signo', '2E+2', 'cientifica'],
    ['texto', 'abc', 'texto'],
    ['mezcla', '12a', 'texto'],
    ['signo más', '+5', 'texto'],
    ['signo solo', '-', 'texto'],
    ['punto sin parte entera', '.5', 'texto'],
    ['punto final sin decimales', '5.', 'texto'],
    ['dígitos de ancho completo', '５', 'texto'],
    ['10 enteros (desborda 12 dígitos)', '1000000000', 'excede_maximo'],
    ['muy por encima de 2^53', '99999999999999999999', 'excede_maximo'],
  ])('rechaza %s (%s)', (_nombre, valor, motivo) => {
    expect(validarCantidad(valor)).toEqual({ ok: false, motivo })
  })

  it('permitirCero acepta 0 (ajustes y Valor Unitario) pero no negativos', () => {
    expect(validarCantidad('0', { permitirCero: true })).toEqual({
      ok: true,
      cantidad: 0,
    })
    expect(validarCantidad('0.000', { permitirCero: true }).ok).toBe(true)
    expect(validarCantidad('-0.5', { permitirCero: true })).toEqual({
      ok: false,
      motivo: 'negativo',
    })
  })

  it('con maxStock rechaza cantidades mayores al stock y acepta el límite (decimales exactos)', () => {
    expect(validarCantidad('12', { maxStock: 12 })).toEqual({
      ok: true,
      cantidad: 12,
    })
    expect(validarCantidad('12.001', { maxStock: 12 })).toEqual({
      ok: false,
      motivo: 'excede_stock',
    })
    expect(validarCantidad('7.25', { maxStock: 7.25 }).ok).toBe(true)
    expect(validarCantidad('7.251', { maxStock: 7.25 })).toEqual({
      ok: false,
      motivo: 'excede_stock',
    })
    // 0.1 + 0.2 en coma flotante es 0.30000000000000004: no debe romper el límite.
    expect(validarCantidad('0.3', { maxStock: 0.1 + 0.2 }).ok).toBe(true)
  })

  it('maxStock = 0: cualquier cantidad positiva excede el stock', () => {
    expect(validarCantidad('1', { maxStock: 0 })).toEqual({
      ok: false,
      motivo: 'excede_stock',
    })
  })
})

describe('mensajeCantidadInvalida', () => {
  const motivos: MotivoCantidadInvalida[] = [
    'vacio',
    'espacios',
    'negativo',
    'coma',
    'cientifica',
    'texto',
    'cero',
    'exceso_decimales',
    'excede_maximo',
    'excede_stock',
  ]

  it('devuelve un mensaje en español no vacío por cada motivo', () => {
    for (const m of motivos) {
      expect(mensajeCantidadInvalida(m, { maxStock: 12 }).length).toBeGreaterThan(5)
    }
  })

  it('incluye el stock, el máximo y la regla de decimales', () => {
    expect(mensajeCantidadInvalida('excede_stock', { maxStock: 12 })).toBe(
      'No puedes mover más del stock disponible (12).',
    )
    expect(mensajeCantidadInvalida('excede_stock', { maxStock: 7.25 })).toContain(
      '7.25',
    )
    expect(mensajeCantidadInvalida('excede_maximo')).toContain('999,999,999.999')
    expect(mensajeCantidadInvalida('exceso_decimales')).toContain('3 decimales')
  })
})

describe('esCantidadDecimalValida (guardia de payload)', () => {
  it.each([0.001, 0.1, 2.5, 2.675, 7.25, 999_999_999.999])('acepta %s', (n) => {
    expect(esCantidadDecimalValida(n)).toBe(true)
  })

  it.each([0, -1, 1.0005, 1e-4, 1_000_000_000, Number.NaN, Infinity])(
    'rechaza %s',
    (n) => {
      expect(esCantidadDecimalValida(n)).toBe(false)
    },
  )

  it('permitirCero acepta 0 pero no negativos', () => {
    expect(esCantidadDecimalValida(0, { permitirCero: true })).toBe(true)
    expect(esCantidadDecimalValida(-0.5, { permitirCero: true })).toBe(false)
  })
})

describe('formatearCantidad', () => {
  it('es-MX con hasta 3 decimales y sin ceros de relleno', () => {
    expect(formatearCantidad(7.25)).toBe('7.25')
    expect(formatearCantidad(12)).toBe('12')
    expect(formatearCantidad(1234.5)).toBe('1,234.5')
    expect(formatearCantidad(0.1 + 0.2)).toBe('0.3')
  })
})
