import { useRef, useState } from 'react'
import { useToast } from './useToasts'
import { useSumarCantidad } from './useSumarCantidad'
import { useMoverMaterial } from './useMoverMaterial'
import {
  construirPayloadMover,
  construirPayloadSumar,
  generarClaveIdempotencia,
} from '../utils/operadorPayload'
import type { TipoInventario } from '../utils/operadorPayload'
import {
  extraerRespuestaError,
  traducirErrorOperador,
} from '../utils/operadorErrores'
import type { OperacionRapida } from '../utils/operadorErrores'
import type { DestinoMover, MoverSubmit } from '../components/MoverMaterialDialog'

// ============================================================================
// FLUJO DE LOS OPERADORES RÁPIDOS (+Cantidad / Mover) — capa de estado
//
// Cablea SumarCantidadDialog / MoverMaterialDialog con POST
// /inventario/sumar-cantidad y /inventario/mover. Compartido por
// SeccionGeneral y FibraOptica (los dos sitios donde se renderiza
// MaterialDetailDrawer).
//
// Reglas (REQ-P2-INV-001/003/004/007):
//  - La clave de idempotencia se genera UNA vez por APERTURA del diálogo
//    (abrirSumar/abrirMover) y se reutiliza en TODOS los envíos de esa
//    apertura (reintentos tras red caída/5xx = resultado 'desconocido': el
//    servidor responde con el resultado original, sin duplicar). Reabrir el
//    diálogo genera una clave nueva.
//  - El diálogo se cierra SOLO tras la respuesta 200.
//  - Los errores se traducen con `traducirErrorOperador` y se pasan por
//    `errorMessage`; `onEditar` limpia el error obsoleto.
//  - El toast de éxito muestra el stock DEVUELTO por el servidor
//    (stock_nuevo / stock_origen / stock_destino); el cliente no calcula.
//  - La recarga de stock (ambos extremos) y auditoría la hacen las mutaciones
//    (useSumarCantidad / useMoverMaterial → invalidateQueries).
// ============================================================================

/** Contexto fijo del material sobre el que se opera (presentación). */
export interface MaterialOperacion {
  materialId: number
  codigo: string
  um: string | null
  /** Stock VISIBLE (solo enriquece mensajes de error; el servidor decide). */
  stockActual: number
  /** Nombre del inventario donde está el material. */
  origenLabel: string
}

export interface UseOperadorRapidoParams {
  /** Tipo del inventario del material: destino de +Cantidad y origen de Mover. */
  inventario: TipoInventario
  material: MaterialOperacion | null
  /** Inventarios candidatos del select «Mover» (para etiquetar el destino). */
  destinos: DestinoMover[]
}

function numero(valor: number): string {
  return valor.toLocaleString('es-MX')
}

function conUm(valor: number, um: string | null): string {
  return `${numero(valor)}${um ? ` ${um}` : ''}`
}

export function useOperadorRapido({
  inventario,
  material,
  destinos,
}: UseOperadorRapidoParams) {
  const { pushToast } = useToast()
  const sumarMut = useSumarCantidad()
  const moverMut = useMoverMaterial()

  const [operacion, setOperacion] = useState<OperacionRapida | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Clave de la apertura vigente del diálogo (no se renderiza → ref).
  const claveRef = useRef<string | null>(null)

  const abrir = (op: OperacionRapida) => {
    claveRef.current = generarClaveIdempotencia(op)
    setError(null)
    setOperacion(op)
  }

  const cerrar = () => {
    claveRef.current = null
    setError(null)
    setOperacion(null)
  }

  const manejarError = (err: unknown, op: OperacionRapida) => {
    const { status, cuerpo } = extraerRespuestaError(err)
    const traducido = traducirErrorOperador(status, cuerpo, {
      operacion: op,
      stockActual: material?.stockActual,
      um: material?.um,
    })
    setError(traducido.mensaje)
  }

  const sumarSubmit = async (cantidad: number): Promise<void> => {
    if (!material || sumarMut.isPending) return
    const construido = construirPayloadSumar({
      inventario,
      materialId: material.materialId,
      cantidad,
      claveIdempotencia: claveRef.current ?? undefined,
    })
    if (!construido.ok) {
      setError(construido.mensaje)
      return
    }
    setError(null)
    try {
      const out = await sumarMut.mutateAsync(construido.payload)
      pushToast(
        out.reenvio_idempotente
          ? `La suma a ${material.codigo} ya estaba registrada (no se duplicó). Stock en ${material.origenLabel}: ${conUm(out.stock_nuevo, material.um)}.`
          : `Se sumaron ${conUm(cantidad, material.um)} a ${material.codigo}. Stock en ${material.origenLabel}: ${conUm(out.stock_nuevo, material.um)}.`,
      )
      cerrar()
    } catch (err) {
      manejarError(err, 'sumar')
    }
  }

  const moverSubmit = async (datos: MoverSubmit): Promise<void> => {
    if (!material || moverMut.isPending) return
    const opcionDestino = destinos.find((d) => d.value === datos.destino)
    const destinoTipo = datos.destinoTipo ?? opcionDestino?.tipo
    if (destinoTipo === undefined) {
      setError('No se pudo identificar el inventario destino.')
      return
    }
    const construido = construirPayloadMover({
      origen: inventario,
      destino: destinoTipo,
      materialId: material.materialId,
      cantidad: datos.cantidad,
      claveIdempotencia: claveRef.current ?? undefined,
    })
    if (!construido.ok) {
      setError(construido.mensaje)
      return
    }
    setError(null)
    const destinoLabel = opcionDestino?.label ?? 'el inventario destino'
    try {
      const out = await moverMut.mutateAsync(construido.payload)
      const stocks = `Stock en ${material.origenLabel}: ${conUm(out.stock_origen, material.um)}; en ${destinoLabel}: ${conUm(out.stock_destino, material.um)}.`
      pushToast(
        out.reenvio_idempotente
          ? `El movimiento de ${material.codigo} ya estaba registrado (no se duplicó). ${stocks}`
          : `Se movieron ${conUm(datos.cantidad, material.um)} de ${material.codigo} de ${material.origenLabel} a ${destinoLabel}. ${stocks}`,
      )
      cerrar()
    } catch (err) {
      manejarError(err, 'mover')
    }
  }

  return {
    /** Operación con diálogo abierto (null = ninguno). */
    operacion,
    abrirSumar: () => abrir('sumar'),
    abrirMover: () => abrir('mover'),
    cerrar,
    /** Props listas para <SumarCantidadDialog /> (junto a open/material/onClose). */
    sumar: {
      onSubmit: sumarSubmit,
      onEditar: () => setError(null),
      isSubmitting: sumarMut.isPending,
      errorMessage: error,
    },
    /** Props listas para <MoverMaterialDialog />. */
    mover: {
      onSubmit: moverSubmit,
      onEditar: () => setError(null),
      isSubmitting: moverMut.isPending,
      errorMessage: error,
    },
  }
}
