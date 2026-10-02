import type { KeyboardEvent, ReactNode } from 'react'

// ============================================================================
// TABS — componente presentacional reutilizable (patrón WAI-ARIA tablist)
//
// Sin estado propio: el contenedor controla `value` y pasa como `children` el
// contenido del panel activo (se envuelve en un tabpanel enlazado por a11y).
// Visual alineado con las pestañas existentes (azul activo / borde claro).
// ============================================================================

export interface TabItem<T extends string> {
  value: T
  label: string
}

interface TabsProps<T extends string> {
  tabs: readonly TabItem<T>[]
  value: T
  onChange: (value: T) => void
  /** Prefijo único para los ids de pestañas y paneles. */
  idPrefix: string
  ariaLabel: string
  /** Contenido del panel de la pestaña activa. */
  children: ReactNode
}

const tabId = (idPrefix: string, value: string) => `${idPrefix}-tab-${value}`
const panelId = (idPrefix: string, value: string) =>
  `${idPrefix}-panel-${value}`

export default function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  idPrefix,
  ariaLabel,
  children,
}: TabsProps<T>) {
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = tabs.findIndex((t) => t.value === value)
    let next: number
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length
    else if (event.key === 'ArrowLeft')
      next = (index - 1 + tabs.length) % tabs.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = tabs.length - 1
    else return
    event.preventDefault()
    onChange(tabs[next].value)
    document.getElementById(tabId(idPrefix, tabs[next].value))?.focus()
  }

  return (
    <>
      <div
        role="tablist"
        aria-label={ariaLabel}
        className="flex flex-wrap gap-2"
      >
        {tabs.map(({ value: tabValue, label }) => {
          const selected = tabValue === value
          return (
            <button
              key={tabValue}
              id={tabId(idPrefix, tabValue)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId(idPrefix, tabValue)}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tabValue)}
              onKeyDown={handleKeyDown}
              className={`rounded-md px-4 py-2 text-sm font-medium ${
                selected
                  ? 'bg-blue-600 text-white'
                  : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>
      <div
        role="tabpanel"
        id={panelId(idPrefix, value)}
        aria-labelledby={tabId(idPrefix, value)}
      >
        {children}
      </div>
    </>
  )
}
