import {
  CANTIDAD_MAX_DECIMAL,
  CANTIDAD_MAX_DECIMALES,
  formatearCantidad,
} from './cantidad'

// ============================================================================
// TRADUCTOR PURO DE ERRORES HTTP -> MENSAJES DE FORMULARIO
// +Cantidad / Mover (REQ-P2-INV-001/003/004/007)
//
// Recibe status + cuerpo (`{error:{code,message,...}}`, o el `{detail:[...]}`
// de validación de FastAPI) y devuelve un texto en español orientado al
// operador. NUNCA se muestra al usuario el `message` crudo del servidor
// (puede contener SQL, ids internos o trazas): solo se usa de forma
// interna y conservadora para DISTINGUIR casos dentro de un mismo status.
// Una operación fallida no modificó ningún inventario (atomicidad,
// REQ-P2-INV-004), salvo cuando el resultado es desconocido (red/5xx).
//
// Códigos del contrato (openspec.yaml):
//   400 cantidad <= 0, stock insuficiente en el origen o desbordamiento
//       numérico (SQLSTATE 22003: «excede el rango soportado»)
//   403 sin alcance sobre las secciones GENERAL implicadas
//   404 material/registro de inventario inexistente
//   409 más de una/ninguna sección GENERAL activa, o clave de idempotencia
//       en uso por otro actor
//   422 destino = origen, cantidad con más de 3 decimales, negativa o fuera
//       de rango (escala/dígitos de NUMERIC(12,3)); campos no declarados
//
// Mensajes pensados para el slot `error` de OperadorRapidoDialog.
// ============================================================================

export type OperacionRapida = 'sumar' | 'mover'

export interface ContextoErrorOperador {
  operacion: OperacionRapida
  /** Stock visible del origen (solo para enriquecer el mensaje de 400). */
  stockActual?: number
  um?: string | null
}

/** Campo del formulario al que apunta el error (o el diálogo completo). */
export type CampoError = 'cantidad' | 'destino' | 'dialogo'

export interface ErrorOperadorTraducido {
  mensaje: string
  campo: CampoError
  /**
   * `rechazada`: el servidor evaluó y rechazó (nada cambió).
   * `desconocido`: no se sabe si se aplicó (sin respuesta / 5xx): reintentar
   * con la MISMA clave de idempotencia es seguro y no duplica efectos.
   */
  resultado: 'rechazada' | 'desconocido'
  /** Si tiene sentido reintentar sin cambiar nada (misma clave). */
  reintentable: boolean
  /** Código de dominio del servidor (solo para telemetría; no se muestra). */
  codigoServidor: string | null
}

interface CuerpoNormalizado {
  code: string | null
  message: string
  detalle: unknown[]
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null
}

/** Soporta `{error:{...}}`, `{detail:{error:{...}}}` y `{detail:[...]}`. */
function normalizarCuerpo(cuerpo: unknown): CuerpoNormalizado {
  const vacio: CuerpoNormalizado = { code: null, message: '', detalle: [] }
  if (!esObjeto(cuerpo)) return vacio

  let error: unknown = cuerpo.error
  if (!esObjeto(error) && esObjeto(cuerpo.detail)) {
    error = cuerpo.detail.error
  }
  const detalle = Array.isArray(cuerpo.detail) ? cuerpo.detail : []

  if (esObjeto(error)) {
    return {
      code: typeof error.code === 'string' ? error.code : null,
      message: typeof error.message === 'string' ? error.message : '',
      detalle,
    }
  }
  // Validación de esquema: se concatenan los `msg` SOLO para clasificar.
  const textos = detalle
    .map((item) =>
      esObjeto(item) && typeof item.msg === 'string' ? item.msg : '',
    )
    .filter(Boolean)
  return { ...vacio, message: textos.join(' '), detalle }
}

/** ¿El detalle de validación de FastAPI apunta a este campo? */
function detalleApunta(detalle: unknown[], campo: string): boolean {
  return detalle.some((item) => {
    if (!esObjeto(item) || !Array.isArray(item.loc)) return false
    return item.loc.some((parte) => parte === campo)
  })
}

function resultado(
  base: Omit<ErrorOperadorTraducido, 'resultado' | 'reintentable'> &
    Partial<Pick<ErrorOperadorTraducido, 'resultado' | 'reintentable'>>,
): ErrorOperadorTraducido {
  return { resultado: 'rechazada', reintentable: false, ...base }
}

const SUFIJO_NADA_CAMBIO = ' No se modificó ningún inventario.'

function cantidadConUm(contexto: ContextoErrorOperador): string | null {
  if (contexto.stockActual === undefined) return null
  const um = contexto.um ? ` ${contexto.um}` : ''
  return `${formatearCantidad(contexto.stockActual)}${um}`
}

