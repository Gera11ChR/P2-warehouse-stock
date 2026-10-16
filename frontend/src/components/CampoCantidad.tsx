import type { KeyboardEvent, Ref } from 'react'

// ============================================================================
// CAMPO DE CANTIDAD DECIMAL (compartido por +Cantidad, Mover y ajustes; RF-6)
//
// Campo de texto con `inputMode="decimal"` (NO `type="number"`): así el valor
// crudo llega intacto y se pueden rechazar con mensaje propio el texto, la
// notación científica, el exceso de decimales (> 3, sin redondeo silencioso),
// los negativos y los espacios (un `type="number"` los sanea en silencio). La validación vive en
// utils/cantidad.ts; este componente solo presenta el estado.
//
// Accesibilidad: label asociado, `aria-invalid`, `aria-describedby` apuntando
// al texto de ayuda/error (el mismo nodo cambia de contenido).
// ============================================================================

export interface CampoCantidadProps {
  id: string
  label: string
  value: string
  onChange: (valor: string) => void
  onBlur?: () => void
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void
  /** Mensaje de error en línea (null = campo sin error visible). */
  error: string | null
  /** Texto de ayuda mientras no haya error. */
  ayuda: string
  disabled?: boolean
  inputRef?: Ref<HTMLInputElement>
}

export default function CampoCantidad({
  id,
  label,
  value,
  onChange,
  onBlur,
  onKeyDown,
  error,
  ayuda,
  disabled = false,
  inputRef,
}: CampoCantidadProps) {
  const ayudaId = `${id}-ayuda`
  return (
    <div>
      <label
        htmlFor={id}
        className="text-xs font-semibold uppercase tracking-wide text-slate-400"
      >
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
        aria-invalid={error !== null}
        aria-describedby={ayudaId}
        disabled={disabled}
        className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
          error ? 'border-red-400' : 'border-slate-300'
        }`}
      />
      <p
        id={ayudaId}
        className={`mt-1 text-xs ${
          error ? 'font-medium text-red-600' : 'text-slate-500'
        }`}
      >
        {error ?? ayuda}
      </p>
    </div>
  )
}
