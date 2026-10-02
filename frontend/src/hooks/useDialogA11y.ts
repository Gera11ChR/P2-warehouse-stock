import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'

// ============================================================================
// Accesibilidad de diálogos modales (foco + teclado)
//
//  - Al abrir: guarda el elemento enfocado, mueve el foco al control inicial
//    (`initialFocusRef`) o al primer elemento enfocable del diálogo.
//  - Tab / Shift+Tab: foco atrapado dentro del contenedor.
//  - Esc: cierra (salvo `closeDisabled`, p. ej. con una operación en vuelo:
//    cerrar a medias dejaría al operador sin saber si fue aceptada).
//  - Al cerrar/desmontar: devuelve el foco al elemento que abrió el diálogo.
// ============================================================================

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface UseDialogA11yOptions {
  open: boolean
  onClose: () => void
  containerRef: RefObject<HTMLElement | null>
  initialFocusRef?: RefObject<HTMLElement | null>
  closeDisabled?: boolean
}

export function useDialogA11y({
  open,
  onClose,
  containerRef,
  initialFocusRef,
  closeDisabled = false,
}: UseDialogA11yOptions) {
  // Últimos valores sin re-ejecutar el efecto (evita re-enfocar en cada render).
  const onCloseRef = useRef(onClose)
  const closeDisabledRef = useRef(closeDisabled)
  useEffect(() => {
    onCloseRef.current = onClose
    closeDisabledRef.current = closeDisabled
  })

  useEffect(() => {
    if (!open) return
    const previo = document.activeElement as HTMLElement | null
    const contenedor = containerRef.current

    const enfocables = (): HTMLElement[] =>
      contenedor
        ? Array.from(contenedor.querySelectorAll<HTMLElement>(FOCUSABLE))
        : []

    const inicial = initialFocusRef?.current ?? enfocables()[0] ?? contenedor
    inicial?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (!closeDisabledRef.current) {
          event.stopPropagation()
          onCloseRef.current()
        }
        return
      }
      if (event.key !== 'Tab') return
      const items = enfocables()
      if (items.length === 0) {
        event.preventDefault()
        contenedor?.focus()
        return
      }
      const primero = items[0]
      const ultimo = items[items.length - 1]
      const activo = document.activeElement
      if (event.shiftKey && (activo === primero || activo === contenedor)) {
        event.preventDefault()
        ultimo.focus()
      } else if (!event.shiftKey && activo === ultimo) {
        event.preventDefault()
        primero.focus()
      } else if (contenedor && !contenedor.contains(activo)) {
        event.preventDefault()
        primero.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (previo && document.contains(previo)) previo.focus()
    }
  }, [open, containerRef, initialFocusRef])
}
