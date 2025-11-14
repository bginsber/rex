import styles from './StatusIndicator.module.css'

export interface StatusIndicatorProps {
  status: 'active' | 'inactive' | 'warning' | 'error'
  label?: string
  pulse?: boolean
  className?: string
}

export function StatusIndicator({ status, label, pulse = false, className = '' }: StatusIndicatorProps) {
  const dotClass = `${styles.dot} ${styles[status]} ${pulse ? 'status-pulse' : ''}`

  return (
    <div className={`${styles.indicator} ${className}`}>
      <span className={dotClass} aria-label={`Status: ${status}`} />
      {label && <span className={styles.label}>{label}</span>}
    </div>
  )
}