const MENSAJE_CANTIDAD_MAXIMA = `La cantidad (o el stock resultante) excede el máximo permitido de ${formatearCantidad(CANTIDAD_MAX_DECIMAL)}. No se modificó ningún inventario.`
const MENSAJE_CANTIDAD_ESCALA = `La cantidad admite máximo ${CANTIDAD_MAX_DECIMALES} decimales; el sistema no redondea automáticamente. Corrige el valor e intenta de nuevo.`

function traducir400(
  cuerpo: CuerpoNormalizado,
  contexto: ContextoErrorOperador,
): ErrorOperadorTraducido {
  const msg = cuerpo.message.toLowerCase()
  const codigoServidor = cuerpo.code

  if (/stock insuficiente|no cuenta con stock suficiente/.test(msg)) {
    const stock = cantidadConUm(contexto)
    return resultado({
      campo: 'cantidad',
      codigoServidor,
      mensaje:
        `La cantidad supera el stock disponible en el inventario de origen${stock ? ` (${stock} según la pantalla)` : ''}. ` +
        `Actualiza el inventario y ajusta la cantidad.${SUFIJO_NADA_CAMBIO}`,
    })
  }
  if (/fuera de rango|out of range|excede el rango/.test(msg)) {
    return resultado({
      campo: 'cantidad',
      codigoServidor,
      mensaje: MENSAJE_CANTIDAD_MAXIMA,
    })
  }
  // «debe ser mayor que cero» / negativa / cualquier otro 400 de este
  // endpoint: el contrato solo define 400 por cantidad.
  return resultado({
    campo: 'cantidad',
    codigoServidor,
    mensaje: `La cantidad debe ser un número mayor que 0.${SUFIJO_NADA_CAMBIO}`,
  })
}

function traducir404(
  cuerpo: CuerpoNormalizado,
  contexto: ContextoErrorOperador,
): ErrorOperadorTraducido {
  return resultado({
    campo: 'dialogo',
    codigoServidor: cuerpo.code,
    mensaje:
      contexto.operacion === 'sumar'
        ? 'El material no existe, está inactivo o aún no tiene registro en este inventario. Si es un material nuevo, registra primero su carga inicial. Actualiza la lista e intenta de nuevo.'
        : 'El material no existe, está inactivo o ya no tiene registro en el inventario de origen. Actualiza la lista e intenta de nuevo.',
  })
}

function traducir409(cuerpo: CuerpoNormalizado): ErrorOperadorTraducido {
  const msg = cuerpo.message.toLowerCase()
  const codigoServidor = cuerpo.code

  if (codigoServidor === 'IDEMPOTENT_REPLAY') {
    return resultado({
      campo: 'dialogo',
      codigoServidor,
      mensaje:
        'Esta operación ya fue registrada anteriormente. Actualiza el inventario para ver el resultado y no la repitas.',
    })
  }
  if (/otro actor|otro usuario/.test(msg)) {
    return resultado({
      campo: 'dialogo',
      codigoServidor,
      mensaje:
        'No fue posible validar la operación (clave de operación en uso por otro usuario). Cierra este diálogo y vuelve a abrirlo para intentarlo de nuevo.',
    })
  }
  if (/no existe una sección general activa|ninguna/.test(msg)) {
    return resultado({
      campo: 'dialogo',
      codigoServidor,
      mensaje: `No hay un Inventario General activo para completar la operación. Contacta a un administrador.${SUFIJO_NADA_CAMBIO}`,
    })
  }
  if (/destino único|más de una|mas de una|varias|ambigu/.test(msg)) {
    return resultado({
      campo: 'dialogo',
      codigoServidor,
      mensaje: `Hay más de un Inventario General activo con este material y no es posible determinar cuál usar. Contacta a un administrador.${SUFIJO_NADA_CAMBIO}`,
    })
  }
  return resultado({
    campo: 'dialogo',
    codigoServidor,
    mensaje: `La operación entra en conflicto con el estado actual del inventario. Actualiza la información e intenta de nuevo.${SUFIJO_NADA_CAMBIO}`,
  })
}

