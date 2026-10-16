import { z } from 'zod'
import { mensajeCantidadInvalida, validarCantidad } from '../utils/cantidad'

// ============================================================================
// VALIDACIÓN PRELIMINAR DEL VALOR UNITARIO (RF-2, RF-3)
//
// Valor Unitario en MXN: decimal ≥ 0, hasta 3 decimales y hasta 9 enteros
// (NUMERIC(12,3); máximo 999 999 999.999). Validación SOLO de forma (feedback
// UX inmediato): la autoridad es el backend (422 por escala/rango/negativo,
// 403 si el actor no es administrador) y PostgreSQL (CHECK >= 0).
// ============================================================================

/** Formato del texto crudo del campo: `^\d{1,9}(\.\d{1,3})?$`. */
export const VALOR_UNITARIO_REGEX = /^\d{1,9}(\.\d{1,3})?$/

export const valorUnitarioTextoSchema = z
  .string()
  .regex(VALOR_UNITARIO_REGEX, 'Valor Unitario inválido.')

export type ResultadoValorUnitario =
  | { ok: true; valor: number }
  | { ok: false; mensaje: string }

/** Valida el texto del campo y devuelve el número a enviar (o el mensaje en
 *  español que explica el rechazo). `0` es válido (E2). No redondea nunca. */
export function validarValorUnitario(texto: string): ResultadoValorUnitario {
  const parsed = valorUnitarioTextoSchema.safeParse(texto)
  if (parsed.success) return { ok: true, valor: Number(parsed.data) }
  const detalle = validarCantidad(texto, { permitirCero: true })
  return {
    ok: false,
    mensaje: detalle.ok
      ? 'Valor Unitario inválido.'
      : mensajeCantidadInvalida(detalle.motivo),
  }
}
