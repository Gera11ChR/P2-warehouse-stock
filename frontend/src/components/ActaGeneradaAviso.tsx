import { FileSpreadsheet, X } from 'lucide-react'
import type { ActaTipo } from '../types'

// ============================================================================
// AVISO DE ACTA GENERADA (confirmation_report_generation.png)
//
// Presentacional. Se muestra DESPUÉS de que el servidor aceptó la operación
// (TEAMS CONFIRMADO → Acta de Entrega, REQ-P2-REP-003; cierre de seguimiento
// → Acta de Consumo, REQ-P2-CON-005). Nunca se muestra por predicción: el
// padre debe montarlo solo en el `onSuccess` de la mutación.
//
// Es persistente (a diferencia del toast de 4 s) porque ofrece una acción:
// ir a Reportes (subsección correspondiente, pre-filtrada por equipo) donde
// se exporta el XLSX. Si no hay navegación disponible la acción se oculta.
// ============================================================================

export interface ActaGeneradaAvisoProps {
  tipo: ActaTipo
  /** Nombre del equipo implicado (contexto operativo; evita confundir equipo). */
  equipoNombre?: string | null
  /** Ir a Reportes > Entrega|Consumo. Sin handler no se muestra la acción. */
  onVerActa?: () => void
  onDismiss: () => void
}

const COPY: Record<
  ActaTipo,
  { titulo: string; detalle: (equipo: string) => string; accion: string }
> = {
  ENTREGA: {
    titulo: 'Acta de Entrega generada',
    detalle: (equipo) =>
      `El movimiento TEAMS${equipo} fue CONFIRMADO por el servidor y su Acta de Entrega quedó registrada. Puedes exportarla en Reportes > Entrega.`,
    accion: 'Ir a Reportes > Entrega',
  },
  CONSUMO: {
    titulo: 'Acta de Consumo generada',
    detalle: (equipo) =>
      `El seguimiento${equipo} fue cerrado por el servidor y su Acta de Consumo quedó registrada. Puedes exportarla en Reportes > Consumo.`,
    accion: 'Ir a Reportes > Consumo',
  },
}

export default function ActaGeneradaAviso({
  tipo,
  equipoNombre,
  onVerActa,
  onDismiss,
}: ActaGeneradaAvisoProps) {
  const copy = COPY[tipo]
  const equipo = equipoNombre
    ? tipo === 'ENTREGA'
      ? ` hacia ${equipoNombre}`
      : ` del equipo ${equipoNombre}`
    : ''
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4"
    >
      <FileSpreadsheet
        className="mt-0.5 h-5 w-5 shrink-0 text-green-700"
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-green-900">{copy.titulo}</p>
        <p className="mt-1 text-sm text-green-800">{copy.detalle(equipo)}</p>
        {onVerActa && (
          <button
            type="button"
            onClick={onVerActa}
            className="mt-2 rounded-md bg-green-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-800"
          >
            {copy.accion}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={`Cerrar aviso de ${copy.titulo}`}
        className="rounded p-1 text-green-700 hover:bg-green-100"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}
