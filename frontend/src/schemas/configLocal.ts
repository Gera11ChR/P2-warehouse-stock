import { z } from 'zod'

// ============================================================================
// VALIDACIÓN DE FORMULARIOS — CONFIGURACIÓN LOCAL DE EQUIPO
// (contrato real PATCH /api/v1/equipos/{equipo_id}/inventario/{material_id})
//
// Validación SOLO de forma (feedback UX inmediato); el backend sigue siendo
// la autoridad del contrato (422 si el payload llega vacío).
// ============================================================================

/**
 * Payload de configuración local:
 * - `stock_minimo_local` entero >= 0 (opcional);
 * - `categoria_local_id` / `um_local_id` enteros > 0 (opcionales);
 * - AL MENOS UNO de los tres campos requerido.
 */
export const configLocalSchema = z
  .object({
    stock_minimo_local: z.number().int().min(0).optional(),
    categoria_local_id: z.number().int().positive().optional(),
    um_local_id: z.number().int().positive().optional(),
  })
  .superRefine((valor, ctx) => {
    if (
      valor.stock_minimo_local === undefined &&
      valor.categoria_local_id === undefined &&
      valor.um_local_id === undefined
    ) {
      ctx.addIssue({
        code: 'custom',
        message: 'Indique al menos un campo: stock mínimo local, categoría o U.M.',
      })
    }
  })

/** Payload validado de configuración local (tipo inferido del schema). */
export type ConfigLocalInput = z.infer<typeof configLocalSchema>
