import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import { moverMaterial, sumarCantidad } from '../inventory'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

const post = vi.mocked(api.post)

beforeEach(() => vi.clearAllMocks())

describe('services/inventory — operadores rápidos', () => {
  it('sumarCantidad: POST /inventario/sumar-cantidad con el payload y devuelve el DTO', async () => {
    const out = {
      destino: 'FO',
      material_id: 7,
      stock_nuevo: 15,
      reenvio_idempotente: false,
    }
    post.mockResolvedValue({ data: out })
    const payload = {
      destino: 'FO' as const,
      material_id: 7,
      cantidad: 5,
      clave_idempotencia: 'sumar-k1',
    }
    await expect(sumarCantidad(payload)).resolves.toEqual(out)
    expect(post).toHaveBeenCalledWith('/inventario/sumar-cantidad', payload)
  })

  it('moverMaterial: POST /inventario/mover con el payload y devuelve el DTO', async () => {
    const out = {
      material_id: 7,
      origen: 'GENERAL',
      destino: 'FO',
      stock_origen: 3,
      stock_destino: 9,
      reenvio_idempotente: true,
    }
    post.mockResolvedValue({ data: out })
    const payload = {
      origen: 'GENERAL' as const,
      destino: 'FO' as const,
      material_id: 7,
      cantidad: 4,
      clave_idempotencia: 'mover-k1',
    }
    await expect(moverMaterial(payload)).resolves.toEqual(out)
    expect(post).toHaveBeenCalledWith('/inventario/mover', payload)
  })

  it.each([400, 403, 404, 409, 422])(
    'propaga el error %i sin transformarlo (se traduce en la UI)',
    async (status) => {
      const error = { response: { status, data: { error: { message: 'm' } } } }
      post.mockRejectedValue(error)
      await expect(
        sumarCantidad({ destino: 'GENERAL', material_id: 1, cantidad: 1 }),
      ).rejects.toBe(error)
      await expect(
        moverMaterial({
          origen: 'GENERAL',
          destino: 'FO',
          material_id: 1,
          cantidad: 1,
        }),
      ).rejects.toBe(error)
    },
  )
})
