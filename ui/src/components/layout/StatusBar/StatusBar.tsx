import { StatusIndicator } from '@/components/common/StatusIndicator'
import styles from './StatusBar.module.css'

export interface StatusBarProps {
  caseNumber?: string
  caseName?: string
  batesNumber?: string
  auditEventCount?: number
  isOnline?: boolean
  indexStatus?: 'ready' | 'building' | 'error'
}

export function StatusBar({
  caseNumber = 'CASE-2024-CV-1847',
  caseName = 'Martinez v. Apex Corp.',
  batesNumber = 'APEX-00428391',
  auditEventCount = 0,
  isOnline = false,
  indexStatus = 'ready'
}: StatusBarProps) {
  const indexStatusMap = {
    ready: 'active' as const,
    building: 'warning' as const,
    error: 'error' as const
  }

  const indexStatusLabel = {
    ready: 'INDEX: READY',
    building: 'INDEX: BUILDING',
    error: 'INDEX: ERROR'
  }

  return (
    <div className={styles.statusBar}>
      {/* Left Section - System Status */}
      <div className={styles.section}>
        <StatusIndicator
          status={isOnline ? 'active' : 'inactive'}
          label={isOnline ? 'ONLINE MODE' : 'OFFLINE MODE'}
        />
        <StatusIndicator
          status={indexStatusMap[indexStatus]}
          label={indexStatusLabel[indexStatus]}
          pulse={indexStatus === 'building'}
        />
      </div>

      {/* Center Section - Case Information */}
      <div className={`${styles.section} ${styles.center}`}>
        <div className={styles.caseBadge}>
          <span className={styles.caseNumber}>{caseNumber}</span>
          <span className={styles.caseName}>{caseName}</span>
        </div>
      </div>

      {/* Right Section - Audit & Bates */}
      <div className={styles.section}>
        <div className={styles.auditChain}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M3 8L8 3L13 8M8 3V13"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <span className={styles.chainCount}>
            {auditEventCount.toLocaleString()} events
          </span>
        </div>
        <div className={styles.batesCounter}>
          <span className="mono">{batesNumber}</span>
        </div>
      </div>
    </div>
  )
}
