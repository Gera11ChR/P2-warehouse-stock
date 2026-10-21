import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import {
  descargarReporteActividadesXlsx,
  ErrorDescargaReporte,
  listarReporteActividades,
  nombreArchivoFallbackActividades,
} from '../reportes'
import type { Actividad } from '../../types'

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}))

const get = vi.mocked(api.get)

beforeEach(() => vi.clearAllMocks())

function blobJson(cuerpo: unknown): Blob {
  return new Blob([JSON.stringify(cuerpo)], { type: 'application/json' })
}

const actividad: Actividad = {
  actividad_id: 7,
  folio: 'R0007',
  folio_num: 7,
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
  materiales: [],
}

describe('services/reportes — listarReporteActividades (formato=json)', () => {
  it('GET /reportes/actividades con los filtros del contrato y formato=json; devuelve `items`', async () => {
    get.mockResolvedValue({ data: { items: [actividad], total: 1 } })
    const items = await listarReporteActividades({
      equipo_id: 5,
      desde: '2026-10-01',
      hasta: '2026-10-19',
      actividad_id: 7,
    })
    expect(items).toEqual([actividad])
    expect(get).toHaveBeenCalledWith('/reportes/actividades', {
      params: {
        equipo_id: 5,
        desde: '2026-10-01',
        hasta: '2026-10-19',
        actividad_id: 7,
        formato: 'json',
      },
    })
  })

  it('GET /reportes/actividades sin filtros', async () => {
    get.mockResolvedValue({ data: { items: [], total: 0 } })
    await expect(listarReporteActividades()).resolves.toEqual([])
    expect(get).toHaveBeenCalledWith('/reportes/actividades', {
      params: { formato: 'json' },
    })
  })

  it('usa exactamente los parámetros del contrato congelado (snake_case, sin campos inventados)', async () => {
    get.mockResolvedValue({ data: { items: [], total: 0 } })
    await listarReporteActividades({
      equipo_id: 1,
      desde: '2026-01-01',
      hasta: '2026-01-31',
      actividad_id: 2,
    })
    const llamada = JSON.stringify(get.mock.calls[0])
    expect(llamada).toContain('equipo_id')
    expect(llamada).toContain('desde')
    expect(llamada).toContain('hasta')
    expect(llamada).toContain('actividad_id')
    expect(llamada).toContain('formato')
    expect(llamada).not.toContain('acta_id')
    expect(llamada).not.toContain('equipoId')
  })

  it('propaga el error HTTP (fail-closed)', async () => {
    const error = { response: { status: 403, data: {} } }
    get.mockRejectedValue(error)
    await expect(
      listarReporteActividades({ equipo_id: 9 }),
    ).rejects.toBe(error)
  })
})

describe('services/reportes — descargarReporteActividadesXlsx', () => {
  it('pide responseType blob con formato=xlsx y filtros; usa el nombre de Content-Disposition', async () => {
    const blob = new Blob(['xlsx'])
    get.mockResolvedValue({
      data: blob,
      headers: {
        'content-disposition':
          'attachment; filename="reporte-actividades-R0007.xlsx"',
      },
    })
    const r = await descargarReporteActividadesXlsx({
      equipo_id: 4,
      actividad_id: 7,
    })
    expect(get).toHaveBeenCalledWith('/reportes/actividades', {
      params: { equipo_id: 4, actividad_id: 7, formato: 'xlsx' },
      responseType: 'blob',
    })
    expect(r.blob).toBe(blob)
    expect(r.nombreArchivo).toBe('reporte-actividades-R0007.xlsx')
  })

  it('sin Content-Disposition usa el fallback determinista', async () => {
    get.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    const r = await descargarReporteActividadesXlsx()
    expect(r.nombreArchivo).toBe(nombreArchivoFallbackActividades())
    expect(r.nombreArchivo).toMatch(
      /^reporte-actividades-\d{4}-\d{2}-\d{2}\.xlsx$/,
    )
  })

  it('Content-Disposition hostil → fallback', async () => {
    get.mockResolvedValue({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="../x.sh"' },
    })
    const r = await descargarReporteActividadesXlsx()
    expect(r.nombreArchivo).toMatch(/^reporte-actividades-/)
  })

  it('404: ErrorDescargaReporte con httpStatus y detalle leído del Blob JSON', async () => {
    get.mockRejectedValue({
      response: {
        status: 404,
        data: blobJson({
          error: {
            code: 'SIN_RESULTADOS',
            message: 'Sin actividades para los filtros indicados',
          },
        }),
      },
    })
    const error = await descargarReporteActividadesXlsx().catch((e) => e)
    expect(error).toBeInstanceOf(ErrorDescargaReporte)
    expect(error.httpStatus).toBe(404)
    expect(error.detalle).toBe('Sin actividades para los filtros indicados')
  })

  it('422: detalle desde {detail:[{msg}]} de FastAPI', async () => {
    get.mockRejectedValue({
      response: {
        status: 422,
        data: blobJson({ detail: [{ msg: 'Input should be a valid date' }] }),
      },
    })
    const error = await descargarReporteActividadesXlsx({
      desde: 'xx',
    }).catch((e) => e)
    expect(error.httpStatus).toBe(422)
    expect(error.detalle).toBe('Input should be a valid date')
  })

  it('422 por tope: propaga `code` de negocio (LIMITE_FILAS_EXCEDIDO) junto al detalle real', async () => {
    const mensaje =
      'El libro excede el límite de 10000 filas inyectadas (materiales + actividades); acote los filtros e intente de nuevo'
    get.mockRejectedValue({
      response: {
        status: 422,
        data: blobJson({
          error: { code: 'LIMITE_FILAS_EXCEDIDO', message: mensaje },
        }),
      },
    })
    const error = await descargarReporteActividadesXlsx().catch((e) => e)
    expect(error).toBeInstanceOf(ErrorDescargaReporte)
    expect(error.httpStatus).toBe(422)
    expect(error.code).toBe('LIMITE_FILAS_EXCEDIDO')
    expect(error.detalle).toBe(mensaje)
  })

  it('sin `code` en el cuerpo (p. ej. {detail:[…]}) el código queda indefinido', async () => {
    get.mockRejectedValue({
      response: {
        status: 422,
        data: blobJson({ detail: [{ msg: 'Input should be a valid date' }] }),
      },
    })
    const error = await descargarReporteActividadesXlsx().catch((e) => e)
    expect(error.code).toBeUndefined()
  })

  it('403: conserva el status aunque el cuerpo no sea JSON', async () => {
    get.mockRejectedValue({
      response: { status: 403, data: new Blob(['<html>prohibido</html>']) },
    })
    const error = await descargarReporteActividadesXlsx().catch((e) => e)
    expect(error.httpStatus).toBe(403)
    expect(error.detalle).toBeUndefined()
  })

  it('sin respuesta (red): httpStatus indefinido', async () => {
    get.mockRejectedValue(new Error('Network Error'))
    const error = await descargarReporteActividadesXlsx().catch((e) => e)
    expect(error).toBeInstanceOf(ErrorDescargaReporte)
    expect(error.httpStatus).toBeUndefined()
    expect(error.detalle).toBeUndefined()
  })
})
