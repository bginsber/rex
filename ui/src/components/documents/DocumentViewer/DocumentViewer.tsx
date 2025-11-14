import type { SearchResult } from '@/types'
import styles from './DocumentViewer.module.css'

export interface DocumentViewerProps {
  document: SearchResult | null
  getDocumentUrl: (sha256: string) => string
}

export function DocumentViewer({ document, getDocumentUrl }: DocumentViewerProps) {
  if (!document) {
    return (
      <div className={styles.viewer}>
        <div className={styles.empty}>
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <rect x="16" y="8" width="32" height="48" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M24 20H40M24 28H40M24 36H32" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <p>Select a document to view</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.viewer}>
      {/* Document Header */}
      <div className={styles.header}>
        <div className={styles.breadcrumb}>
          <span className={styles.path}>{document.path}</span>
        </div>
        <div className={styles.actions}>
          <button className={styles.actionButton} title="Download">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2V10M8 10L5 7M8 10L11 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 12V13C2 13.5 2.5 14 3 14H13C13.5 14 14 13.5 14 13V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Document Content */}
      <div className={styles.content}>
        <iframe
          src={getDocumentUrl(document.sha256)}
          title={`Document: ${document.path}`}
          className={styles.iframe}
        />
      </div>
    </div>
  )
}
