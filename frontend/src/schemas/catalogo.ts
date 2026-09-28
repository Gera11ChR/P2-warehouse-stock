import { z } from 'zod'

// ============================================================================
// VALIDACIÓN DE FORMULARIOS — CATÁLOGO (nombre)
// (contrato real /api/v1/catalogo: categorías y unidades de medida)
//
// Validación SOLO de forma (feedback UX inmediato); el backend sigue siendo
// la autoridad del contrato.
// ============================================================================

/** Nombre de categoría o unidad de medida: 1–100 caracteres. */
export const nombreSchema = z.object({
  nombre: z.string().min(1).max(100),
})

/** Payload validado de nombre (tipo inferido del schema). */
export type NombreInput = z.infer<typeof nombreSchema>
