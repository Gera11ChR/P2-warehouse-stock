import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  guardarBlob,
  nombreArchivoDescarga,
  sanearNombreArchivo,
} from '../descargaArchivo'

const FALLBACK = 'acta-consumo-normal-2026-10-02.xlsx'

describe('nombreArchivoDescarga (Content-Disposition)', () => {
  it('toma filename="…" del header', () => {
    expect(
      nombreArchivoDescarga(
        'attachment; filename="ACTA_DE_CONSUMO_2026-10-02.xlsx"',
        FALLBACK,
      ),
    ).toBe('ACTA_DE_CONSUMO_2026-10-02.xlsx')
  })

  it('acepta filename sin comillas', () => {
    expect(
      nombreArchivoDescarga('attachment; filename=acta.xlsx', FALLBACK),
    ).toBe('acta.xlsx')
  })

  it('prefiere filename* (RFC 5987) y lo decodifica', () => {
    expect(
      nombreArchivoDescarga(
        `attachment; filename="x.xlsx"; filename*=UTF-8''Acta%20Entrega%20%C3%81.xlsx`,
        FALLBACK,
      ),
    ).toBe('Acta Entrega Á.xlsx')
  })

  it.each([
    [null],
    [undefined],
    [''],
    ['attachment'],
    ['inline; foo=bar'],
  ])('sin nombre utilizable (%s) usa el fallback', (cabecera) => {
    expect(nombreArchivoDescarga(cabecera, FALLBACK)).toBe(FALLBACK)
  })

  it('neutraliza path traversal conservando solo el último segmento', () => {
    expect(
      nombreArchivoDescarga(
        'attachment; filename="../../etc/passwd.xlsx"',
        FALLBACK,
      ),
    ).toBe('passwd.xlsx')
    expect(
      nombreArchivoDescarga(
        'attachment; filename="C:\\\\Windows\\\\acta.xlsx"',
        FALLBACK,
      ),
    ).toBe('acta.xlsx')
  })

  it('rechaza extensiones distintas de .xlsx (usa el fallback)', () => {
    expect(
      nombreArchivoDescarga('attachment; filename="acta.exe"', FALLBACK),
    ).toBe(FALLBACK)
    expect(
      nombreArchivoDescarga('attachment; filename="acta.csv"', FALLBACK),
    ).toBe(FALLBACK)
  })

  it('rechaza nombres vacíos tras sanear, solo extensión o demasiado largos', () => {
    expect(nombreArchivoDescarga('attachment; filename=".xlsx"', FALLBACK)).toBe(
      FALLBACK,
    )
    expect(
      nombreArchivoDescarga(
        `attachment; filename="${'a'.repeat(200)}.xlsx"`,
        FALLBACK,
      ),
    ).toBe(FALLBACK)
  })

  it('filename* mal codificado cae al filename simple o al fallback', () => {
    expect(
      nombreArchivoDescarga(
        `attachment; filename="ok.xlsx"; filename*=UTF-8''%E0%A4%A.xlsx`,
        FALLBACK,
      ),
    ).toBe('ok.xlsx')
  })
})

describe('sanearNombreArchivo', () => {
  it('elimina caracteres de control y reservados', () => {
    expect(sanearNombreArchivo('a<b>c:d|e?f*g.xlsx')).toBe('abcdefg.xlsx')
    expect(sanearNombreArchivo('a\u0000b\u001f.xlsx')).toBe('ab.xlsx')
  })

  it('colapsa puntos consecutivos y quita puntos iniciales', () => {
    expect(sanearNombreArchivo('...oculto..xlsx')).toBe('oculto.xlsx')
  })
})

describe('guardarBlob', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('crea el object URL, dispara la descarga con el nombre y lo revoca', () => {
    const crear = vi.fn(() => 'blob:fake-url')
    const revocar = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: crear, revokeObjectURL: revocar })
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        expect(this.download).toBe('acta.xlsx')
        expect(this.href).toContain('blob:fake-url')
      })

    const blob = new Blob(['x'])
    guardarBlob(blob, 'acta.xlsx')

    expect(crear).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalledTimes(1)
    expect(revocar).toHaveBeenCalledWith('blob:fake-url')
    expect(document.querySelector('a[download]')).toBeNull()
    vi.unstubAllGlobals()
  })

  it('revoca el object URL aunque el click falle', () => {
    const revocar = vi.fn()
    vi.stubGlobal('URL', {
      createObjectURL: () => 'blob:otro',
      revokeObjectURL: revocar,
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {
      throw new Error('click bloqueado')
    })

    expect(() => guardarBlob(new Blob(['x']), 'a.xlsx')).toThrow(
      'click bloqueado',
    )
    expect(revocar).toHaveBeenCalledWith('blob:otro')
    expect(document.querySelector('a[download]')).toBeNull()
    vi.unstubAllGlobals()
  })
})
