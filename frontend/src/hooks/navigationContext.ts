import { createContext } from 'react'
import type { NavigationTarget } from '../types'

/**
 * Navegación entre páginas de la app (estado de ruta de MainLayout).
 * Es OPCIONAL: fuera del provider el valor es null y las acciones de
 * "ir a" deben ocultarse (nunca mostrar un botón muerto).
 */
export type AppNavigate = (target: NavigationTarget) => void

export const NavigationContext = createContext<AppNavigate | null>(null)
