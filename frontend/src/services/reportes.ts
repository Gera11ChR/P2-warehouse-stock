import api from './api'
import { nombreArchivoDescarga } from '../utils/descargaArchivo'
import type { ReporteTipo } from '../utils/reporteExport'
import type {
  Acta,
  ActaList,
  Actividad,
  ActividadList,
  FormatoXlsx,
  ReporteActividadesParams,
  ReporteParams,
} from '../types'

// ============================================================================
// REPORTES — contrato certificado (openspec.yaml)
//   GET /api/v1/reportes/entrega   (Acta de Entrega: TEAMS confirmado)
//   GET /api/v1/reportes/consumo   (Acta de Consumo: cierre de seguimiento)
// Query: equipo_id, desde, hasta, acta_id, formato = json | normal | extenso.
//   - formato=json (default)  → {actas: ActaOut[]}
//   - formato=normal|extenso  → XLSX (Content-Disposition: attachment)
// Errores: 403 (equipo ajeno), 404 (XLSX sin actas), 422 (formato/filtros
// inválidos). La ruta legacy /reportes/despliegues y el CSV NO existen.
//
// El frontend NO agrega ni recalcula las actas: son snapshots de PostgreSQL.
// ============================================================================

/** Media type de las actas XLSX. */
export const MEDIA_TYPE_XLSX =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** GET /reportes/{tipo}?formato=json — actas para la tabla de la UI. */
export async function listarActas(
  tipo: ReporteTipo,
  params: ReporteParams = {},
): Promise<Acta[]> {
  const { data } = await api.get<ActaList>(`/reportes/${tipo}`, {
    params: { ...params, formato: 'json' },
  })
  return data.actas
}

/** Error de una descarga XLSX con el contexto que consume `exportStatus`. */
export class ErrorDescargaReporte extends Error {
  readonly httpStatus: number | undefined
  readonly detalle: string | undefined

  constructor(httpStatus?: number, detalle?: string) {
    super(detalle ?? `Error al descargar el reporte (HTTP ${httpStatus ?? 'sin respuesta'})`)
    this.name = 'ErrorDescargaReporte'
    this.httpStatus = httpStatus
    this.detalle = detalle
  }
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null
}

/** `{error:{message}}` o `{detail:[{msg}]}` → texto de detalle (o undefined). */
function detalleDeCuerpo(cuerpo: unknown): string | undefined {
  if (!esObjeto(cuerpo)) return undefined
  if (esObjeto(cuerpo.error) && typeof cuerpo.error.message === 'string') {
    return cuerpo.error.message || undefined
  }
  if (Array.isArray(cuerpo.detail)) {
    const textos = cuerpo.detail
      .map((d) => (esObjeto(d) && typeof d.msg === 'string' ? d.msg : ''))
      .filter(Boolean)
    return textos.length > 0 ? textos.join(' ') : undefined
  }
  return undefined
}

/**
 * Con `responseType: 'blob'`, axios entrega el cuerpo de un error JSON como
 * Blob: se lee como texto y se interpreta; cualquier fallo de lectura/parseo
 * se ignora (queda solo el status HTTP).
 */
async function detalleDeRespuestaError(data: unknown): Promise<string | undefined> {
  try {
    if (typeof Blob !== 'undefined' && data instanceof Blob) {
      return detalleDeCuerpo(JSON.parse(await data.text()))
    }
    if (typeof data === 'string') return detalleDeCuerpo(JSON.parse(data))
    return detalleDeCuerpo(data)
  } catch {
    return undefined
  }
}

export interface ArchivoDescargado {
  blob: Blob
  nombreArchivo: string
}

/** Nombre determinista (no proviene del servidor) si falta/invalida Content-Disposition. */
export function nombreArchivoFallback(
  tipo: ReporteTipo,
  formato: FormatoXlsx,
  hoy: Date = new Date(),
): string {
  return `acta-${tipo}-${formato}-${hoy.toISOString().slice(0, 10)}.xlsx`
}

/**
 * GET /reportes/{tipo}?formato=normal|extenso — descarga del XLSX como Blob.
 * El nombre sale de `Content-Disposition` (saneado) con fallback seguro.
 * Un error HTTP se normaliza a `ErrorDescargaReporte` (httpStatus + detalle).
 */
