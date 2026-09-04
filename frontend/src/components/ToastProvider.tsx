import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ToastContext } from '../hooks/toastContext'
import type { ToastVariant } from '../hooks/toastContext'
import ToastContainer from './ToastContainer'

interface Toast {
  id: number
  message: string
  variant: ToastVariant
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const removeToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback((message: string, variant: ToastVariant) => {
    const id = Date.now() + Math.random()
    setToasts((current) => [...current, { id, message, variant }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 4000)
  }, [])

  const pushToast = useCallback((message: string) => push(message, 'success'), [push])
  const pushError = useCallback((message: string) => push(message, 'error'), [push])

  const value = useMemo(() => ({ pushToast, pushError }), [pushToast, pushError])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  )
}
