import { describe, expect, it } from 'vitest'
import {
  CLAVE_IDEMPOTENCIA_MAX,
  construirPayloadMover,
  construirPayloadSumar,
  generarClaveIdempotencia,
  resolverInventario,
} from '../operadorPayload'

describe('resolverInventario', () => {
  it('mapea los tres tipos y rechaza otros', () => {
    expect(resolverInventario('GENERAL')).toEqual({ inventario: 'GENERAL' })
    expect(resolverInventario('FO_PAQUETE')).toEqual({
      inventario: 'FO',
      modulo: 'PAQUETE',
    })
    expect(resolverInventario('FO_EN_USO')).toEqual({
      inventario: 'FO',
      modulo: 'EN_USO',
    })
    expect(resolverInventario('EQUIPO')).toBeNull()
  })
})

describe('construirPayloadSumar (POST /inventario/sumar-cantidad)', () => {
  it('GENERAL: sin `modulo`', () => {
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

  it.each([
    ['FO_PAQUETE', 'PAQUETE'],
    ['FO_EN_USO', 'EN_USO'],
  ] as const)('%s: destino FO + modulo %s', (tipo, modulo) => {
    const r = construirPayloadSumar({
      inventario: tipo,
      materialId: 3,
      cantidad: 1,
    })
    expect(r).toEqual({
      ok: true,
      payload: { destino: 'FO', modulo, material_id: 3, cantidad: 1 },
    })
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

  it.each([0, -1, 1.5, 2_147_483_648, Number.NaN])(
    'rechaza cantidad %s',
    (cantidad) => {
      const r = construirPayloadSumar({
        inventario: 'GENERAL',
        materialId: 1,
        cantidad,
      })
      expect(r).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
    },
  )

  it('acepta el límite INT4', () => {
    expect(
      construirPayloadSumar({
        inventario: 'GENERAL',
        materialId: 1,
        cantidad: 2_147_483_647,
      }).ok,
    ).toBe(true)
  })

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
  it('GENERAL -> FO Paquete', () => {
    expect(
      construirPayloadMover({
        origen: 'GENERAL',
        destino: 'FO_PAQUETE',
        materialId: 7,
        cantidad: 20,
        claveIdempotencia: 'mover-1',
      }),
    ).toEqual({
      ok: true,
      payload: {
        origen: 'GENERAL',
        destino: 'FO',
        destino_modulo: 'PAQUETE',
        material_id: 7,
        cantidad: 20,
        clave_idempotencia: 'mover-1',
      },
    })
  })

  it('GENERAL -> FO En Uso', () => {
    const r = construirPayloadMover({
      origen: 'GENERAL',
      destino: 'FO_EN_USO',
      materialId: 7,
      cantidad: 2,
    })
    expect(r).toEqual({
      ok: true,
      payload: {
        origen: 'GENERAL',
        destino: 'FO',
        destino_modulo: 'EN_USO',
        material_id: 7,
        cantidad: 2,
      },
    })
  })

  it('FO En Uso -> GENERAL (origen_modulo, sin destino_modulo)', () => {
    const r = construirPayloadMover({
      origen: 'FO_EN_USO',
      destino: 'GENERAL',
      materialId: 7,
      cantidad: 3,
    })
    expect(r).toEqual({
      ok: true,
      payload: {
        origen: 'FO',
        origen_modulo: 'EN_USO',
        destino: 'GENERAL',
        material_id: 7,
        cantidad: 3,
      },
    })
    if (r.ok) expect('destino_modulo' in r.payload).toBe(false)
  })

  it('FO Paquete -> FO En Uso y viceversa (ambos módulos)', () => {
    expect(
      construirPayloadMover({
        origen: 'FO_PAQUETE',
        destino: 'FO_EN_USO',
        materialId: 1,
        cantidad: 4,
      }),
    ).toEqual({
      ok: true,
      payload: {
        origen: 'FO',
        origen_modulo: 'PAQUETE',
        destino: 'FO',
        destino_modulo: 'EN_USO',
        material_id: 1,
        cantidad: 4,
      },
    })
    const inverso = construirPayloadMover({
      origen: 'FO_EN_USO',
      destino: 'FO_PAQUETE',
      materialId: 1,
      cantidad: 4,
    })
    expect(inverso).toMatchObject({
      ok: true,
      payload: { origen_modulo: 'EN_USO', destino_modulo: 'PAQUETE' },
    })
  })

  it.each(['GENERAL', 'FO_PAQUETE', 'FO_EN_USO'] as const)(
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

  it('rechaza cantidad fuera de 1..INT4, material inválido y tipos desconocidos', () => {
    const base = {
      origen: 'GENERAL',
      destino: 'FO_PAQUETE',
      materialId: 1,
      cantidad: 1,
    } as const
    expect(construirPayloadMover({ ...base, cantidad: 0 })).toMatchObject({
      ok: false,
      codigo: 'CANTIDAD_INVALIDA',
    })
    expect(
      construirPayloadMover({ ...base, cantidad: 2_147_483_648 }),
    ).toMatchObject({ ok: false, codigo: 'CANTIDAD_INVALIDA' })
    expect(construirPayloadMover({ ...base, materialId: 0 })).toMatchObject({
      ok: false,
      codigo: 'MATERIAL_INVALIDO',
    })
    expect(
      construirPayloadMover({ ...base, destino: 'X' as never }),
    ).toMatchObject({ ok: false, codigo: 'TIPO_INVENTARIO_INVALIDO' })
  })

  it('el payload no incluye campos fuera del contrato', () => {
    const r = construirPayloadMover({
      origen: 'FO_PAQUETE',
      destino: 'GENERAL',
      materialId: 1,
      cantidad: 1,
      claveIdempotencia: 'k',
    })
    if (!r.ok) throw new Error('debía ser válido')
    const permitidos = [
      'origen',
      'origen_modulo',
      'destino',
      'destino_modulo',
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
