// ============================================================================
// VALIDACIÓN DE CANTIDADES DECIMALES (+Cantidad / Mover / ajustes / Valor
// Unitario) — RF-2, RF-6
//
// Guardia de PRESENTACIÓN (validación preliminar de UX). La autoridad es el
// backend: 400/422 por escala > 3 decimales, negativos, cantidad <= 0 o
// desbordamiento (más de 12 dígitos: 9 enteros + 3 decimales). Nada de este
// módulo calcula ni persiste stock.
//
// Formato aceptado (texto crudo): `^\d{1,9}(\.\d{1,3})?$` — punto decimal
// (locale es-MX), sin separadores de miles, sin signo, sin notación
// científica. Nunca se redondea en silencio: una cantidad con más de 3
// decimales se rechaza (el valor `1e-4`, p. ej., es sobre-precisión).
//
// Vocabulario oficial: `cantidad_inicial`, `cantidad_transferir`,
// `cantidad_devolver`, `cantidad_integrantes`, `cantidad_diferencial`. Los
// operadores rápidos usan el campo `cantidad` del contrato.
// ============================================================================

/** Dígitos enteros máximos de una cantidad decimal (NUMERIC(12,3)). */
export const CANTIDAD_MAX_ENTEROS = 9
/** Decimales máximos de una cantidad decimal. */
export const CANTIDAD_MAX_DECIMALES = 3
/** Máximo valor representable: 999 999 999.999 (12 dígitos en total). */
export const CANTIDAD_MAX_DECIMAL = 999_999_999.999

export type MotivoCantidadInvalida =
  | 'vacio'
  | 'espacios'
  | 'negativo'
  | 'coma'
  | 'cientifica'
  | 'texto'
  | 'cero'
  | 'exceso_decimales'
  | 'excede_maximo'
  | 'excede_stock'

export type ResultadoCantidad =
  | { ok: true; cantidad: number }
  | { ok: false; motivo: MotivoCantidadInvalida }

export interface OpcionesCantidad {
  /** Si se indica, la cantidad no puede exceder este stock (Mover). */
  maxStock?: number
  /** Permite `0` (ajustes de stock, Valor Unitario). Por omisión la
   *  cantidad de un movimiento debe ser mayor que 0. */
  permitirCero?: boolean
}

const DECIMAL_VALIDO = /^(\d+)(?:\.(\d+))?$/
const NEGATIVO = /^-\d+([.,]\d+)?$/
const CIENTIFICA = /^\d+([.,]\d+)?[eE][+-]?\d+$/
const COMA_DECIMAL = /^\d+,\d+$/

/** Escala una cantidad numérica a milésimas enteras (BigInt) para
 *  COMPARAR sin error de coma flotante (solo guardias de presentación). */
function aMilesimas(valor: number): bigint {
  return BigInt(valor.toFixed(CANTIDAD_MAX_DECIMALES).replace('.', ''))
}

/**
 * Valida el TEXTO crudo de un campo de cantidad decimal. Estricto: solo
 * dígitos ASCII y un punto decimal. Rechaza vacío, espacios (incluso
 * alrededor), signos, coma decimal, notación científica, texto, exceso de
 * decimales (>3) y desbordamiento (>9 enteros). La comparación usa BigInt
 * sobre milésimas, sin aritmética de coma flotante.
 */
export function validarCantidad(
  valor: string,
  opciones: OpcionesCantidad = {},
): ResultadoCantidad {
  if (valor === '') return { ok: false, motivo: 'vacio' }
  if (/\s/.test(valor)) return { ok: false, motivo: 'espacios' }

  const coincidencia = DECIMAL_VALIDO.exec(valor)
  if (coincidencia === null) {
    if (NEGATIVO.test(valor)) return { ok: false, motivo: 'negativo' }
    if (CIENTIFICA.test(valor)) return { ok: false, motivo: 'cientifica' }
    if (COMA_DECIMAL.test(valor)) return { ok: false, motivo: 'coma' }
    return { ok: false, motivo: 'texto' }
  }

  const [, enteros, decimales = ''] = coincidencia
  if (decimales.length > CANTIDAD_MAX_DECIMALES) {
    return { ok: false, motivo: 'exceso_decimales' }
  }
  const enterosSinCeros = enteros.replace(/^0+(?=\d)/, '')
  if (enterosSinCeros.length > CANTIDAD_MAX_ENTEROS) {
    return { ok: false, motivo: 'excede_maximo' }
  }

  const milesimas = BigInt(
    `${enterosSinCeros}${decimales.padEnd(CANTIDAD_MAX_DECIMALES, '0')}`,
  )
  if (milesimas <= 0n && opciones.permitirCero !== true) {
    return { ok: false, motivo: 'cero' }
  }
  if (
    opciones.maxStock !== undefined &&
    milesimas > aMilesimas(opciones.maxStock)
  ) {
    return { ok: false, motivo: 'excede_stock' }
  }
  // Para ≤ 12 dígitos significativos Number() es exacto (≤ 15 garantizados).
  return { ok: true, cantidad: Number(valor) }
}

/** Formatea para mensajes: es-MX, hasta 3 decimales, sin ceros de relleno. */
export function formatearCantidad(valor: number): string {
  return valor.toLocaleString('es-MX', {
    minimumFractionDigits: 0,
    maximumFractionDigits: CANTIDAD_MAX_DECIMALES,
  })
}

/** Mensaje en español (en línea, junto al campo) para cada motivo. */
export function mensajeCantidadInvalida(
  motivo: MotivoCantidadInvalida,
  opciones: OpcionesCantidad = {},
): string {
  switch (motivo) {
    case 'vacio':
      return 'Ingresa la cantidad.'
    case 'espacios':
      return 'La cantidad no debe contener espacios.'
    case 'negativo':
      return 'La cantidad no puede ser negativa.'
    case 'coma':
      return 'Usa punto como separador decimal (por ejemplo 2.5).'
    case 'cientifica':
      return 'No uses notación científica; escribe el número completo.'
    case 'texto':
      return 'Ingresa solo dígitos y, si aplica, un punto decimal (por ejemplo 0.5).'
    case 'cero':
      return 'La cantidad debe ser mayor que 0.'
    case 'exceso_decimales':
      return `Máximo ${CANTIDAD_MAX_DECIMALES} decimales; no se redondea automáticamente.`
    case 'excede_maximo':
      return `La cantidad máxima permitida es ${formatearCantidad(CANTIDAD_MAX_DECIMAL)}.`
    case 'excede_stock':
      return `No puedes mover más del stock disponible (${formatearCantidad(opciones.maxStock ?? 0)}).`
  }
}

/** ¿El número cumple la escala/rango de cantidad (≤3 decimales, ≤12
 *  dígitos, finito)? Guardia de payload; no redondea. */
export function esCantidadDecimalValida(
  valor: number,
  { permitirCero = false }: { permitirCero?: boolean } = {},
): boolean {
  if (!Number.isFinite(valor)) return false
  if (valor < 0 || (valor === 0 && !permitirCero)) return false
  if (valor > CANTIDAD_MAX_DECIMAL) return false
  return Number(valor.toFixed(CANTIDAD_MAX_DECIMALES)) === valor
}
