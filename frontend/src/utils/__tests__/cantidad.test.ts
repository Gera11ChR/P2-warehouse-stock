import { describe, expect, it } from 'vitest'
import {
  CANTIDAD_MAX_INT4,
  mensajeCantidadInvalida,
  parseCantidadEntera,
  validarCantidad,
} from '../cantidad'
import type { MotivoCantidadInvalida } from '../cantidad'

describe('validarCantidad (REQ-P2-INV-001/003)', () => {
  it.each(['1', '5', '007', '2147483647'])('acepta el entero válido %s', (v) => {
    const r = validarCantidad(v)
    expect(r.ok).toBe(true)
  })

  it('devuelve el número entero parseado', () => {
    expect(validarCantidad('007')).toEqual({ ok: true, cantidad: 7 })
    expect(validarCantidad('2147483647')).toEqual({
      ok: true,
      cantidad: CANTIDAD_MAX_INT4,
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
    ['negativo', '-5', 'negativo'],
    ['negativo decimal', '-1.5', 'negativo'],
    ['decimal con punto', '1.5', 'decimal'],
    ['decimal con coma', '1,5', 'decimal'],
    ['decimal sin parte entera', '.5', 'decimal'],
    ['notación científica', '1e3', 'cientifica'],
    ['notación científica con signo', '2E+2', 'cientifica'],
    ['texto', 'abc', 'texto'],
    ['mezcla', '12a', 'texto'],
    ['signo más', '+5', 'texto'],
    ['signo solo', '-', 'texto'],
    ['dígitos de ancho completo', '５', 'texto'],
    ['sobre INT4', '2147483648', 'excede_int4'],
    ['muy por encima de 2^53', '99999999999999999999', 'excede_int4'],
  ])('rechaza %s (%s)', (_nombre, valor, motivo) => {
    expect(validarCantidad(valor)).toEqual({ ok: false, motivo })
  })

  it('con maxStock rechaza cantidades mayores al stock y acepta el límite', () => {
    expect(validarCantidad('12', { maxStock: 12 })).toEqual({
      ok: true,
      cantidad: 12,
    })
    expect(validarCantidad('13', { maxStock: 12 })).toEqual({
      ok: false,
      motivo: 'excede_stock',
    })
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
    'decimal',
    'cientifica',
    'texto',
    'cero',
    'excede_int4',
    'excede_stock',
  ]

  it('devuelve un mensaje en español no vacío por cada motivo', () => {
    for (const m of motivos) {
      expect(mensajeCantidadInvalida(m, { maxStock: 12 }).length).toBeGreaterThan(5)
    }
  })

  it('incluye el stock y la cota INT4', () => {
    expect(mensajeCantidadInvalida('excede_stock', { maxStock: 12 })).toBe(
      'No puedes mover más del stock disponible (12).',
    )
    expect(mensajeCantidadInvalida('excede_int4')).toContain('2,147,483,647')
  })
})

describe('parseCantidadEntera', () => {
  it('devuelve el entero o null', () => {
    expect(parseCantidadEntera('5')).toBe(5)
    expect(parseCantidadEntera('0')).toBeNull()
    expect(parseCantidadEntera('-1')).toBeNull()
    expect(parseCantidadEntera('9', { maxStock: 8 })).toBeNull()
  })
})
