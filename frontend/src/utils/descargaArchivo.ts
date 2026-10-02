// ============================================================================
// DESCARGA DE ARCHIVOS (blob) — helpers puros/DOM sin red
//
// Usados por la exportación XLSX de Reportes (REQ-P2-REP-005/008):
//  - `nombreArchivoDescarga`: nombre de archivo SEGURO a partir del header
//    `Content-Disposition` del servidor, con fallback determinista.
//  - `guardarBlob`: Blob → <a download> temporal; el object URL SIEMPRE se
//    libera (aunque el click falle).
// ============================================================================

/** Longitud máxima del nombre de archivo aceptado del servidor. */
const NOMBRE_MAX = 120

/** Extensión obligatoria de las actas XLSX. */
const EXTENSION_XLSX = '.xlsx'

function decodificar(valor: string): string | null {
  try {
    return decodeURIComponent(valor)
  } catch {
    return null
  }
}

/** Extrae el nombre crudo de `filename*=UTF-8''…` (RFC 5987) o `filename="…"`. */
function extraerNombreCrudo(header: string): string | null {
  const extendido = /filename\*\s*=\s*([^;]+)/i.exec(header)
  if (extendido) {
    const valor = extendido[1].trim()
    // charset'lang'valor-codificado
    const partes = /^[^']*'[^']*'(.*)$/.exec(valor)
    const decodificado = decodificar(partes ? partes[1] : valor)
    if (decodificado) return decodificado
  }
  const simple = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(header)
  if (simple) return (simple[1] ?? simple[2] ?? '').trim()
  return null
}

/**
 * Sanitiza un nombre de archivo: sin rutas, sin caracteres de control ni
 * reservados, sin `..`, longitud acotada y extensión .xlsx obligatoria.
 * Devuelve `null` si no queda un nombre utilizable.
 */
export function sanearNombreArchivo(crudo: string): string | null {
  // Solo el último segmento (anula path traversal tipo ../../x o C:\x).
  const base = crudo.split(/[\\/]/).pop() ?? ''
  const limpio = base
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f\u007f<>:"|?*]/g, '')
    .replace(/\.{2,}/g, '.')
    .trim()
    .replace(/^\.+/, '')
  if (limpio === '') return null
  if (!limpio.toLowerCase().endsWith(EXTENSION_XLSX)) return null
  if (limpio.length > NOMBRE_MAX) return null
  if (limpio.length <= EXTENSION_XLSX.length) return null
  return limpio
}

/**
 * Nombre de descarga: el declarado en `Content-Disposition` (si es seguro) o
 * `fallback`. El fallback lo construye el llamador (p. ej. acta-consumo-normal-
 * 2026-10-02.xlsx) y NO depende de entrada del servidor.
 */
export function nombreArchivoDescarga(
  contentDisposition: string | null | undefined,
  fallback: string,
): string {
  if (!contentDisposition) return fallback
  const crudo = extraerNombreCrudo(contentDisposition)
  if (crudo === null) return fallback
  return sanearNombreArchivo(crudo) ?? fallback
}

/** Guarda un Blob como descarga del navegador y libera el object URL. */
export function guardarBlob(blob: Blob, nombreArchivo: string): void {
  const url = URL.createObjectURL(blob)
  try {
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = nombreArchivo
    document.body.appendChild(enlace)
    try {
      enlace.click()
    } finally {
      enlace.remove()
    }
  } finally {
    URL.revokeObjectURL(url)
  }
}
