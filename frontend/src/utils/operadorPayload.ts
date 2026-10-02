import type { SeccionTransferible } from '../types'
import { CANTIDAD_MAX_INT4 } from './cantidad'

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
// Mapeo de tipo de inventario (`SeccionTransferible['tipo']`) -> contrato:
//   GENERAL    -> destino/origen = 'GENERAL'            (sin módulo)
//   FO_PAQUETE -> destino/origen = 'FO' + modulo 'PAQUETE'
//   FO_EN_USO  -> destino/origen = 'FO' + modulo 'EN_USO'
// ============================================================================

/** Tipo de inventario tal como lo publica /inventario/secciones/transferibles. */
export type TipoInventario = SeccionTransferible['tipo']
export type InventarioContrato = 'GENERAL' | 'FO'
export type ModuloFo = 'PAQUETE' | 'EN_USO'

/** Cuerpo de POST /api/v1/inventario/sumar-cantidad. */
export interface SumarCantidadPayload {
  destino: InventarioContrato
  /** Obligatorio cuando destino = FO; ausente cuando GENERAL. */
  modulo?: ModuloFo
  material_id: number
  cantidad: number
  clave_idempotencia?: string
}

/** Cuerpo de POST /api/v1/inventario/mover. */
export interface MoverMaterialPayload {
  origen: InventarioContrato
  origen_modulo?: ModuloFo
  destino: InventarioContrato
  destino_modulo?: ModuloFo
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

interface InventarioResuelto {
  inventario: InventarioContrato
  modulo?: ModuloFo
}

/** GENERAL -> {GENERAL}; FO_PAQUETE/FO_EN_USO -> {FO, modulo}; otro -> null. */
export function resolverInventario(tipo: string): InventarioResuelto | null {
  switch (tipo) {
    case 'GENERAL':
      return { inventario: 'GENERAL' }
    case 'FO_PAQUETE':
      return { inventario: 'FO', modulo: 'PAQUETE' }
    case 'FO_EN_USO':
      return { inventario: 'FO', modulo: 'EN_USO' }
    default:
      return null
  }
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
  if (
    !Number.isSafeInteger(cantidad) ||
    cantidad <= 0 ||
    cantidad > CANTIDAD_MAX_INT4
  ) {
    return {
      ok: false,
      codigo: 'CANTIDAD_INVALIDA',
      mensaje: `La cantidad debe ser un entero entre 1 y ${CANTIDAD_MAX_INT4.toLocaleString('es-MX')}.`,
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
    destino: destino.inventario,
    material_id: entrada.materialId,
    cantidad: entrada.cantidad,
  }
  if (destino.modulo) payload.modulo = destino.modulo
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
  // El contrato identifica los inventarios por (tipo, módulo): GENERAL ->
  // GENERAL o FO/PAQUETE -> FO/PAQUETE son «destino = origen» (422).
  if (
    origen.inventario === destino.inventario &&
    origen.modulo === destino.modulo
  ) {
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
    origen: origen.inventario,
    destino: destino.inventario,
    material_id: entrada.materialId,
    cantidad: entrada.cantidad,
  }
  if (origen.modulo) payload.origen_modulo = origen.modulo
  if (destino.modulo) payload.destino_modulo = destino.modulo
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