function traducir422(
  cuerpo: CuerpoNormalizado,
  contexto: ContextoErrorOperador,
): ErrorOperadorTraducido {
  const msg = cuerpo.message.toLowerCase()
  const codigoServidor = cuerpo.code

  // Validación de esquema (FastAPI/Pydantic): cuerpo `{detail:[...]}`.
  if (detalleApunta(cuerpo.detalle, 'cantidad')) {
    const tipos = cuerpo.detalle
      .filter(
        (item) =>
          esObjeto(item) &&
          Array.isArray(item.loc) &&
          item.loc.includes('cantidad'),
      )
      .map((item) => (esObjeto(item) ? String(item.type) : ''))
    const campo = 'cantidad' as const
    if (tipos.includes('decimal_max_places')) {
      return resultado({ campo, codigoServidor, mensaje: MENSAJE_CANTIDAD_ESCALA })
    }
    if (tipos.includes('decimal_max_digits')) {
      return resultado({ campo, codigoServidor, mensaje: MENSAJE_CANTIDAD_MAXIMA })
    }
    if (tipos.some((t) => t === 'greater_than' || t === 'greater_than_equal')) {
      return resultado({
        campo,
        codigoServidor,
        mensaje: 'La cantidad debe ser mayor que 0.',
      })
    }
    return resultado({
      campo,
      codigoServidor,
      mensaje:
        'La cantidad debe ser un número válido, mayor que 0 y con máximo 3 decimales.',
    })
  }
  // Defensa en profundidad de PostgreSQL (P0001 → 422 canónico).
  if (/m[aá]ximo 3 decimales|3 decimales/.test(msg)) {
    return resultado({
      campo: 'cantidad',
      codigoServidor,
      mensaje: MENSAJE_CANTIDAD_ESCALA,
    })
  }
  if (
    (/destino/.test(msg) && /origen/.test(msg)) ||
    /mismo inventario|igual al origen|distint/.test(msg) ||
    detalleApunta(cuerpo.detalle, 'destino')
  ) {
    return resultado({
      campo: 'destino',
      codigoServidor,
      mensaje:
        contexto.operacion === 'mover'
          ? 'El inventario destino debe ser distinto del origen. Elige otro destino.'
          : 'La operación no es válida para este inventario.',
    })
  }
  if (/fuera de rango|out of range|rango/.test(msg)) {
    return resultado({
      campo: 'cantidad',
      codigoServidor,
      mensaje: MENSAJE_CANTIDAD_MAXIMA,
    })
  }
  return resultado({
    campo: 'dialogo',
    codigoServidor,
    mensaje: `Los datos de la operación no son válidos. Revisa el destino y la cantidad e intenta de nuevo.${SUFIJO_NADA_CAMBIO}`,
  })
}

/**
 * Traduce una respuesta HTTP de los operadores rápidos.
 *
 * @param status  código HTTP; `undefined`/`null`/0 = sin respuesta (red).
 * @param cuerpo  cuerpo JSON de la respuesta (cualquier forma; se normaliza).
 */
export function traducirErrorOperador(
  status: number | null | undefined,
  cuerpo: unknown,
  contexto: ContextoErrorOperador,
): ErrorOperadorTraducido {
  const normalizado = normalizarCuerpo(cuerpo)

  if (status === undefined || status === null || status === 0) {
    return {
      mensaje:
        'No se recibió respuesta del servidor, por lo que no sabemos si la operación se aplicó. Revisa tu conexión y vuelve a confirmar: el reintento no duplica la operación.',
      campo: 'dialogo',
      resultado: 'desconocido',
      reintentable: true,
      codigoServidor: null,
    }
  }

  switch (status) {
    case 400:
      return traducir400(normalizado, contexto)
    case 403:
      return resultado({
        campo: 'dialogo',
        codigoServidor: normalizado.code,
        mensaje:
          'No tienes permiso para realizar esta operación sobre este inventario. Solicita acceso a un administrador.',
      })
    case 404:
      return traducir404(normalizado, contexto)
    case 409:
      return traducir409(normalizado)
    case 422:
      return traducir422(normalizado, contexto)
    default:
      if (status >= 500) {
        return {
          mensaje:
            'El servidor no pudo completar la operación y no sabemos si se aplicó. Espera un momento y vuelve a confirmar: el reintento no duplica la operación.',
          campo: 'dialogo',
          resultado: 'desconocido',
          reintentable: true,
          codigoServidor: normalizado.code,
        }
      }
      return resultado({
        campo: 'dialogo',
        codigoServidor: normalizado.code,
        mensaje: `No fue posible completar la operación. Actualiza la información e intenta de nuevo.${SUFIJO_NADA_CAMBIO}`,
      })
  }
}

/**
 * Extrae `{status, cuerpo}` de un error lanzado por el cliente HTTP sin
 * importar axios (duck-typing sobre `error.response`). Sin `response` (error
 * de red/timeout) devuelve `status: undefined`.
 */
export function extraerRespuestaError(error: unknown): {
  status: number | undefined
  cuerpo: unknown
} {
  if (esObjeto(error) && esObjeto(error.response)) {
    const { status, data } = error.response
    return {
      status: typeof status === 'number' ? status : undefined,
      cuerpo: data,
    }
  }
  return { status: undefined, cuerpo: undefined }
}
