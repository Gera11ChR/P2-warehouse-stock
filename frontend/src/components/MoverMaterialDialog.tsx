import { useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import OperadorRapidoDialog from './OperadorRapidoDialog'
import CampoCantidad from './CampoCantidad'
import { mensajeCantidadInvalida, validarCantidad } from '../utils/cantidad'
import { resolverInventario } from '../utils/operadorPayload'
import type { TipoInventario } from '../utils/operadorPayload'
import type { MaterialOperacionContexto } from './SumarCantidadDialog'

// ============================================================================
// DIÁLOGO «MOVER» (REQ-P2-INV-003/004/005)
//
// El formulario CAPTURA la intención («mover N unidades de este inventario a
// otro»); descontar el origen, acreditar el destino y auditar es de
// PostgreSQL (fn_mover_material). Las validaciones de aquí son preliminares.
//
// UX: mover cambia DOS inventarios a la vez (alto riesgo de enviar al
// inventario equivocado). Reglas de diseño:
//  - El destino NO tiene valor por defecto: el operador debe elegirlo
//    conscientemente («— Selecciona destino —») y es obligatorio.
//  - El origen nunca aparece como destino. Se excluye por `value` y, cuando
//    hay `tipo`, TODO inventario del mismo tipo que el origen (el contrato
//    identifica los inventarios por tipo/módulo: GENERAL->GENERAL o
//    FO_PAQUETE->FO_PAQUETE sería «destino = origen», 422).
//  - La cantidad por defecto es el stock completo (REQ-P2-INV-003); regla:
//    entero, 1 <= cantidad <= stock del origen y <= INT4 (mismas reglas
//    numéricas que +Cantidad, utils/cantidad.ts). Si excede el stock se
//    explica; el servidor responde 400 si el stock real es menor.
//  - El botón de confirmar nombra cantidad, material y destino, está
//    deshabilitado con motivo visible mientras el formulario sea inválido y,
//    al intentar enviar con Enter, el foco va al primer campo inválido.
//
// Contrato de props (cableado por @state-agent):
//   open / onClose, material (origen, contexto fijo, o null = cerrado)
//   destinos   inventarios destino candidatos {value, label, tipo?}. `value`
//              es opaco (id de sección); `tipo` ('GENERAL'|'FO_PAQUETE'|
//              'FO_EN_USO') permite construir el payload sin consultar de
//              nuevo la sección.
//   origenValue  `value` del origen: se excluye de las opciones.
//   origenTipo   tipo del origen (si se omite se deduce de `origenValue`).
//   onSubmit({ destino, destinoTipo, cantidad })  `destino` = `value`
//              elegido; `destinoTipo` = `tipo` de esa opción (si se informó);
//              cantidad entera 1..min(stock, INT4). Puede devolver promesa;
//              el padre gestiona `isSubmitting` / `errorMessage` (usar
//              `traducirErrorOperador` sobre 400/403/404/409/422) y cierra
//              solo tras la respuesta aceptada. Sin `onSubmit` Confirmar queda
//              deshabilitado con motivo visible.
//   onEditar()   (opcional) al editar un campo, para limpiar `errorMessage`.
//
// Cableado: `useOperadorRapido` (hooks/useOperadorRapido.ts) conecta `onSubmit`
// a POST /inventario/mover con `construirPayloadMover` (clave de idempotencia
// por APERTURA del diálogo, reutilizada en reintentos) y recarga origen Y
// destino tras cada intento.
// ============================================================================

export interface DestinoMover {
  value: string
  label: string
  /** Tipo de inventario (para excluir el origen y mapear al contrato). */
  tipo?: TipoInventario
}

export interface MoverSubmit {
  destino: string
  destinoTipo?: TipoInventario
  cantidad: number
}

export interface MoverMaterialDialogProps {
  open: boolean
  material: MaterialOperacionContexto | null
  destinos: DestinoMover[]
  origenValue?: string
  origenTipo?: TipoInventario
  onClose: () => void
  onSubmit?: (datos: MoverSubmit) => void | Promise<void>
  /** Se invoca al editar un campo (para limpiar un error del servidor previo). */
  onEditar?: () => void
  isSubmitting?: boolean
  errorMessage?: string | null
}

export default function MoverMaterialDialog(props: MoverMaterialDialogProps) {
  if (!props.open || !props.material) return null
  return <Contenido {...props} material={props.material} />
}

function Contenido({
  open,
  material,
  destinos,
  origenValue,
  origenTipo,
  onClose,
  onSubmit,
  onEditar,
  isSubmitting = false,
  errorMessage = null,
}: MoverMaterialDialogProps & { material: MaterialOperacionContexto }) {
  const [destino, setDestino] = useState('')
  // Cantidad por defecto = stock completo del origen (REQ-P2-INV-003).
  // Sin stock no hay nada que sugerir: el campo nace vacío.
  const [valor, setValor] = useState(
    material.stockActual > 0 ? String(material.stockActual) : '',
  )
  const [tocadoDestino, setTocadoDestino] = useState(false)
  const [tocadoCantidad, setTocadoCantidad] = useState(false)
  const [intentado, setIntentado] = useState(false)
  const selectRef = useRef<HTMLSelectElement>(null)
  const cantidadRef = useRef<HTMLInputElement>(null)

  const tipoOrigen =
    origenTipo ?? destinos.find((d) => d.value === origenValue)?.tipo
  const opciones = destinos.filter(
    (d) =>
      d.value !== origenValue &&
      (d.tipo === undefined || resolverInventario(d.tipo) !== null) &&
      !(tipoOrigen !== undefined && d.tipo === tipoOrigen),
  )
  const destinoElegido = opciones.find((d) => d.value === destino) ?? null

  const sinStock = material.stockActual <= 0
  const validacion = validarCantidad(valor, { maxStock: material.stockActual })
  const cantidad = validacion.ok ? validacion.cantidad : null
  const mensajeCantidad: string | null = validacion.ok
    ? null
    : sinStock
      ? 'No hay stock disponible en el origen para mover.'
      : mensajeCantidadInvalida(validacion.motivo, {
          maxStock: material.stockActual,
        })
  const mensajeDestino: string | null =
    destinoElegido === null ? 'Selecciona el inventario destino.' : null

  const valido = mensajeDestino === null && mensajeCantidad === null
  const primerMensaje = mensajeDestino ?? mensajeCantidad

  const errorDestino =
    mensajeDestino !== null && (tocadoDestino || intentado)
      ? mensajeDestino
      : null
  const errorCantidad =
    mensajeCantidad !== null && (valor !== '' || tocadoCantidad || intentado)
      ? mensajeCantidad
      : null

  const um = material.um ?? ''
  const restante =
    valido && cantidad !== null ? material.stockActual - cantidad : null

  const confirmLabel =
    valido && cantidad !== null && destinoElegido
      ? `Mover ${cantidad.toLocaleString('es-MX')} ${um} a ${destinoElegido.label}`.replace(
          /\s+/g,
          ' ',
        )
      : 'Mover material'

  // Enter con el formulario inválido: no se envía; se revelan los errores y el
  // foco va al PRIMER campo inválido (destino antes que cantidad).
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !valido) {
      event.preventDefault()
      setIntentado(true)
      if (mensajeDestino !== null) selectRef.current?.focus()
      else cantidadRef.current?.focus()
    }
  }

  const motivo = !onSubmit
    ? 'Esta operación aún no está habilitada en esta versión de la interfaz.'
    : primerMensaje !== null
      ? `Confirmar deshabilitado: ${primerMensaje}`
      : undefined

  const destinoAyudaId = 'mover-destino-ayuda'

  return (
    <OperadorRapidoDialog
      open={open}
      titulo="Mover"
      descripcion="Traslada stock de este inventario a otro inventario."
      onClose={onClose}
      initialFocusRef={selectRef}
      resumen={[
        { label: 'Operación', value: 'Mover entre inventarios' },
        {
          label: 'Material',
          value: (
            <>
              <span className="font-mono">{material.codigo}</span>
              {material.descripcion ? ` — ${material.descripcion}` : ''}
            </>
          ),
        },
        { label: 'Origen', value: material.origenLabel },
        {
          label: 'Destino',
          value: destinoElegido?.label ?? (
            <span className="text-slate-400">Sin seleccionar</span>
          ),
        },
        {
          label: 'Cantidad',
          value:
            cantidad !== null
              ? `${cantidad.toLocaleString('es-MX')} ${um}`.trim()
              : '—',
        },
      ]}
      proyeccion={
        restante !== null && cantidad !== null ? (
          <>
            {material.origenLabel}:{' '}
            {material.stockActual.toLocaleString('es-MX')} −{' '}
            {cantidad.toLocaleString('es-MX')} ={' '}
            <strong>{restante.toLocaleString('es-MX')}</strong> {um}
            {destinoElegido && (
              <>
                {' '}
                · {destinoElegido.label}: +{cantidad.toLocaleString('es-MX')}{' '}
                {um}
              </>
            )}
            {restante === 0 && ' · El origen quedaría en 0.'}
          </>
        ) : undefined
      }
      error={errorMessage}
      confirmLabel={confirmLabel}
      onConfirm={() => {
        if (valido && cantidad !== null && destinoElegido) {
          void onSubmit?.({
            destino: destinoElegido.value,
            destinoTipo: destinoElegido.tipo,
            cantidad,
          })
        }
      }}
      confirmDisabled={!valido || !onSubmit}
      confirmDisabledReason={motivo}
      isSubmitting={isSubmitting}
    >
      <div className="space-y-4">
        <div>
          <label
            htmlFor="mover-destino"
            className="text-xs font-semibold uppercase tracking-wide text-slate-400"
          >
            Inventario destino
          </label>
          <select
            id="mover-destino"
            ref={selectRef}
            value={destino}
            onChange={(event) => {
              setDestino(event.target.value)
              onEditar?.()
            }}
            onBlur={() => setTocadoDestino(true)}
            aria-invalid={errorDestino !== null}
            aria-describedby={destinoAyudaId}
            aria-required="true"
            disabled={isSubmitting || opciones.length === 0}
            className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
              errorDestino ? 'border-red-400' : 'border-slate-300'
            }`}
          >
            <option value="">— Selecciona destino —</option>
            {opciones.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
          <p
            id={destinoAyudaId}
            className={`mt-1 text-xs ${
              errorDestino || opciones.length === 0
                ? 'font-medium text-red-600'
                : 'text-slate-500'
            }`}
          >
            {opciones.length === 0
              ? 'No hay otros inventarios disponibles como destino.'
              : (errorDestino ?? `Origen: ${material.origenLabel}.`)}
          </p>
        </div>

        <CampoCantidad
          id="mover-cantidad"
          label="Cantidad a mover"
          value={valor}
          onChange={(v) => {
            setValor(v)
            onEditar?.()
          }}
          onBlur={() => setTocadoCantidad(true)}
          onKeyDown={handleKeyDown}
          error={errorCantidad}
          ayuda={`Por defecto se mueve todo el stock (${material.stockActual.toLocaleString('es-MX')}). Puedes indicar una cantidad parcial.`}
          disabled={isSubmitting}
          inputRef={cantidadRef}
        />
      </div>
    </OperadorRapidoDialog>
  )
}
