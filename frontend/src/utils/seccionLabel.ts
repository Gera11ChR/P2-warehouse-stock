/** Nombre visible único del inventario de fibra óptica (RF-1/RF-10). */
export const ETIQUETA_INVENTARIO_FO = 'Inventario FO'

/**
 * Etiqueta operativa de un inventario (sección): el Inventario FO unificado
 * y los orígenes FO HISTÓRICOS (`FO_PAQUETE`/`FO_EN_USO`, solo datos
 * heredados de movimientos antiguos; RF-9) se muestran como «Inventario FO»;
 * el resto usa el nombre del almacén. El dato persistido no se muta.
 */
export function etiquetaSeccion(s: { tipo: string; nombre: string }): string {
  if (s.tipo === 'FO' || s.tipo === 'FO_PAQUETE' || s.tipo === 'FO_EN_USO') {
    return ETIQUETA_INVENTARIO_FO
  }
  return s.nombre
}

/**
 * Etiqueta de una sección referenciada por id en el HISTORIAL de movimientos
 * (RF-9): las secciones listadas en `secciones` (GENERAL activas + Inventario
 * FO) usan `etiquetaSeccion`; un id que NO figura en ninguna lista solo puede
 * ser un origen/destino FO histórico (FO_PAQUETE/FO_EN_USO: el contrato no
 * los emite y no existe API para crear/desactivar secciones), y se muestra
 * como «Inventario FO» sin mutar el dato persistido.
 */
export function etiquetaSeccionPorId(
  id: number | null,
  secciones: { almacen_id: number; tipo: string; nombre: string }[],
): string {
  if (id === null) return '—'
  const seccion = secciones.find((s) => s.almacen_id === id)
  return seccion ? etiquetaSeccion(seccion) : ETIQUETA_INVENTARIO_FO
}
