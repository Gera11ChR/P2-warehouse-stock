import { describe, expect, it } from 'vitest'
import {
  CLAVE_IDEMPOTENCIA_MAX,
  construirPayloadMover,
  construirPayloadSumar,
  generarClaveIdempotencia,
  resolverInventario,
} from '../operadorPayload'

describe('resolverInventario', () => {
  it('mapea GENERAL y FO 1:1 y rechaza otros (incl. orígenes FO históricos)', () => {
    expect(resolverInventario('GENERAL')).toBe('GENERAL')
    expect(resolverInventario('FO')).toBe('FO')
    // RF-9: FO_PAQUETE / FO_EN_USO ya no son opciones seleccionables.
    expect(resolverInventario('FO_PAQUETE')).toBeNull()
    expect(resolverInventario('FO_EN_USO')).toBeNull()
    expect(resolverInventario('EQUIPO')).toBeNull()
  })
})

describe('construirPayloadSumar (POST /inventario/sumar-cantidad)', () => {
  it('GENERAL: sin campos de módulo (RF-1)', () => {
    const r = construirPayloadSumar({
      inventario: 'GENERAL',
      materialId: 10,
      cantidad: 5,
      claveIdempotencia: 'k-1',
    })
    expect(r).toEqual({
      ok: true,
      payload: {
        destino: 'GENERAL',
        material_id: 10,
        cantidad: 5,
        clave_idempotencia: 'k-1',
      },
    })
    if (r.ok) expect('modulo' in r.payload).toBe(false)
  })

  it('FO: destino FO sin campo `modulo` (Inventario FO único, RF-1)', () => {
    const r = construirPayloadSumar({
      inventario: 'FO',
      materialId: 3,
      cantidad: 1,
    })
    expect(r).toEqual({
      ok: true,
      payload: { destino: 'FO', material_id: 3, cantidad: 1 },
    })
    if (r.ok) expect('modulo' in r.payload).toBe(false)
  })

  it('omite la clave si no se informa y la recorta si viene con espacios', () => {
    const sin = construirPayloadSumar({
      inventario: 'GENERAL',
      materialId: 1,
      cantidad: 1,
    })
    if (sin.ok) expect('clave_idempotencia' in sin.payload).toBe(false)
    const con = construirPayloadSumar({
      inventario: 'GENERAL',
      materialId: 1,
      cantidad: 1,
      claveIdempotencia: '  abc  ',
    })
    if (con.ok) expect(con.payload.clave_idempotencia).toBe('abc')
  })

  it.each([0, -1, 1.0005, 1e-4, 1_000_000_000, Number.NaN, Infinity])(
    'rechaza cantidad %s (≤0, >3 decimales, >999999999.999 o no finita)',
    (cantidad) => {
      const r = construirPayloadSumar({
        inventario: 'GENERAL',
        materialId: 1,
        cantidad,
      })
      expect(r).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
    },
  )

  it.each([1.5, 0.1, 2.675, 0.001, 7.25, 999_999_999.999])(
    'acepta la cantidad decimal %s (hasta 3 decimales; RF-6)',
    (cantidad) => {
      expect(
        construirPayloadSumar({ inventario: 'GENERAL', materialId: 1, cantidad }),
      ).toMatchObject({ ok: true, payload: { cantidad } })
    },
  )

  it.each([0, -3, 1.2])('rechaza material_id %s', (materialId) => {
    expect(
      construirPayloadSumar({ inventario: 'GENERAL', materialId, cantidad: 1 }),
    ).toMatchObject({ ok: false, codigo: 'MATERIAL_INVALIDO' })
  })

  it('rechaza clave vacía o de más de 100 caracteres', () => {
    for (const clave of ['', '   ', 'x'.repeat(CLAVE_IDEMPOTENCIA_MAX + 1)]) {
      expect(
        construirPayloadSumar({
          inventario: 'GENERAL',
          materialId: 1,
          cantidad: 1,
          claveIdempotencia: clave,
        }),
      ).toMatchObject({ ok: false, codigo: 'CLAVE_IDEMPOTENCIA_INVALIDA' })
    }
  })

  it('rechaza un tipo de inventario desconocido', () => {
    expect(
      construirPayloadSumar({
        inventario: 'EQUIPO' as never,
        materialId: 1,
        cantidad: 1,
      }),
    ).toMatchObject({ ok: false, codigo: 'TIPO_INVENTARIO_INVALIDO' })
  })
})

