/** Nombre visible único del inventario de fibra óptica. */
export const ETIQUETA_INVENTARIO_FO = 'Inventario FO'

/**
 * Etiqueta operativa de un inventario (sección): la sección `FO` se muestra
 * como «Inventario FO»; el resto usa el nombre del almacén.
 */
export function etiquetaSeccion(s: { tipo: string; nombre: string }): string {
  return s.tipo === 'FO' ? ETIQUETA_INVENTARIO_FO : s.nombre
}

/**
 * Etiqueta de una sección referenciada por id (historial de movimientos y
 * auditoría). Un id que no figura en la lista recibida se muestra como
 * «Sección #<id>» (nunca se presume «Inventario FO»).
 */
export function etiquetaSeccionPorId(
  id: number | null,
  secciones: { almacen_id: number; tipo: string; nombre: string }[],
): string {
  if (id === null) return '—'
  const seccion = secciones.find((s) => s.almacen_id === id)
  return seccion ? etiquetaSeccion(seccion) : `Sección #${id}`
}
