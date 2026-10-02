import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import {
  agregarTodoSeguimiento,
  cerrarSeguimiento,
  crearSeguimiento,
  getSeguimiento,
  listSeguimientos,
} from '../seguimientos'
import type { Seguimiento } from '../../types'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const seguimiento: Seguimiento = {
  id: 3,
  equipo_id: 1,
  fecha: '2026-10-01',
  observaciones: null,
  usuario: 'demo-operador',
  estado: 'ABIERTA',
  created_at: '2026-10-01T10:00:00',
  updated_at: '2026-10-01T10:00:00',
  closed_at: null,
  items: [],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('services/seguimientos — contrato /equipos/{id}/seguimientos', () => {
  it('listSeguimientos: GET y extrae la clave `seguimientos`', async () => {
    get.mockResolvedValue({ data: { seguimientos: [seguimiento] } })
    await expect(listSeguimientos(1)).resolves.toEqual([seguimiento])
    expect(get).toHaveBeenCalledWith('/equipos/1/seguimientos')
  })

  it('getSeguimiento: GET del detalle', async () => {
    get.mockResolvedValue({ data: seguimiento })
    await expect(getSeguimiento(1, 3)).resolves.toEqual(seguimiento)
    expect(get).toHaveBeenCalledWith('/equipos/1/seguimientos/3')
  })

  it('crearSeguimiento: POST con el payload', async () => {
    post.mockResolvedValue({ data: seguimiento })
    const payload = {
      observaciones: 'obra',
      items: [{ material_id: 10, cantidad_tomada: 2 }],
    }
    await expect(crearSeguimiento(1, payload)).resolves.toEqual(seguimiento)
    expect(post).toHaveBeenCalledWith('/equipos/1/seguimientos', payload)
  })

  it('cerrarSeguimiento: POST .../{id}/cerrar con sobrantes', async () => {
    post.mockResolvedValue({ data: { ...seguimiento, estado: 'CERRADA' } })
    const payload = {
      sobrantes: [{ material_id: 10, cantidad_sobrante: 1 }],
      observaciones_cierre: 'ok',
    }
    await cerrarSeguimiento(1, 3, payload)
    expect(post).toHaveBeenCalledWith('/equipos/1/seguimientos/3/cerrar', payload)
  })

  it('no usa ninguna ruta legacy /despliegues', async () => {
    get.mockResolvedValue({ data: { seguimientos: [] } })
    post.mockResolvedValue({ data: seguimiento })
    await listSeguimientos(1)
    await crearSeguimiento(1, { items: [{ material_id: 1, cantidad_tomada: 1 }] })
    await cerrarSeguimiento(1, 3, { sobrantes: [] })
    await agregarTodoSeguimiento(1, 3)
    const urls = [...get.mock.calls, ...post.mock.calls].map((c) => String(c[0]))
    expect(urls.every((u) => !u.includes('despliegue'))).toBe(true)
  })

  it('propaga el error HTTP sin reinterpretarlo (fail-closed)', async () => {
    const error = { response: { status: 409, data: { error: { message: 'x' } } } }
    post.mockRejectedValue(error)
    await expect(crearSeguimiento(1, { items: [] })).rejects.toBe(error)
  })
})

describe('services/seguimientos — agregar-todo (REQ-P2-CON-003)', () => {
  const resultado = { lineas_agregadas: 4, seguimiento }

  it('sin clave: POST sin body (el body es opcional)', async () => {
    post.mockResolvedValue({ data: resultado })
    await expect(agregarTodoSeguimiento(1, 3)).resolves.toEqual(resultado)
    expect(post).toHaveBeenCalledTimes(1)
    expect(post.mock.calls[0]).toEqual([
      '/equipos/1/seguimientos/3/agregar-todo',
    ])
  })

  it('con clave: POST {clave_idempotencia}', async () => {
    post.mockResolvedValue({ data: resultado })
    await agregarTodoSeguimiento(1, 3, 'agregar-todo-abc')
    expect(post).toHaveBeenCalledWith('/equipos/1/seguimientos/3/agregar-todo', {
      clave_idempotencia: 'agregar-todo-abc',
    })
  })

  it('propaga 409 (seguimiento no ABIERTA)', async () => {
    const error = { response: { status: 409, data: {} } }
    post.mockRejectedValue(error)
    await expect(agregarTodoSeguimiento(1, 3)).rejects.toBe(error)
  })
})
