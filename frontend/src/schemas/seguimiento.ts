import { z } from 'zod'

// ============================================================================
// VALIDACIÓN DE FORMULARIOS — SEGUIMIENTOS DE EQUIPO (CONSUMO)
// (contrato real /api/v1/equipos/{equipo_id}/seguimientos)
//
// Validación SOLO de forma (feedback UX inmediato). La autoridad del
// contrato sigue siendo el backend (Pydantic): estos esquemas replican
// las reglas de negocio, NUNCA las reemplazan.
// ============================================================================

/** Línea del payload de apertura (POST seguimientos). */
const seguimientoItemSchema = z.object({
  material_id: z.number().int().positive(),
  cantidad_tomada: z.number().int().positive(),
})

/**
 * Payload de apertura de seguimiento:
 * - `observaciones` opcional, máx. 2000 caracteres;
 * - `items` con al menos una línea;
 * - `material_id` SIN duplicados (el backend lo exige).
 */
export const seguimientoCreateSchema = z
  .object({
    observaciones: z.string().max(2000).optional(),
    items: z.array(seguimientoItemSchema).min(1),
  })
  .superRefine((valor, ctx) => {
    const ids = valor.items.map((i) => i.material_id)
    const duplicados = ids.filter((id, idx) => ids.indexOf(id) !== idx)
    if (duplicados.length > 0) {
      ctx.addIssue({
        code: 'custom',
        message: `material_id duplicado: ${[...new Set(duplicados)].join(', ')}`,
        path: ['items'],
      })
    }
  })

/** Payload validado de apertura (tipo inferido del schema). */
export type SeguimientoCreateInput = z.infer<typeof seguimientoCreateSchema>

/** Línea de consumo del payload de cierre (cantidad_consumida >= 0). */
const consumoItemSchema = z.object({
  material_id: z.number().int().positive(),
  cantidad_consumida: z.number().int().min(0),
})

/**
 * Payload de cierre de seguimiento:
 * - `consumidos`: UNA línea por cada material del seguimiento (obligatorio,
 *   al menos una; el backend rechaza con 422 las líneas faltantes);
 * - `observaciones_cierre` opcional;
 * - `material_id` SIN duplicados.
 */
export const cerrarSeguimientoSchema = z
  .object({
    consumidos: z.array(consumoItemSchema).min(1),
    observaciones_cierre: z.string().optional(),
  })
  .superRefine((valor, ctx) => {
    const ids = valor.consumidos.map((i) => i.material_id)
    const duplicados = ids.filter((id, idx) => ids.indexOf(id) !== idx)
    if (duplicados.length > 0) {
      ctx.addIssue({
        code: 'custom',
        message: `material_id duplicado en consumidos: ${[...new Set(duplicados)].join(', ')}`,
        path: ['consumidos'],
      })
    }
  })

/** Payload validado de cierre (tipo inferido del schema). */
export type CerrarSeguimientoInput = z.infer<typeof cerrarSeguimientoSchema>
