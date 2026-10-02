import { beforeEach, describe, expect, it, vi } from 'vitest'
import api from '../api'
import {
  descargarActaXlsx,
  ErrorDescargaReporte,
  listarActas,
  nombreArchivoFallback,
} from '../reportes'

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}))

const get = vi.mocked(api.get)

beforeEach(() => vi.clearAllMocks())

function blobJson(cuerpo: unknown): Blob {
  return new Blob([JSON.stringify(cuerpo)], { type: 'application/json' })
}

describe('services/reportes — listarActas (formato=json)', () => {
  it('GET /reportes/entrega con filtros y formato=json; devuelve `actas`', async () => {
    get.mockResolvedValue({ data: { actas: [{ acta_id: 1 }] } })
    const actas = await listarActas('entrega', {
      equipo_id: 5,
      desde: '2026-01-01',
      hasta: '2026-02-01',
    })
    expect(actas).toEqual([{ acta_id: 1 }])
    expect(get).toHaveBeenCalledWith('/reportes/entrega', {
      params: {
        equipo_id: 5,
        desde: '2026-01-01',
        hasta: '2026-02-01',
        formato: 'json',
      },
    })
  })

  it('GET /reportes/consumo sin filtros', async () => {
    get.mockResolvedValue({ data: { actas: [] } })
    await expect(listarActas('consumo')).resolves.toEqual([])
    expect(get).toHaveBeenCalledWith('/reportes/consumo', {
      params: { formato: 'json' },
    })
  })

  it('nunca llama a la ruta legacy /reportes/despliegues ni usa format=csv', async () => {
    get.mockResolvedValue({ data: { actas: [] } })
    await listarActas('entrega')
    await listarActas('consumo')
    const llamadas = JSON.stringify(get.mock.calls)
    expect(llamadas).not.toContain('despliegue')
    expect(llamadas).not.toContain('csv')
  })

  it('propaga el error HTTP (fail-closed)', async () => {
    const error = { response: { status: 403, data: {} } }
    get.mockRejectedValue(error)
    await expect(listarActas('entrega', { equipo_id: 9 })).rejects.toBe(error)
  })
})

describe('services/reportes — descargarActaXlsx', () => {
  it('pide responseType blob con formato y filtros; usa el nombre de Content-Disposition', async () => {
    const blob = new Blob(['xlsx'])
    get.mockResolvedValue({
      data: blob,
      headers: {
        'content-disposition': 'attachment; filename="ACTA_CONSUMO_2026-10-02.xlsx"',
      },
    })
    const r = await descargarActaXlsx('consumo', 'extenso', {
      equipo_id: 2,
      acta_id: 8,
    })
    expect(get).toHaveBeenCalledWith('/reportes/consumo', {
      params: { equipo_id: 2, acta_id: 8, formato: 'extenso' },
      responseType: 'blob',
    })
    expect(r.blob).toBe(blob)
    expect(r.nombreArchivo).toBe('ACTA_CONSUMO_2026-10-02.xlsx')
  })

  it('sin Content-Disposition usa el fallback seguro', async () => {
    get.mockResolvedValue({ data: new Blob(['x']), headers: {} })
    const r = await descargarActaXlsx('entrega', 'normal')
    expect(r.nombreArchivo).toBe(nombreArchivoFallback('entrega', 'normal'))
    expect(r.nombreArchivo).toMatch(/^acta-entrega-normal-\d{4}-\d{2}-\d{2}\.xlsx$/)
  })

  it('Content-Disposition hostil → fallback', async () => {
    get.mockResolvedValue({
      data: new Blob(['x']),
      headers: { 'content-disposition': 'attachment; filename="../x.sh"' },
    })
    const r = await descargarActaXlsx('entrega', 'normal')
    expect(r.nombreArchivo).toMatch(/^acta-entrega-normal-/)
  })

  it('404: ErrorDescargaReporte con httpStatus y detalle leído del Blob JSON', async () => {
    get.mockRejectedValue({
      response: {
        status: 404,
        data: blobJson({
          error: { code: 'NOT_FOUND', message: 'No hay actas para los filtros indicados' },
        }),
      },
    })
    const error = await descargarActaXlsx('consumo', 'normal').catch((e) => e)
    expect(error).toBeInstanceOf(ErrorDescargaReporte)
    expect(error.httpStatus).toBe(404)
    expect(error.detalle).toBe('No hay actas para los filtros indicados')
  })

  it('422: detalle desde {detail:[{msg}]} de FastAPI', async () => {
    get.mockRejectedValue({
      response: {
        status: 422,
        data: blobJson({ detail: [{ msg: 'Input should be a valid date' }] }),
      },
    })
    const error = await descargarActaXlsx('entrega', 'normal', {
      desde: 'xx',
    }).catch((e) => e)
    expect(error.httpStatus).toBe(422)
    expect(error.detalle).toBe('Input should be a valid date')
  })

  it('403: conserva el status aunque el cuerpo no sea JSON', async () => {
    get.mockRejectedValue({
      response: { status: 403, data: new Blob(['<html>prohibido</html>']) },
    })
    const error = await descargarActaXlsx('entrega', 'normal').catch((e) => e)
    expect(error.httpStatus).toBe(403)
    expect(error.detalle).toBeUndefined()
  })

  it('sin respuesta (red): httpStatus indefinido', async () => {
    get.mockRejectedValue(new Error('Network Error'))
    const error = await descargarActaXlsx('entrega', 'normal').catch((e) => e)
    expect(error).toBeInstanceOf(ErrorDescargaReporte)
    expect(error.httpStatus).toBeUndefined()
    expect(error.detalle).toBeUndefined()
  })
})
