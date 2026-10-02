import type { SeccionTransferible } from '../types'

/** Etiqueta operativa de un inventario (sección transferible): las raíces FO
 *  usan su nombre propio; el resto, el nombre del almacén. */
export function etiquetaSeccion(
  s: Pick<SeccionTransferible, 'tipo' | 'nombre'>,
): string {
  if (s.tipo === 'FO_PAQUETE') return 'Fibra Óptica - Paquete'
  if (s.tipo === 'FO_EN_USO') return 'Fibra Óptica - En Uso'
  return s.nombre
}
