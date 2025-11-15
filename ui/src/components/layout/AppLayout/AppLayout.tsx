import type { ReactNode } from 'react'
import { StatusBar } from '../StatusBar'
import styles from './AppLayout.module.css'

export interface AppLayoutProps {
  children: ReactNode
  statusBarProps?: {
    caseNumber?: string
    caseName?: string
    batesNumber?: string
    auditEventCount?: number
    isOnline?: boolean
    indexStatus?: 'ready' | 'building' | 'error'
  }
}

export function AppLayout({ children, statusBarProps }: AppLayoutProps) {
  return (
    <div className={styles.appLayout}>
      <StatusBar {...statusBarProps} />
      <div className={styles.mainContainer}>
        {children}
      </div>
    </div>
  )
}
