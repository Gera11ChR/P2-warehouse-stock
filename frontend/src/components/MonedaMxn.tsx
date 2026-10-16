import { formatMxn } from '../utils/formatMxn'

// ============================================================================
// IMPORTE EN MXN (RF-3, RF-5) — componente de PRESENTACIÓN único.
//
// Cifra a la izquierda y etiqueta `MXN` a su derecha (p. ej. `1.00 MXN`;
// es-MX, mínimo 2 y máximo 3 decimales). Solo formatea el número que entrega
// la API: jamás suma ni multiplica.
// ============================================================================

interface MonedaMxnProps {
  valor: number
  className?: string
}

export default function MonedaMxn({ valor, className = '' }: MonedaMxnProps) {
  return (
    <span className={`whitespace-nowrap tabular-nums ${className}`.trim()}>
      {formatMxn(valor)}{' '}
      <span className="text-xs font-semibold text-slate-400">MXN</span>
    </span>
  )
}
