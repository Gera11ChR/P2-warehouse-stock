import { useContext } from 'react'
import { NavigationContext } from './navigationContext'
import type { AppNavigate } from './navigationContext'

/** Devuelve la función de navegación o null si no hay provider. */
export function useAppNavigation(): AppNavigate | null {
  return useContext(NavigationContext)
}
