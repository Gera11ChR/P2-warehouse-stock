import { useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import OperadorRapidoDialog from './OperadorRapidoDialog'
import CampoCantidad from './CampoCantidad'
import {
  CANTIDAD_MAX_INT4,
  mensajeCantidadInvalida,
  validarCantidad,
} from '../utils/cantidad'

// ============================================================================
// DIÁLOGO «+ CANTIDAD» (REQ-P2-INV-001/005)
//
// El formulario CAPTURA la intención («sumar N unidades a este material»); la
// suma autoritativa, la auditoría inmutable y el rechazo de entradas inválidas
// pertenecen a FastAPI + PostgreSQL (fn_sumar_cantidad). Las validaciones de
// aquí son preliminares y nunca sustituyen al servidor.
//
// Reglas del campo (utils/cantidad.ts): entero > 0, solo dígitos, máximo
// 2.147.483.647 (INT4). Rechaza vacío, 0, negativos, decimales, notación
// científica, texto y espacios. Errores en línea (aria-invalid +
// aria-describedby), envío con Enter, botón deshabilitado con motivo visible
// y foco al campo inválido si se intenta enviar.
//
// La «vista previa» (stock + cantidad = nuevo stock) es solo una PROYECCIÓN
// visual: no se guarda ni se usa como fuente de verdad.
//
// Contrato de props (cableado por @state-agent):
//   open / onClose           control del diálogo (el padre guarda la selección)
//   material                 contexto fijo de la operación (o null = cerrado)
//   onSubmit(cantidad)       cantidad entera 1..INT4. Puede devolver una
//                            promesa; el padre indica `isSubmitting` y
//                            `errorMessage` (usar `traducirErrorOperador`
//                            sobre la respuesta 400/403/404/409/422) y cierra
//                            el diálogo SOLO tras la respuesta aceptada. Sin
//                            `onSubmit`, Confirmar queda deshabilitado con
//                            motivo visible.
//   onEditar()               (opcional) se invoca al editar el campo para que
//                            el padre limpie `errorMessage` obsoleto.
//
// Cableado: `useOperadorRapido` (hooks/useOperadorRapido.ts) conecta `onSubmit`
// a POST /inventario/sumar-cantidad con `construirPayloadSumar` (clave de
// idempotencia por APERTURA del diálogo, reutilizada en reintentos), recarga
// el stock afectado y muestra el toast con el stock devuelto por el servidor.
// ============================================================================

export interface MaterialOperacionContexto {
  codigo: string
  descripcion: string | null
  um: string | null
  stockActual: number
  /** Nombre del inventario origen (p. ej. «Inventario General», «Fibra Óptica - Paquete»). */
  origenLabel: string
}

export interface SumarCantidadDialogProps {
  open: boolean
  material: MaterialOperacionContexto | null
  onClose: () => void
  onSubmit?: (cantidad: number) => void | Promise<void>
  /** Se invoca al editar el campo (para limpiar un error del servidor previo). */
  onEditar?: () => void
  isSubmitting?: boolean
  errorMessage?: string | null
}

export default function SumarCantidadDialog(props: SumarCantidadDialogProps) {
  if (!props.open || !props.material) return null
  return <Contenido {...props} material={props.material} />
}

function Contenido({
  open,
  material,
  onClose,
  onSubmit,
  onEditar,
  isSubmitting = false,
  errorMessage = null,
}: SumarCantidadDialogProps & { material: MaterialOperacionContexto }) {
  const [valor, setValor] = useState('')
  const [tocado, setTocado] = useState(false)
  const [intentado, setIntentado] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const validacion = validarCantidad(valor)
  const cantidad = validacion.ok ? validacion.cantidad : null
  // Preliminar: el stock resultante no puede rebasar INT4 (el servidor decide).
  const desborda =
    cantidad !== null && material.stockActual + cantidad > CANTIDAD_MAX_INT4

  const mensajeInvalido: string | null = !validacion.ok
    ? mensajeCantidadInvalida(validacion.motivo)
    : desborda
      ? `El stock resultante superaría el máximo permitido (${CANTIDAD_MAX_INT4.toLocaleString('es-MX')}). Reduce la cantidad.`
      : null
  const invalido = mensajeInvalido !== null
  // Un valor ya escrito y erróneo se señala de inmediato; el campo vacío solo
  // tras salir de él o al intentar enviar (no regañar antes de empezar).
  const errorCampo =
    mensajeInvalido !== null && (valor !== '' || tocado || intentado)
      ? mensajeInvalido
      : null

  const um = material.um ?? ''
  const confirmLabel =
    cantidad !== null && !invalido
      ? `Sumar ${cantidad.toLocaleString('es-MX')} ${um} a ${material.codigo}`.replace(
          /\s+/g,
          ' ',
        )
      : 'Sumar cantidad'

  // Enter con el campo inválido: no se envía; se muestra el error y el foco
  // permanece en el campo (el botón deshabilitado no dispara el submit).
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && invalido) {
      event.preventDefault()
      setIntentado(true)
      inputRef.current?.focus()
    }
  }

  const motivo = !onSubmit
    ? 'Esta operación aún no está habilitada en esta versión de la interfaz.'
    : mensajeInvalido !== null
      ? `Confirmar deshabilitado: ${mensajeInvalido}`
      : undefined

  return (
    <OperadorRapidoDialog
      open={open}
      titulo="+ Cantidad"
      descripcion="Suma unidades al stock actual del material."
      onClose={onClose}
      initialFocusRef={inputRef}
      resumen={[
        { label: 'Operación', value: 'Sumar cantidad al stock' },
        {
          label: 'Material',
          value: (
            <>
              <span className="font-mono">{material.codigo}</span>
              {material.descripcion ? ` — ${material.descripcion}` : ''}
            </>
          ),
        },
        { label: 'Inventario', value: material.origenLabel },
        {
          label: 'Stock actual',
          value: `${material.stockActual.toLocaleString('es-MX')} ${um}`.trim(),
        },
      ]}
      proyeccion={
        cantidad !== null && !invalido ? (
          <>
            Stock {material.stockActual.toLocaleString('es-MX')} +{' '}
            {cantidad.toLocaleString('es-MX')} ={' '}
            <strong>
              {(material.stockActual + cantidad).toLocaleString('es-MX')}
            </strong>{' '}
            {um}
          </>
        ) : undefined
      }
      error={errorMessage}
      confirmLabel={confirmLabel}
      onConfirm={() => {
        if (cantidad !== null && !invalido) void onSubmit?.(cantidad)
      }}
      confirmDisabled={invalido || !onSubmit}
      confirmDisabledReason={motivo}
      isSubmitting={isSubmitting}
    >
      <CampoCantidad
        id="sumar-cantidad-input"
        label="Cantidad a sumar"
        value={valor}
        onChange={(v) => {
          setValor(v)
          onEditar?.()
        }}
        onBlur={() => setTocado(true)}
        onKeyDown={handleKeyDown}
        error={errorCampo}
        ayuda="Número entero mayor que 0. Presiona Enter para confirmar."
        disabled={isSubmitting}
        inputRef={inputRef}
      />
    </OperadorRapidoDialog>
  )
}
