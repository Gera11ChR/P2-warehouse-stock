import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import {
  crearActividad,
  listarActividades,
  obtenerActividadPendiente,
} from '../actividades'
import type { Actividad, ActividadPendiente } from '../../types'

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const actividad: Actividad = {
  actividad_id: 1,
  folio: 'R0001',
  folio_num: 1,
  seguimiento_id: 9,
  equipo_id: 4,
  equipo_nombre: 'Unidad Norte',
  fecha: '2026-10-19T10:00:00Z',
  usuario: 'demo-operador',
  vehiculo: 'Camioneta 12',
  clientes: 'Cliente A',
  direcciones: 'Calle 1',
  actividades: ['Tendido de fibra'],
  comentarios: null,
  materiales: [
    {
      material_id: 3,
      codigo: null,
      descripcion: 'Cable FO',
      u_m: 'MTS',
      cantidad_consumida: 4,
      valor_unitario: 7.5,
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('services/actividades — contrato /equipos/{id}/actividades', () => {
  it('obtenerActividadPendiente: GET /pendiente y devuelve el cuerpo', async () => {
    const pendiente: ActividadPendiente = {
      seguimiento: {
        seguimiento_id: 9,
        fecha_cierre: '2026-10-19T09:00:00Z',
        materiales: actividad.materiales,
      },
    }
    get.mockResolvedValue({ data: pendiente })
    await expect(obtenerActividadPendiente(4)).resolves.toEqual(pendiente)
    expect(get).toHaveBeenCalledWith('/equipos/4/actividades/pendiente')
  })

  it('crearActividad: POST con el payload y devuelve la actividad (201)', async () => {
    const payload = {
      seguimiento_id: 9,
      vehiculo: 'Camioneta 12',
      clientes: 'Cliente A',
      direcciones: 'Calle 1',
      actividades: ['Tendido de fibra'],
      comentarios: null,
    }
    post.mockResolvedValue({ data: actividad })
    await expect(crearActividad(4, payload)).resolves.toEqual(actividad)
    expect(post).toHaveBeenCalledWith('/equipos/4/actividades', payload)
  })

  it('listarActividades: GET del historial y extrae el cuerpo', async () => {
    get.mockResolvedValue({ data: { items: [actividad], total: 1 } })
    await expect(listarActividades(4)).resolves.toEqual({
      items: [actividad],
      total: 1,
    })
    expect(get).toHaveBeenCalledWith('/equipos/4/actividades')
  })
})
