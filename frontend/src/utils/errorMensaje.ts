import axios from 'axios'
import {
  CANTIDAD_MAX_DECIMAL,
  CANTIDAD_MAX_DECIMALES,
  formatearCantidad,
} from './cantidad'

// ============================================================================
// MENSAJES OPERATIVOS PARA ERRORES DE MUTACIÓN (RF-6, RF-8) — capa UX
//
// Traduce el error HTTP de una mutación (PATCH de material, DELETE, TRANSF,
// cancelación, ...) a un texto en español orientado al operador. Cubre:
//  - 400/403/404/409 con cuerpo canónico `{error:{code,message}}`: se muestra
//    el mensaje canónico del backend (p. ej. «Se requiere rol administrador»).
//  - 422 de validación de Pydantic (`{detail:[{loc,type,msg}]}`): escala > 3
//    decimales, exceso de dígitos, negativos y campos no declarados, con el
//    nombre legible del campo.
// Nunca se contradice al servidor ni se decide validez transaccional: solo se
// redacta lo que el backend ya resolvió.
// ============================================================================

const ETIQUETA_CAMPO: Record<string, string> = {
  valor_unitario: 'Valor Unitario',
  stock_actual: 'Stock Actual',
  stock_inicial: 'Stock Inicial',
  nuevo_stock: 'Nuevo stock',
  cantidad: 'La cantidad',
  cantidad_tomada: 'La cantidad tomada',
  cantidad_consumida: 'La cantidad consumida',
}

interface ItemDetalle {
  loc: unknown[]
  type: string
}

function esObjeto(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null
}

function itemsDetalle(data: unknown): ItemDetalle[] {
  if (!esObjeto(data) || !Array.isArray(data.detail)) return []
  return data.detail.filter(esObjeto).map((item) => ({
    loc: Array.isArray(item.loc) ? item.loc : [],
    type: typeof item.type === 'string' ? item.type : '',
  }))
}

function campoDe(item: ItemDetalle): string | null {
  for (const parte of [...item.loc].reverse()) {
    if (typeof parte === 'string' && parte in ETIQUETA_CAMPO) return parte
  }
  return null
}

/** Mensaje del primer error de validación de campo decimal reconocible. */
function mensajeValidacion(items: ItemDetalle[]): string | null {
  for (const item of items) {
    const campo = campoDe(item)
    if (campo === null) continue
    const etiqueta = ETIQUETA_CAMPO[campo]
    switch (item.type) {
      case 'decimal_max_places':
        return `${etiqueta} admite máximo ${CANTIDAD_MAX_DECIMALES} decimales; no se redondea automáticamente.`
      case 'decimal_max_digits':
      case 'decimal_whole_digits':
      case 'less_than_equal':
        return `${etiqueta} excede el máximo permitido (${formatearCantidad(CANTIDAD_MAX_DECIMAL)}).`
      case 'greater_than':
        return `${etiqueta} debe ser mayor que 0.`
      case 'greater_than_equal':
        return `${etiqueta} no puede ser negativo.`
      default:
        return `${etiqueta} no es un número válido (hasta ${CANTIDAD_MAX_DECIMALES} decimales).`
    }
  }
  if (items.some((i) => i.type === 'extra_forbidden')) {
    return 'La solicitud incluye un campo no permitido. Actualiza la pantalla e intenta de nuevo.'
  }
  return null
}

/**
 * Texto para el toast de error de una mutación. `fallback` se usa cuando el
 * error no trae información reconocible.
 */
export function mensajeErrorApi(
  error: unknown,
  fallback = 'Ocurrió un error',
): string {
  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data
    if (esObjeto(data) && esObjeto(data.error)) {
      const msg = data.error.message
      if (typeof msg === 'string' && msg !== '') return msg
    }
    if (error.response?.status === 422) {
      const mensaje = mensajeValidacion(itemsDetalle(data))
      if (mensaje !== null) return mensaje
    }
  }
  return fallback
}
