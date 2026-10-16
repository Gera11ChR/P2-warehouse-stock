import { z } from 'zod'
import {
  CANTIDAD_MAX_DECIMAL,
  CANTIDAD_MAX_DECIMALES,
} from '../utils/cantidad'

// ============================================================================
// ESQUEMAS ZOD DE CANTIDADES DECIMALES (RF-6) — validación PRELIMINAR.
//
// Una cantidad decimal es un número con hasta 3 decimales y hasta 12 dígitos
// (máximo 999 999 999.999). Sin redondeo silencioso. La autoridad es el
// backend (422/400) y PostgreSQL (escala NUMERIC(12,3)).
// ============================================================================

function tieneEscalaValida(valor: number): boolean {
  return Number(valor.toFixed(CANTIDAD_MAX_DECIMALES)) === valor
}

const baseDecimal = z
  .number()
  .finite()
  .max(CANTIDAD_MAX_DECIMAL)
  .refine(tieneEscalaValida, {
    message: `Máximo ${CANTIDAD_MAX_DECIMALES} decimales.`,
  })

/** Cantidad de movimiento / tomada: decimal estrictamente mayor que 0. */
export const cantidadMovimientoSchema = baseDecimal.positive()

/** Existencia / cantidad consumida: decimal mayor o igual a 0. */
export const cantidadNoNegativaSchema = baseDecimal.min(0)
