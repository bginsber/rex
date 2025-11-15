import { useEffect, useState } from 'react'
import { rexlitApi } from '@/api/rexlit'
import styles from './AnalyticsView.module.css'

export function AnalyticsView() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    rexlitApi
      .stats()
      .then(setStats)
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load analytics')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const documentCount =
    typeof stats?.doc_count === 'number' ? stats.doc_count : stats?.doc_count ?? '—'
  const custodians = Array.isArray(stats?.custodians)
    ? stats?.custodians.length
    : stats?.custodians ?? '—'

  return (
    <section className={styles.analyticsView}>
      <header className={styles.header}>
        <div>
          <h2>Analytics</h2>
          <p className={styles.subtitle}>Source corpus telemetry and ingestion status.</p>
        </div>
      </header>

      {error && <div className={`${styles.alert} ${styles.error}`}>{error}</div>}

      <div className={styles.statGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Documents</span>
          <span className={styles.statValue}>{String(documentCount)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Custodians</span>
          <span className={styles.statValue}>{String(custodians)}</span>
        </div>
      </div>

      <div className={styles.dataPanel}>
        <div className={styles.dataHeader}>
          <h3>Raw stats payload</h3>
          {loading && <span className={styles.tag}>Refreshing…</span>}
        </div>
        <pre>{JSON.stringify(stats ?? {}, null, 2)}</pre>
      </div>
    </section>
  )
}
