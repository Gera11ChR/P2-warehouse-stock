// ============================================================================
// FORMATO DE IMPORTES EN MXN (RF-3, RF-5; C-7) — solo PRESENTACIÓN.
//
// Locale `es-MX`, mínimo 2 y máximo 3 decimales (p. ej. `1.00`, `12.345`).
// La etiqueta `MXN` se renderiza a la derecha de la cifra (componente
// `MonedaMxn`/KpiCards); aquí solo se formatea el número. El cálculo del
// Valor Total vive en PostgreSQL: este módulo nunca suma ni multiplica.
// ============================================================================

const FORMATO = new Intl.NumberFormat('es-MX', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
})

/** `1` → `1.00`; `12.345` → `12.345`; `1234.5` → `1,234.50`. */
export function formatMxn(valor: number): string {
  return FORMATO.format(valor)
}

/** Cifra + etiqueta `MXN` a la derecha (`1.00 MXN`). */
export function formatMxnConMoneda(valor: number, moneda: string = 'MXN'): string {
  return `${formatMxn(valor)} ${moneda}`
}
