import { z } from 'zod'

// ============================================================================
// VALIDACIÓN DE FORMULARIOS — DESPLIEGUES DE EQUIPO
// (contrato real /api/v1/equipos/{equipo_id}/despliegues)
//
// Validación SOLO de forma (feedback UX inmediato). La autoridad del
// contrato sigue siendo el backend (Pydantic): estos esquemas replican
// las reglas de negocio, NUNCA las reemplazan.
// ============================================================================

/** Línea del payload de apertura (POST despliegues). */
const despliegueItemSchema = z.object({
  material_id: z.number().int().positive(),
  cantidad_tomada: z.number().int().positive(),
})

/**
 * Payload de apertura de despliegue:
 * - `observaciones` opcional, máx. 2000 caracteres;
 * - `items` con al menos una línea;
 * - `material_id` SIN duplicados (el backend lo exige).
 */
export const despliegueCreateSchema = z
  .object({
    observaciones: z.string().max(2000).optional(),
    items: z.array(despliegueItemSchema).min(1),
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
export type DespliegueCreateInput = z.infer<typeof despliegueCreateSchema>

/** Línea de sobrantes del payload de cierre (cantidad_sobrante >= 0). */
const sobranteItemSchema = z.object({
  material_id: z.number().int().positive(),
  cantidad_sobrante: z.number().int().min(0),
})

/**
 * Payload de cierre de despliegue:
 * - `sobrantes` (solo los materiales devueltos; los omitidos se consideran
 *   consumidos al 100 % — resolución backend);
 * - `observaciones_cierre` opcional;
 * - `material_id` SIN duplicados.
 */
export const cerrarDespliegueSchema = z
  .object({
    sobrantes: z.array(sobranteItemSchema),
    observaciones_cierre: z.string().optional(),
  })
  .superRefine((valor, ctx) => {
    const ids = valor.sobrantes.map((i) => i.material_id)
    const duplicados = ids.filter((id, idx) => ids.indexOf(id) !== idx)
    if (duplicados.length > 0) {
      ctx.addIssue({
        code: 'custom',
        message: `material_id duplicado en sobrantes: ${[...new Set(duplicados)].join(', ')}`,
        path: ['sobrantes'],
      })
    }
  })

/** Payload validado de cierre (tipo inferido del schema). */
export type CerrarDespliegueInput = z.infer<typeof cerrarDespliegueSchema>
