import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import {
  crearReferencia,
  eliminarReferencia,
  listarReferencia,
  modificarReferencia,
} from '../referencia'
import type {
  ReferenciaCreatePayload,
  ReferenciaLinea,
  ReferenciaList,
} from '../../types'

// REQ-REF-005/006/008/009/015 — contrato congelado en T7
// (openapi.snapshot.json). El servicio SOLO transporta: extrae `items` del
// listado y propaga los errores TAL CUAL (fail-closed, REQ-REF-016).

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)
const patch = vi.mocked(api.patch)
const del = vi.mocked(api.delete)

const linea: ReferenciaLinea = {
  material_id: 10,
  codigo: 'CBL-001',
  descripcion: 'Cable UTP Cat 6',
  u_m: 'METRO (M)',
  cantidad_semanal: 2.5,
}

const lista: ReferenciaList = { items: [linea], total: 1 }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('services/referencia — contrato /equipos/{id}/referencia', () => {
  it('listarReferencia: GET y extrae la clave `items` (no recalcula nada)', async () => {
    get.mockResolvedValue({ data: lista })
    await expect(listarReferencia(1)).resolves.toEqual([linea])
    expect(get).toHaveBeenCalledWith('/equipos/1/referencia')
  })

  it('listarReferencia: un error se propaga sin reinterpretarse como lista vacía', async () => {
    const error = { response: { status: 403, data: { detail: 'prohibido' } } }
    get.mockRejectedValue(error)
    await expect(listarReferencia(1)).rejects.toBe(error)
  })

  it('crearReferencia: POST con el payload completo (líneas 1..50)', async () => {
    post.mockResolvedValue({ data: lista })
    const payload: ReferenciaCreatePayload = {
      lineas: [{ material_id: 10, cantidad_semanal: 2.5 }],
    }
    await expect(crearReferencia(1, payload)).resolves.toEqual(lista)
    expect(post).toHaveBeenCalledWith('/equipos/1/referencia', payload)
  })

  it('crearReferencia: propaga el rechazo HTTP tal cual', async () => {
    const error = {
      response: {
        status: 409,
        data: {
          error: {
            code: 'REFERENCIA_DUPLICADA',
            message: 'ya existe',
            coordinates: { linea: 0, material_id: 10 },
          },
        },
      },
    }
    post.mockRejectedValue(error)
    await expect(
      crearReferencia(1, { lineas: [{ material_id: 10, cantidad_semanal: 1 }] }),
    ).rejects.toBe(error)
  })

  it('modificarReferencia: PATCH .../referencia/{materialId} con SOLO la cantidad', async () => {
    patch.mockResolvedValue({ data: { ...linea, cantidad_semanal: 7 } })
    await expect(
      modificarReferencia(1, 10, { cantidad_semanal: 7 }),
    ).resolves.toEqual({ ...linea, cantidad_semanal: 7 })
    expect(patch).toHaveBeenCalledWith('/equipos/1/referencia/10', {
      cantidad_semanal: 7,
    })
  })

  it('eliminarReferencia: DELETE .../referencia/{materialId} sin cuerpo', async () => {
    del.mockResolvedValue({ data: '' })
    await expect(eliminarReferencia(1, 10)).resolves.toBeUndefined()
    expect(del).toHaveBeenCalledWith('/equipos/1/referencia/10')
  })

  it('ninguna ruta usa un segmento ajeno al contrato congelado', async () => {
    get.mockResolvedValue({ data: lista })
    post.mockResolvedValue({ data: lista })
    patch.mockResolvedValue({ data: linea })
    del.mockResolvedValue({ data: '' })
    await listarReferencia(1)
    await crearReferencia(1, { lineas: [{ material_id: 10, cantidad_semanal: 1 }] })
    await modificarReferencia(1, 10, { cantidad_semanal: 2 })
    await eliminarReferencia(1, 10)
    const urls = [...get.mock.calls, ...post.mock.calls, ...patch.mock.calls, ...del.mock.calls].map(
      (c) => String(c[0]),
    )
    for (const url of urls) {
      expect(url).toMatch(/^\/equipos\/1\/referencia(\/10)?$/)
    }
  })
})
