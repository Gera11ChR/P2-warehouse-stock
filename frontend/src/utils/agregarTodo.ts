import type { InventarioEquipoRow } from '../types'

// ============================================================================
// "AGREGAR TODO" — proyección LOCAL de la lista de seguimiento (REQ-P2-CON-003/004)
//
// Helper puro de PRESENTACIÓN: precarga en el borrador de la lista una línea
// por cada material con stock del inventario de la unidad, usando el stock
// visible en el cliente como cantidad. NO es autoridad transaccional: el
// borrador solo captura intención; la creación del seguimiento
// (fn_crear_seguimiento) y su validación de stock siguen siendo del backend.
//
// Semántica alineada con `fn_agregar_todo_seguimiento`
// (ON CONFLICT (seguimiento_id, material_id) DO NOTHING):
//  - Se agregan SOLO los materiales con stock > 0 que aún no están en la lista.
//  - Las líneas ya presentes se conservan tal cual (material y cantidad
//    editada por el operador): nunca se duplican ni se pisan.
//  - Las filas vacías (sin material elegido) no llevan intención y se
//    descartan para no bloquear el envío.
//  - Idempotente: ejecutarlo dos veces seguidas no cambia la lista.
// ============================================================================

export interface SeguimientoLinea {
  materialId: number | null
  cantidad: string
}

export interface AgregarTodoResultado {
  lineas: SeguimientoLinea[]
  /** Materiales con stock que no estaban en la lista y se agregaron. */
  agregadas: number
  /** Materiales con stock que ya estaban en la lista (se conservan). */
  yaPresentes: number
  /** Filas sin material seleccionado que se descartaron. */
  vaciasDescartadas: number
}

export function calcularAgregarTodo(
  lineas: SeguimientoLinea[],
  materiales: InventarioEquipoRow[],
): AgregarTodoResultado {
  const conStock = materiales.filter((m) => m.stock_actual > 0)
  const conMaterial = lineas.filter((l) => l.materialId !== null)
  const idsPresentes = new Set(conMaterial.map((l) => l.materialId))

  const faltantes = conStock.filter((m) => !idsPresentes.has(m.material_id))

  return {
    lineas: [
      ...conMaterial,
      ...faltantes.map((m) => ({
        materialId: m.material_id,
        cantidad: String(m.stock_actual),
      })),
    ],
    agregadas: faltantes.length,
    yaPresentes: conStock.length - faltantes.length,
    vaciasDescartadas: lineas.length - conMaterial.length,
  }
}

/** Copy del feedback (aria-live) según el resultado. */
export function mensajeAgregarTodo(resultado: AgregarTodoResultado): string {
  const { agregadas, yaPresentes } = resultado
  if (agregadas === 0) {
    return `La lista ya incluye todos los materiales con stock de la unidad (${yaPresentes}). No se agregó ninguna línea.`
  }
  const nuevas =
    agregadas === 1
      ? 'Se agregó 1 material con su stock completo'
      : `Se agregaron ${agregadas} materiales con su stock completo`
  if (yaPresentes === 0) {
    return `${nuevas}. Revisa las cantidades antes de crear el seguimiento.`
  }
  const previas =
    yaPresentes === 1
      ? '1 material ya estaba en la lista y conserva su cantidad'
      : `${yaPresentes} materiales ya estaban en la lista y conservan su cantidad`
  return `${nuevas}; ${previas}. Revisa las cantidades antes de crear el seguimiento.`
}
