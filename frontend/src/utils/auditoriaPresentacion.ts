// ============================================================================
// PRESENTACIÓN DE EVENTOS DE AUDITORÍA HISTÓRICOS (RF-7, RF-10)
//
// El ledger es INMUTABLE: los eventos previos a la unificación conservan
// `modulo`/`origen_modulo`/`destino_modulo` = 'PAQUETE' | 'EN_USO' en su
// `detalles`. El dato NO se muta: solo al MOSTRARLO esos valores se rotulan
// con la nomenclatura oficial «Inventario FO» (copia profunda; el original
// queda intacto).
// ============================================================================

const CLAVES_MODULO = new Set(['modulo', 'origen_modulo', 'destino_modulo'])
const VALORES_MODULO_HISTORICO = new Set(['PAQUETE', 'EN_USO'])
const ETIQUETA = 'Inventario FO'

function presentar(valor: unknown, clave?: string): unknown {
  if (Array.isArray(valor)) return valor.map((v) => presentar(v))
  if (typeof valor === 'object' && valor !== null) {
    return Object.fromEntries(
      Object.entries(valor).map(([k, v]) => [k, presentar(v, k)]),
    )
  }
  if (
    clave !== undefined &&
    CLAVES_MODULO.has(clave) &&
    typeof valor === 'string' &&
    VALORES_MODULO_HISTORICO.has(valor)
  ) {
    return ETIQUETA
  }
  return valor
}

/** Copia de `detalles` apta para mostrar: los módulos FO históricos se
 *  rotulan «Inventario FO». No muta el argumento. */
export function presentarDetallesAuditoria(
  detalles: Record<string, unknown>,
): Record<string, unknown> {
  return presentar(detalles) as Record<string, unknown>
}
