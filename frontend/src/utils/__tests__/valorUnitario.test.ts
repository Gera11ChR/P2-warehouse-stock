import { describe, expect, it } from 'vitest'
import { validarValorUnitario, VALOR_UNITARIO_REGEX } from '../../schemas/valorUnitario'
import {
  cantidadMovimientoSchema,
  cantidadNoNegativaSchema,
} from '../../schemas/cantidadDecimal'
import { formatMxn, formatMxnConMoneda } from '../formatMxn'

// RF-2 / RF-3: validación PRELIMINAR del Valor Unitario (el backend decide) y
// formato es-MX con mínimo 2 y máximo 3 decimales.

describe('validarValorUnitario (RF-2)', () => {
  it.each([
    ['1', 1],
    ['0', 0], // E2: valor 0 permitido
    ['12.345', 12.345],
    ['2.5', 2.5],
    ['0.001', 0.001],
    ['999999999.999', 999_999_999.999],
  ])('acepta %s', (texto, valor) => {
    expect(validarValorUnitario(texto)).toEqual({ ok: true, valor })
  })

  it.each([
    ['', /ingresa/i],
    ['-1', /negativa/i],
    ['1.2345', /3 decimales/i], // E3: sin redondeo silencioso
    ['1e-4', /científica/i], // E5
    ['1000000000', /máxima/i], // E4: desbordamiento
    ['1,5', /punto/i],
    ['abc', /dígitos/i],
    [' 1', /espacios/i],
  ])('rechaza «%s» con un mensaje que explica el motivo', (texto, mensaje) => {
    const r = validarValorUnitario(texto)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.mensaje).toMatch(mensaje)
  })

  it('la regex preliminar es ^\\d{1,9}(\\.\\d{1,3})?$', () => {
    expect(VALOR_UNITARIO_REGEX.source).toBe('^\\d{1,9}(\\.\\d{1,3})?$')
  })
})

describe('esquemas zod de cantidad decimal (RF-6)', () => {
  it('cantidad de movimiento: decimal > 0 con ≤ 3 decimales', () => {
    expect(cantidadMovimientoSchema.safeParse(2.5).success).toBe(true)
    expect(cantidadMovimientoSchema.safeParse(0.001).success).toBe(true)
    expect(cantidadMovimientoSchema.safeParse(0).success).toBe(false)
    expect(cantidadMovimientoSchema.safeParse(-1).success).toBe(false)
    expect(cantidadMovimientoSchema.safeParse(1.0005).success).toBe(false)
    expect(cantidadMovimientoSchema.safeParse(1_000_000_000).success).toBe(false)
    expect(cantidadMovimientoSchema.safeParse(Number.NaN).success).toBe(false)
    expect(cantidadMovimientoSchema.safeParse(Infinity).success).toBe(false)
  })

  it('cantidad no negativa: acepta 0 y rechaza negativos / sobre-precisión', () => {
    expect(cantidadNoNegativaSchema.safeParse(0).success).toBe(true)
    expect(cantidadNoNegativaSchema.safeParse(7.25).success).toBe(true)
    expect(cantidadNoNegativaSchema.safeParse(-0.5).success).toBe(false)
    expect(cantidadNoNegativaSchema.safeParse(0.1234).success).toBe(false)
  })
})

describe('formatMxn (RF-3, RF-5; C-7)', () => {
  it.each([
    [1, '1.00'],
    [2.5, '2.50'],
    [12.345, '12.345'],
    [0, '0.00'],
    [1234.5, '1,234.50'],
    [22.5, '22.50'],
  ])('formatea %s como %s', (valor, esperado) => {
    expect(formatMxn(valor)).toBe(esperado)
  })

  it('formatMxnConMoneda coloca la etiqueta MXN a la derecha', () => {
    expect(formatMxnConMoneda(1)).toBe('1.00 MXN')
  })
})
