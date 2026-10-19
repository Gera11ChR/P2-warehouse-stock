import { z } from 'zod'

// ============================================================================
// VALIDACIÓN DE FORMULARIOS — ACTIVIDADES DE LA UNIDAD (Etapa 1)
// (contrato real /api/v1/equipos/{equipo_id}/actividades, congelado T7)
//
// Validación SOLO de forma (feedback UX inmediato). La autoridad del
// contrato sigue siendo el backend (Pydantic + fn_crear_actividad): estos
// esquemas replican las reglas, NUNCA las reemplazan.
// ============================================================================

/** Celda de "Actividades realizadas": texto de 1..500 tras recortar
 *  espacios; el formulario descarta las vacías antes de enviar. */
const actividadCeldaSchema = z
  .string()
  .trim()
  .min(1, 'Cada actividad debe tener contenido')
  .max(500, 'Máximo 500 caracteres por actividad')

/**
 * Payload de confirmación:
 * - Vehículo/Cliente(s)/Dirección(es) obligatorios, sin blancos y con los
 *   límites del contrato (100/500/500);
 * - `actividades`: 1..30 celdas;
 * - `comentarios` opcional (≤2000): el formulario envía `null` cuando queda
 *   vacío (observación T7).
 */
export const actividadSchema = z.object({
  seguimiento_id: z.number().int().positive(),
  vehiculo: z.string().trim().min(1, 'El vehículo es obligatorio').max(100),
  clientes: z
    .string()
    .trim()
    .min(1, 'El cliente es obligatorio')
    .max(500),
  direcciones: z
    .string()
    .trim()
    .min(1, 'La dirección es obligatoria')
    .max(500),
  actividades: z.array(actividadCeldaSchema).min(1).max(30),
  comentarios: z.string().max(2000).nullable().optional(),
})

/** Payload validado de confirmación (tipo inferido del schema). */
export type ActividadInput = z.infer<typeof actividadSchema>
