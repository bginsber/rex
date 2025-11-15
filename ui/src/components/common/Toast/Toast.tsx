import { useEffect } from 'react'
import type { Toast as ToastType } from '@/types'
import styles from './Toast.module.css'

export interface ToastProps {
  toast: ToastType
  onDismiss: (id: string) => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  useEffect(() => {
    const duration = toast.duration ?? 2000
    const timer = setTimeout(() => {
      onDismiss(toast.id)
    }, duration)

    return () => clearTimeout(timer)
  }, [toast.id, toast.duration, onDismiss])

  return (
    <div className={`${styles.toast} ${styles[toast.type ?? 'info']} toast-enter`} role="alert">
      {toast.message}
    </div>
  )
}
