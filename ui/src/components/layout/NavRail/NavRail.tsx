import type { ReactNode } from 'react'
import type { NavigationView } from '@/types'
import styles from './NavRail.module.css'

export interface NavRailProps {
  activeView: NavigationView
  onViewChange: (view: NavigationView) => void
}

export function NavRail({ activeView, onViewChange }: NavRailProps) {
  const navItems: Array<{ view: NavigationView; label: string; icon: ReactNode }> = [
    {
      view: 'search',
      label: 'Search',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" />
          <path d="M12.5 12.5L17 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      )
    },
    {
      view: 'review',
      label: 'Review',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="2" />
          <path d="M7 10L9 12L13 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )
    },
    {
      view: 'policy',
      label: 'Policy',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 2L3 7V13C3 16 10 18 10 18C10 18 17 16 17 13V7L10 2Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        </svg>
      )
    },
    {
      view: 'analytics',
      label: 'Analytics',
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="5" cy="10" r="2" fill="currentColor" />
          <circle cx="10" cy="10" r="2" fill="currentColor" />
          <circle cx="15" cy="10" r="2" fill="currentColor" />
          <path d="M5 10H15" stroke="currentColor" strokeWidth="2" />
        </svg>
      )
    }
  ]

  return (
    <nav className={styles.navRail}>
      <div className={styles.navSection}>
        {navItems.map((item) => (
          <button
            key={item.view}
            className={`${styles.navItem} ${activeView === item.view ? styles.active : ''}`}
            onClick={() => onViewChange(item.view)}
            aria-label={item.label}
            aria-current={activeView === item.view ? 'page' : undefined}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </div>
      <div className={styles.navSection}>
        <button
          className={`${styles.navItem} ${activeView === 'settings' ? styles.active : ''}`}
          onClick={() => onViewChange('settings')}
          aria-label="Settings"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="2" />
            <path d="M10 2V4M10 16V18M18 10H16M4 10H2M15.5 4.5L14 6M6 14L4.5 15.5M15.5 15.5L14 14M6 6L4.5 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span>Settings</span>
        </button>
      </div>
    </nav>
  )
}