export async function descargarActaXlsx(
  tipo: ReporteTipo,
  formato: FormatoXlsx,
  params: ReporteParams = {},
): Promise<ArchivoDescargado> {
  try {
    const response = await api.get<Blob>(`/reportes/${tipo}`, {
      params: { ...params, formato },
      responseType: 'blob',
    })
    const cabecera: unknown = response.headers?.['content-disposition']
    const blob =
      response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: MEDIA_TYPE_XLSX })
    return {
      blob,
      nombreArchivo: nombreArchivoDescarga(
        typeof cabecera === 'string' ? cabecera : null,
        nombreArchivoFallback(tipo, formato),
      ),
    }
  } catch (error) {
    const respuesta =
      esObjeto(error) && esObjeto(error.response) ? error.response : null
    const httpStatus =
      respuesta && typeof respuesta.status === 'number'
        ? respuesta.status
        : undefined
    const detalle = respuesta
      ? await detalleDeRespuestaError(respuesta.data)
      : undefined
    throw new ErrorDescargaReporte(httpStatus, detalle)
  }
}

// ============================================================================
// REPORTE DE ACTIVIDADES — contrato congelado (openapi.snapshot.json T7)
//   GET /api/v1/reportes/actividades
// Query: equipo_id, desde, hasta, actividad_id, formato = json | xlsx.
//   - formato=json (default) → ActividadListOut {items, total}: 200 con el
//     listado más reciente primero (REQ-REP-002).
//   - formato=xlsx → libro de una hoja por folio con tope de 100 folios
//     (REQ-REP-009); 404 sin actividades para los filtros.
// Errores (REQ-REP-010/011): 400 NUMERIC_OUT_OF_RANGE, 403 Unidad ajena al
// actor, 404 sin resultados, 422 (RANGO_FECHAS_INVALIDO, LIMITE_HOJAS_EXCEDIDO,
// LIMITE_FILAS_EXCEDIDO o parámetros inválidos/no declarados). El OpenAPI solo
// declara `application/json`; la descarga XLSX se pide con
// `responseType: 'blob'` y el media type de la plantilla (plan §5.1, nota H-1).
//
// El frontend NO agrega, ordena ni recalcula los datos del reporte: renderiza
// y descarga exactamente lo que entrega el backend (REQ-REP-005/013).
// ============================================================================

/** GET /reportes/actividades?formato=json — folios para la tabla de la UI. */
export async function listarReporteActividades(
  params: ReporteActividadesParams = {},
): Promise<Actividad[]> {
  const { data } = await api.get<ActividadList>('/reportes/actividades', {
    params: { ...params, formato: 'json' },
  })
  return data.items
}

/** Nombre determinista (no proviene del servidor) si falta o es inválido el
 *  Content-Disposition de la descarga del reporte de actividades. */
export function nombreArchivoFallbackActividades(
  hoy: Date = new Date(),
): string {
  return `reporte-actividades-${hoy.toISOString().slice(0, 10)}.xlsx`
}

/**
 * GET /reportes/actividades?formato=xlsx — descarga del libro (una hoja por
 * folio) como Blob. El nombre sale de `Content-Disposition` (saneado) con
 * fallback seguro. Un error HTTP se normaliza a `ErrorDescargaReporte`
 * (httpStatus + detalle).
 */
export async function descargarReporteActividadesXlsx(
  params: ReporteActividadesParams = {},
): Promise<ArchivoDescargado> {
  try {
    const response = await api.get<Blob>('/reportes/actividades', {
      params: { ...params, formato: 'xlsx' },
      responseType: 'blob',
    })
    const cabecera: unknown = response.headers?.['content-disposition']
    const blob =
      response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: MEDIA_TYPE_XLSX })
    return {
      blob,
      nombreArchivo: nombreArchivoDescarga(
        typeof cabecera === 'string' ? cabecera : null,
        nombreArchivoFallbackActividades(),
      ),
    }
  } catch (error) {
    const respuesta =
      esObjeto(error) && esObjeto(error.response) ? error.response : null
    const httpStatus =
      respuesta && typeof respuesta.status === 'number'
        ? respuesta.status
        : undefined
    const detalle = respuesta
      ? await detalleDeRespuestaError(respuesta.data)
      : undefined
    throw new ErrorDescargaReporte(httpStatus, detalle)
  }
}
