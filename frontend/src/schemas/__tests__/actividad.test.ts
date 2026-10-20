import { describe, expect, it } from 'vitest'
import { actividadSchema } from '../actividad'

// ============================================================================
// SCHEMA ZOD — ACTIVIDADES DE LA UNIDAD (Etapa 1, T10)
//
// Validación SOLO de forma: estos casos replican los límites del contrato
// congelado (T7) para RF-5/RF-6/RF-7. La autoridad sigue siendo el backend
// (Pydantic + fn_crear_actividad); aquí se fija lo que el formulario acepta.
// ============================================================================

const VALIDO = {
  seguimiento_id: 9,
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido de fibra'],
  comentarios: null,
}

describe('schemas/actividad — límites del contrato congelado (RF-5/RF-6/RF-7)', () => {
  it('acepta el payload mínimo válido', () => {
    const resultado = actividadSchema.safeParse(VALIDO)
    expect(resultado.success).toBe(true)
  })

  it('comentarios: null, ausente y texto ≤2000 son válidos', () => {
    expect(actividadSchema.safeParse(VALIDO).success).toBe(true)
    const sinComentarios: Partial<typeof VALIDO> = { ...VALIDO }
    delete sinComentarios.comentarios
    expect(actividadSchema.safeParse(sinComentarios).success).toBe(true)
    expect(
      actividadSchema.safeParse({ ...VALIDO, comentarios: 'x'.repeat(2000) })
        .success,
    ).toBe(true)
  })

  it('comentarios: más de 2000 caracteres se rechaza', () => {
    const resultado = actividadSchema.safeParse({
      ...VALIDO,
      comentarios: 'x'.repeat(2001),
    })
    expect(resultado.success).toBe(false)
  })

  it('seguimiento_id: entero positivo (0, negativo y decimal se rechazan)', () => {
    for (const invalido of [0, -1, 1.5, '9']) {
      expect(
        actividadSchema.safeParse({ ...VALIDO, seguimiento_id: invalido }).success,
      ).toBe(false)
    }
  })

  it('vehículo: obligatorio, recortado y máximo 100 caracteres', () => {
    expect(
      actividadSchema.safeParse({ ...VALIDO, vehiculo: '   ' }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, vehiculo: 'x'.repeat(101) }).success,
    ).toBe(false)
    const resultado = actividadSchema.safeParse({
      ...VALIDO,
      vehiculo: '  Camioneta 12  ',
    })
    expect(resultado.success).toBe(true)
    if (resultado.success) expect(resultado.data.vehiculo).toBe('Camioneta 12')
  })

  it('clientes: obligatorio, recortado y máximo 500 caracteres', () => {
    expect(
      actividadSchema.safeParse({ ...VALIDO, clientes: '  ' }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, clientes: 'x'.repeat(501) }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, clientes: 'x'.repeat(500) }).success,
    ).toBe(true)
  })

  it('direcciones: obligatorio, recortado y máximo 500 caracteres', () => {
    expect(
      actividadSchema.safeParse({ ...VALIDO, direcciones: '' }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, direcciones: 'x'.repeat(501) })
        .success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, direcciones: 'x'.repeat(500) })
        .success,
    ).toBe(true)
  })

  it('actividades: vacío o más de 30 celdas se rechaza; 30 celdas es válido', () => {
    expect(actividadSchema.safeParse({ ...VALIDO, actividades: [] }).success).toBe(
      false,
    )
    expect(
      actividadSchema.safeParse({
        ...VALIDO,
        actividades: Array.from({ length: 31 }, (_, i) => `A${i}`),
      }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({
        ...VALIDO,
        actividades: Array.from({ length: 30 }, (_, i) => `A${i}`),
      }).success,
    ).toBe(true)
  })

  it('celda: vacía tras recortar o de más de 500 caracteres se rechaza', () => {
    expect(
      actividadSchema.safeParse({ ...VALIDO, actividades: ['   '] }).success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, actividades: ['x'.repeat(501)] })
        .success,
    ).toBe(false)
    expect(
      actividadSchema.safeParse({ ...VALIDO, actividades: ['x'.repeat(500)] })
        .success,
    ).toBe(true)
  })

  it('recorta cada celda de actividades al validar', () => {
    const resultado = actividadSchema.safeParse({
      ...VALIDO,
      actividades: ['  Tendido  '],
    })
    expect(resultado.success).toBe(true)
    if (resultado.success) {
      expect(resultado.data.actividades).toEqual(['Tendido'])
    }
  })

  it('zod descarta campos desconocidos (el 422 por extras lo decide el backend)', () => {
    const resultado = actividadSchema.safeParse({ ...VALIDO, folio: 'R0001' })
    expect(resultado.success).toBe(true)
    if (resultado.success) {
      expect('folio' in resultado.data).toBe(false)
    }
  })
})
