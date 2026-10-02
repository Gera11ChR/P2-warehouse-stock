import { Download, Loader2 } from 'lucide-react'

// ============================================================================
// BOTONES DE EXPORTACIÓN XLSX — presentacional (REQ-P2-REP-005)
//
// Sin lógica de red: recibe los handlers por props. Un botón sin handler
// queda deshabilitado (la integración la aporta la capa de estado).
// `loadingFormato` indica cuál exportación está en curso; mientras tanto
// ambos botones se bloquean para evitar dobles descargas.
// ============================================================================

export type FormatoExportacion = 'normal' | 'extenso'

export interface ReporteExportButtonsProps {
  onExportNormal?: () => void
  onExportExtenso?: () => void
  /** Deshabilita ambos botones (p. ej. mientras carga el listado). */
  disabled?: boolean
  /** Formato cuya exportación está en curso (muestra spinner). */
  loadingFormato?: FormatoExportacion | null
  /** id del texto que explica por qué están deshabilitados (aria-describedby). */
  describedBy?: string
}

const BOTON =
  'flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50'

export default function ReporteExportButtons({
  onExportNormal,
  onExportExtenso,
  disabled = false,
  loadingFormato = null,
  describedBy,
}: ReporteExportButtonsProps) {
  const ocupado = loadingFormato !== null
  const icono = (formato: FormatoExportacion) =>
    loadingFormato === formato ? (
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
    ) : (
      <Download className="h-4 w-4" aria-hidden="true" />
    )

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onExportNormal}
        disabled={disabled || ocupado || !onExportNormal}
        aria-busy={loadingFormato === 'normal'}
        aria-describedby={describedBy}
        className={`${BOTON} bg-blue-600 hover:bg-blue-700`}
      >
        {icono('normal')} Exportar XLSX (Normal)
      </button>
      <button
        type="button"
        onClick={onExportExtenso}
        disabled={disabled || ocupado || !onExportExtenso}
        aria-busy={loadingFormato === 'extenso'}
        aria-describedby={describedBy}
        className={`${BOTON} bg-slate-700 hover:bg-slate-800`}
      >
        {icono('extenso')} Exportar XLSX (Extenso)
      </button>
    </div>
  )
}