describe('construirPayloadMover (POST /inventario/mover)', () => {
  it('GENERAL -> FO (sin origen_modulo/destino_modulo)', () => {
    expect(
      construirPayloadMover({
        origen: 'GENERAL',
        destino: 'FO',
        materialId: 7,
        cantidad: 20,
        claveIdempotencia: 'mover-1',
      }),
    ).toEqual({
      ok: true,
      payload: {
        origen: 'GENERAL',
        destino: 'FO',
        material_id: 7,
        cantidad: 20,
        clave_idempotencia: 'mover-1',
      },
    })
  })

  it('FO -> GENERAL con cantidad decimal', () => {
    const r = construirPayloadMover({
      origen: 'FO',
      destino: 'GENERAL',
      materialId: 7,
      cantidad: 2.5,
    })
    expect(r).toEqual({
      ok: true,
      payload: {
        origen: 'FO',
        destino: 'GENERAL',
        material_id: 7,
        cantidad: 2.5,
      },
    })
    if (r.ok) {
      expect('origen_modulo' in r.payload).toBe(false)
      expect('destino_modulo' in r.payload).toBe(false)
    }
  })

  it.each(['GENERAL', 'FO'] as const)(
    'rechaza destino = origen (%s) sin construir payload',
    (tipo) => {
      expect(
        construirPayloadMover({
          origen: tipo,
          destino: tipo,
          materialId: 1,
          cantidad: 1,
        }),
      ).toMatchObject({ ok: false, codigo: 'DESTINO_IGUAL_ORIGEN' })
    },
  )

  it('rechaza cantidad inválida, material inválido y tipos desconocidos (o históricos)', () => {
    const base = {
      origen: 'GENERAL',
      destino: 'FO',
      materialId: 1,
      cantidad: 1,
    } as const
    expect(construirPayloadMover({ ...base, cantidad: 0 })).toMatchObject({
      ok: false,
      codigo: 'CANTIDAD_INVALIDA',
    })
    expect(
      construirPayloadMover({ ...base, cantidad: 1.0005 }),
    ).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
    expect(
      construirPayloadMover({ ...base, cantidad: 1_000_000_000 }),
    ).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
    expect(construirPayloadMover({ ...base, materialId: 0 })).toMatchObject({
      ok: false,
      codigo: 'MATERIAL_INVALIDO',
    })
    expect(
      construirPayloadMover({ ...base, destino: 'X' as never }),
    ).toMatchObject({ ok: false, codigo: 'TIPO_INVENTARIO_INVALIDO' })
    expect(
      construirPayloadMover({ ...base, destino: 'FO_PAQUETE' as never }),
    ).toMatchObject({ ok: false, codigo: 'TIPO_INVENTARIO_INVALIDO' })
  })

  it('el payload no incluye campos fuera del contrato (RF-1: nunca módulo)', () => {
    const r = construirPayloadMover({
      origen: 'FO',
      destino: 'GENERAL',
      materialId: 1,
      cantidad: 1,
      claveIdempotencia: 'k',
    })
    if (!r.ok) throw new Error('debía ser válido')
    const permitidos = [
      'origen',
      'destino',
      'material_id',
      'cantidad',
      'clave_idempotencia',
    ]
    for (const clave of Object.keys(r.payload)) {
      expect(permitidos).toContain(clave)
    }
  })
})

describe('generarClaveIdempotencia', () => {
  it('es única por invocación, con prefijo y dentro del máximo del contrato', () => {
    const a = generarClaveIdempotencia('mover')
    const b = generarClaveIdempotencia('mover')
    expect(a).not.toBe(b)
    expect(a.startsWith('mover-')).toBe(true)
    expect(a.length).toBeGreaterThanOrEqual(1)
    expect(a.length).toBeLessThanOrEqual(CLAVE_IDEMPOTENCIA_MAX)
  })
})
