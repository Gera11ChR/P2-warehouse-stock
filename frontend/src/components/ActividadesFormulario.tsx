import { useState } from 'react'
import type { FormEvent } from 'react'
import { actividadSchema } from '../schemas/actividad'
import type { ActividadCreatePayload } from '../types'

// ============================================================================
// FORMULARIO — CAPTURA DE ACTIVIDADES (Etapa 1)
//
// Captura la intención; el backend valida y PostgreSQL decide (folio, fecha,
// materiales y valor unitario NO se capturan ni se calculan aquí).
//   * Fecha: solo lectura, «Automatizado» (se registra al confirmar).
//   * Vehículo, Nombre Cliente(s), Dirección(es): obligatorios; los
//     placeholders son los ejemplos EXACTOS del documento de requerimientos.
//   * Actividades realizadas: una celda inicial; «+ Agregar» añade celdas
//     (máx. 30); las vacías se descartan al confirmar.
//   * Comentarios: opcional; vacío => `null` en el payload (observación T7).
//
// Validación SOLO de forma (actividadSchema); el backend es la autoridad.
// Los datos escritos se conservan si el backend rechaza (el estado vive aquí
// y el panel no desmonta el formulario).
// ============================================================================

export const PLACEHOLDER_CLIENTES = 'Ej. Acelmo Hernández, Guillermina Juárez, …'
export const PLACEHOLDER_DIRECCIONES = 'Ej. Huapacal 2da, Los Palmares, …'
export const MAX_CELDAS = 30

interface Props {
  /** Seguimiento a documentar; `null` => formulario deshabilitado (RF-3). */
  seguimientoId: number | null
  /** Confirmación en curso (estado «pendiente», RF-17). */
  enviando: boolean
  onSubmit: (payload: ActividadCreatePayload) => void
}

const CLASE_INPUT =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-400'
const CLASE_ETIQUETA =
  'text-xs font-semibold uppercase tracking-wide text-slate-500'

export default function ActividadesFormulario({
  seguimientoId,
  enviando,
  onSubmit,
}: Props) {
  const [vehiculo, setVehiculo] = useState('')
  const [clientes, setClientes] = useState('')
  const [direcciones, setDirecciones] = useState('')
  const [celdas, setCeldas] = useState<string[]>([''])
  const [comentarios, setComentarios] = useState('')
  const [errores, setErrores] = useState<string[]>([])

  const bloqueado = seguimientoId === null || enviando

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (seguimientoId === null) return

    const payload: ActividadCreatePayload = {
      seguimiento_id: seguimientoId,
      vehiculo: vehiculo.trim(),
      clientes: clientes.trim(),
      direcciones: direcciones.trim(),
      // Las celdas vacías se descartan antes de enviar (RF-6).
      actividades: celdas.map((c) => c.trim()).filter((c) => c !== ''),
      comentarios: comentarios.trim() === '' ? null : comentarios,
    }

    const resultado = actividadSchema.safeParse(payload)
    if (!resultado.success) {
      const mensajes = new Set<string>()
      for (const issue of resultado.error.issues) {
        if (issue.path[0] === 'actividades' && issue.path.length === 1) {
          mensajes.add('Registre al menos una actividad realizada (máx. 30).')
        } else if (issue.path[0] === 'actividades') {
          mensajes.add(issue.message)
        } else if (issue.path[0] === 'vehiculo') {
          mensajes.add(
            vehiculo.trim() === ''
              ? 'El vehículo es obligatorio.'
              : 'El vehículo admite máximo 100 caracteres.',
          )
        } else if (issue.path[0] === 'clientes') {
          mensajes.add(
            clientes.trim() === ''
              ? 'El nombre del cliente es obligatorio.'
              : 'Cliente(s) admite máximo 500 caracteres.',
          )
        } else if (issue.path[0] === 'direcciones') {
          mensajes.add(
            direcciones.trim() === ''
              ? 'La dirección es obligatoria.'
              : 'Dirección(es) admite máximo 500 caracteres.',
          )
        } else if (issue.path[0] === 'comentarios') {
          mensajes.add('Los comentarios admiten máximo 2000 caracteres.')
        } else {
          mensajes.add(issue.message)
        }
      }
      setErrores([...mensajes])
      return
    }

    setErrores([])
    onSubmit({
      ...resultado.data,
      comentarios: resultado.data.comentarios ?? null,
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Registro de actividades"
      className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <fieldset disabled={bloqueado} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="act-fecha" className={CLASE_ETIQUETA}>
              Fecha
            </label>
            <input
              id="act-fecha"
              type="text"
              readOnly
              disabled
              value="Automatizado"
              className={`${CLASE_INPUT} font-medium text-red-600`}
            />
          </div>
          <div>
            <label htmlFor="act-vehiculo" className={CLASE_ETIQUETA}>
              Vehículo
            </label>
            <input
              id="act-vehiculo"
              type="text"
              maxLength={100}
              value={vehiculo}
              onChange={(e) => {
                setVehiculo(e.target.value)
                setErrores([])
              }}
              className={CLASE_INPUT}
            />
          </div>
        </div>

        <div>
          <label htmlFor="act-clientes" className={CLASE_ETIQUETA}>
            Nombre Cliente(s)
          </label>
          <input
            id="act-clientes"
            type="text"
            maxLength={500}
            placeholder={PLACEHOLDER_CLIENTES}
            value={clientes}
            onChange={(e) => {
              setClientes(e.target.value)
              setErrores([])
            }}
            className={CLASE_INPUT}
          />
        </div>

        <div>
          <label htmlFor="act-direcciones" className={CLASE_ETIQUETA}>
            Dirección(es)
          </label>
          <input
            id="act-direcciones"
            type="text"
            maxLength={500}
            placeholder={PLACEHOLDER_DIRECCIONES}
            value={direcciones}
            onChange={(e) => {
              setDirecciones(e.target.value)
              setErrores([])
            }}
            className={CLASE_INPUT}
          />
        </div>

        <div className="space-y-2">
          <p className={CLASE_ETIQUETA}>Actividades Realizadas</p>
          {celdas.map((valor, indice) => (
            <input
              key={indice}
              type="text"
              maxLength={500}
              aria-label={`Actividad realizada ${indice + 1}`}
              value={valor}
              onChange={(e) => {
                setCeldas(
                  celdas.map((c, i) => (i === indice ? e.target.value : c)),
                )
                setErrores([])
              }}
              className={CLASE_INPUT}
            />
          ))}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setCeldas([...celdas, ''])}
              disabled={celdas.length >= MAX_CELDAS}
              className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              + Agregar
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="act-comentarios" className={CLASE_ETIQUETA}>
            Comentarios (opcional)
          </label>
          <textarea
            id="act-comentarios"
            rows={3}
            maxLength={2000}
            value={comentarios}
            onChange={(e) => {
              setComentarios(e.target.value)
              setErrores([])
            }}
            className={CLASE_INPUT}
          />
        </div>
      </fieldset>

      {errores.length > 0 && (
        <div className="space-y-1 rounded-md border border-red-200 bg-red-50 p-3">
          {errores.map((mensaje) => (
            <p key={mensaje} className="text-xs font-medium text-red-600" role="alert">
              {mensaje}
            </p>
          ))}
        </div>
      )}

      <div className="flex justify-end pt-2">
        <button
          type="submit"
          disabled={bloqueado}
          className="rounded-md bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {enviando ? 'Confirmando…' : 'Confirmar'}
        </button>
      </div>
    </form>
  )
}
