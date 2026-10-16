import type { SeccionTransferible } from '../types'
import { CANTIDAD_MAX_DECIMAL, esCantidadDecimalValida, formatearCantidad } from './cantidad'

// ============================================================================
// BUILDER PURO DE PAYLOADS — +Cantidad / Mover (REQ-P2-INV-001/003/004/007)
//
// Traduce las SELECCIONES de la interfaz a la INTENCIÓN que entiende el
// contrato certificado (openspec/openspec.yaml):
//   POST /api/v1/inventario/sumar-cantidad  -> SumarCantidadPayload
//   POST /api/v1/inventario/mover           -> MoverMaterialPayload
//
// Sin red, sin estado, sin aritmética de stock. Las guardas son preliminares
// (cortan errores obvios antes de enviar); la decisión final es de FastAPI y
// PostgreSQL. `cantidad` = campo oficial del contrato.
//
// Mapeo de tipo de inventario (`SeccionTransferible['tipo']`) -> contrato
// (1:1, RF-1): el Inventario FO es único, sin módulos. Enviar `modulo`,
// `origen_modulo` o `destino_modulo` es 422.
//   GENERAL -> destino/origen = 'GENERAL'
//   FO      -> destino/origen = 'FO'
//
// `cantidad`: decimal > 0 con hasta 3 decimales y 12 dígitos (RF-6).
// ============================================================================

/** Tipo de inventario tal como lo publica /inventario/secciones/transferibles. */
export type TipoInventario = SeccionTransferible['tipo']
export type InventarioContrato = 'GENERAL' | 'FO'

/** Cuerpo de POST /api/v1/inventario/sumar-cantidad. */
export interface SumarCantidadPayload {
  destino: InventarioContrato
  material_id: number
  cantidad: number
  clave_idempotencia?: string
}

/** Cuerpo de POST /api/v1/inventario/mover. */
export interface MoverMaterialPayload {
  origen: InventarioContrato
  destino: InventarioContrato
  material_id: number
  cantidad: number
  clave_idempotencia?: string
}

export type CodigoPayloadInvalido =
  | 'TIPO_INVENTARIO_INVALIDO'
  | 'MATERIAL_INVALIDO'
  | 'CANTIDAD_INVALIDA'
  | 'DESTINO_IGUAL_ORIGEN'
  | 'CLAVE_IDEMPOTENCIA_INVALIDA'

export type ResultadoPayload<T> =
  | { ok: true; payload: T }
  | { ok: false; codigo: CodigoPayloadInvalido; mensaje: string }

/** Longitud máxima de `clave_idempotencia` en el contrato (min 1, max 100). */
export const CLAVE_IDEMPOTENCIA_MAX = 100

/** GENERAL -> 'GENERAL'; FO -> 'FO'; otro (incl. orígenes FO históricos,
 *  que ya no se ofrecen) -> null. */
export function resolverInventario(tipo: string): InventarioContrato | null {
  return tipo === 'GENERAL' || tipo === 'FO' ? tipo : null
}

function fallo<T>(
  codigo: CodigoPayloadInvalido,
  mensaje: string,
): ResultadoPayload<T> {
  return { ok: false, codigo, mensaje }
}

/** Guardas comunes. Devuelve un fallo o la clave normalizada (o undefined). */
function validarComunes(
  materialId: number,
  cantidad: number,
  clave: string | undefined,
):
  | { ok: true; clave: string | undefined }
  | { ok: false; codigo: CodigoPayloadInvalido; mensaje: string } {
  if (!Number.isSafeInteger(materialId) || materialId <= 0) {
    return {
      ok: false,
      codigo: 'MATERIAL_INVALIDO',
      mensaje: 'No se pudo identificar el material de la operación.',
    }
  }
  if (!esCantidadDecimalValida(cantidad)) {
    return {
      ok: false,
      codigo: 'CANTIDAD_INVALIDA',
      mensaje: `La cantidad debe ser mayor que 0, con máximo 3 decimales y no exceder ${formatearCantidad(CANTIDAD_MAX_DECIMAL)}.`,
    }
  }
  if (clave === undefined) return { ok: true, clave: undefined }
  const limpia = clave.trim()
  if (limpia.length < 1 || limpia.length > CLAVE_IDEMPOTENCIA_MAX) {
    return {
      ok: false,
      codigo: 'CLAVE_IDEMPOTENCIA_INVALIDA',
      mensaje: `La clave de operación debe tener entre 1 y ${CLAVE_IDEMPOTENCIA_MAX} caracteres.`,
    }
  }
  return { ok: true, clave: limpia }
}

export interface EntradaSumar {
  /** Inventario que recibe la suma (donde está el material). */
  inventario: TipoInventario
  materialId: number
  cantidad: number
  /** Generada por apertura del diálogo; se reutiliza en reintentos. */
  claveIdempotencia?: string
}

export function construirPayloadSumar(
  entrada: EntradaSumar,
): ResultadoPayload<SumarCantidadPayload> {
  const destino = resolverInventario(entrada.inventario)
  if (destino === null) {
    return fallo(
      'TIPO_INVENTARIO_INVALIDO',
      'El inventario seleccionado no admite esta operación.',
    )
  }
  const comunes = validarComunes(
    entrada.materialId,
    entrada.cantidad,
    entrada.claveIdempotencia,
  )
  if (!comunes.ok) return fallo(comunes.codigo, comunes.mensaje)

  const payload: SumarCantidadPayload = {
    destino,
    material_id: entrada.materialId,
    cantidad: entrada.cantidad,
  }
  if (comunes.clave !== undefined) payload.clave_idempotencia = comunes.clave
  return { ok: true, payload }
}

export interface EntradaMover {
  origen: TipoInventario
  destino: TipoInventario
  materialId: number
  cantidad: number
  claveIdempotencia?: string
}

export function construirPayloadMover(
  entrada: EntradaMover,
): ResultadoPayload<MoverMaterialPayload> {
  const origen = resolverInventario(entrada.origen)
  const destino = resolverInventario(entrada.destino)
  if (origen === null || destino === null) {
    return fallo(
      'TIPO_INVENTARIO_INVALIDO',
      'El inventario de origen o destino no admite esta operación.',
    )
  }
  // GENERAL -> GENERAL o FO -> FO son «destino = origen» (422).
  if (origen === destino) {
    return fallo(
      'DESTINO_IGUAL_ORIGEN',
      'El inventario destino debe ser distinto del origen.',
    )
  }
  const comunes = validarComunes(
    entrada.materialId,
    entrada.cantidad,
    entrada.claveIdempotencia,
  )
  if (!comunes.ok) return fallo(comunes.codigo, comunes.mensaje)

  const payload: MoverMaterialPayload = {
    origen,
    destino,
    material_id: entrada.materialId,
    cantidad: entrada.cantidad,
  }
  if (comunes.clave !== undefined) payload.clave_idempotencia = comunes.clave
  return { ok: true, payload }
}

/**
 * Clave de idempotencia (REQ-P2-INV-007). NO es pura (aleatoria): se invoca
 * UNA vez por APERTURA del diálogo y se conserva para los reintentos del mismo
 * intento (red caída, doble clic); se regenera al reabrir. Usa
 * `crypto.randomUUID` (36 caracteres, dentro del máximo de 100).
 */
export function generarClaveIdempotencia(
  prefijo: 'sumar' | 'mover' | 'agregar-todo' = 'sumar',
): string {
  const aleatorio =
    typeof globalThis.crypto?.randomUUID === 'function'
      ? globalThis.crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  return `${prefijo}-${aleatorio}`
}
