// ============================================================================
// VALIDACIÓN DE CANTIDADES ENTERAS (+Cantidad / Mover) — REQ-P2-INV-001/003/004
//
// Guardia de PRESENTACIÓN (validación preliminar de UX). La autoridad es el
// backend: 400 si cantidad <= 0 o stock insuficiente; 422 si excede INT4.
// Nada de este módulo calcula ni persiste stock.
//
// Vocabulario oficial: `cantidad_inicial`, `cantidad_transferir`,
// `cantidad_devolver`, `cantidad_integrantes`, `cantidad_diferencial`. Los
// operadores rápidos usan el campo `cantidad` del contrato
// (openspec.yaml: /inventario/sumar-cantidad y /inventario/mover).
// ============================================================================

/** Cota superior INT4 de PostgreSQL (el backend responde 422 por encima). */
export const CANTIDAD_MAX_INT4 = 2_147_483_647

export type MotivoCantidadInvalida =
  | 'vacio'
  | 'espacios'
  | 'negativo'
  | 'decimal'
  | 'cientifica'
  | 'texto'
  | 'cero'
  | 'excede_int4'
  | 'excede_stock'

export type ResultadoCantidad =
  | { ok: true; cantidad: number }
  | { ok: false; motivo: MotivoCantidadInvalida }

export interface OpcionesCantidad {
  /** Si se indica, la cantidad no puede exceder este stock (Mover). */
  maxStock?: number
}

const ENTERO = /^\d+$/
const NEGATIVO = /^-\d+([.,]\d+)?$/
const DECIMAL = /^\d*[.,]\d+$/
const CIENTIFICA = /^\d+([.,]\d+)?[eE][+-]?\d+$/

/**
 * Valida el TEXTO crudo de un campo de cantidad. Estricto: solo dígitos
 * ASCII 0-9. Rechaza vacío, espacios (incluso alrededor), signos, decimales,
 * notación científica y texto. Comparación con BigInt para no perder
 * precisión por encima de 2^53.
 */
export function validarCantidad(
  valor: string,
  opciones: OpcionesCantidad = {},
): ResultadoCantidad {
  if (valor === '') return { ok: false, motivo: 'vacio' }
  if (/\s/.test(valor)) return { ok: false, motivo: 'espacios' }
  if (!ENTERO.test(valor)) {
    if (NEGATIVO.test(valor)) return { ok: false, motivo: 'negativo' }
    if (CIENTIFICA.test(valor)) return { ok: false, motivo: 'cientifica' }
    if (DECIMAL.test(valor)) return { ok: false, motivo: 'decimal' }
    return { ok: false, motivo: 'texto' }
  }

  const n = BigInt(valor)
  if (n <= 0n) return { ok: false, motivo: 'cero' }
  if (opciones.maxStock !== undefined && n > BigInt(opciones.maxStock)) {
    return { ok: false, motivo: 'excede_stock' }
  }
  if (n > BigInt(CANTIDAD_MAX_INT4)) {
    return { ok: false, motivo: 'excede_int4' }
  }
  return { ok: true, cantidad: Number(n) }
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
    case 'decimal':
      return 'Ingresa un número entero, sin decimales.'
    case 'cientifica':
      return 'No uses notación científica; escribe el número completo.'
    case 'texto':
      return 'Ingresa solo dígitos (0-9).'
    case 'cero':
      return 'La cantidad debe ser mayor que 0.'
    case 'excede_int4':
      return `La cantidad máxima permitida es ${CANTIDAD_MAX_INT4.toLocaleString('es-MX')}.`
    case 'excede_stock':
      return `No puedes mover más del stock disponible (${(opciones.maxStock ?? 0).toLocaleString('es-MX')}).`
  }
}

/** Entero positivo válido o null. Atajo sobre `validarCantidad`. */
export function parseCantidadEntera(
  valor: string,
  opciones: OpcionesCantidad = {},
): number | null {
  const r = validarCantidad(valor, opciones)
  return r.ok ? r.cantidad : null
}
