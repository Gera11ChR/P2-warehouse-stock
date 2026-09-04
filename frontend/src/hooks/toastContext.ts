import { createContext } from 'react'

export type ToastVariant = 'success' | 'error'

export interface ToastContextValue {
  pushToast: (message: string) => void
  pushError: (message: string) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)
