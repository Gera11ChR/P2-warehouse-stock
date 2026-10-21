import type {
  OpcionOrigenFo,
  OpcionOrigenGeneral,
} from '../hooks/useReferencia'

// ============================================================================
// ORIGEN DEL SELECTOR DE LA REFERENCIA (REQ-REF-013, T9)
//
// Utilidades puras compartidas por MaterialSelect y el formulario de alta.
// El origen («Inventario General» / «Inventario FO») es solo una ayuda de
// selección de la interfaz: NO forma parte del contrato (Q3, RN-4).
// ============================================================================

export type OpcionMaterial = OpcionOrigenGeneral | OpcionOrigenFo

export type OrigenReferencia = 'general' | 'fo'

/** Etiquetas oficiales (nomenclatura «Inventario FO», `.agents.md` §3). */
export const ORIGEN_ETIQUETA: Record<OrigenReferencia, string> = {
  general: 'Inventario General',
  fo: 'Inventario FO',
}

/** Clave única de una opción (el mismo material en dos secciones difiere). */
export function claveOpcion(opcion: OpcionMaterial): string {
  return opcion.origen === 'general'
    ? `general:${opcion.almacen_id}:${opcion.material_id}`
    : `fo:${opcion.material_id}`
}
