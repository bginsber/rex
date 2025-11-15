import type { SearchResult } from '@/types'
import styles from './DocumentCard.module.css'

export interface DocumentCardProps {
  document: SearchResult
  isActive?: boolean
  onClick?: () => void
}

export function DocumentCard({ document, isActive = false, onClick }: DocumentCardProps) {
  // Generate Bates-style number from hash (first 8 chars)
  const batesNumber = `DOC-${document.sha256.substring(0, 8).toUpperCase()}`

  // Truncate snippet for display
  const displaySnippet = document.snippet
    ? document.snippet.length > 150
      ? document.snippet.substring(0, 150) + '...'
      : document.snippet
    : 'No preview available'

  return (
    <div
      className={`${styles.card} ${isActive ? styles.active : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
    >
      {/* Bates Tag */}
      <div className={styles.batesTag}>
        <span className="mono">{batesNumber}</span>
      </div>

      {/* Document Info */}
      <div className={styles.content}>
        <div className={styles.header}>
          <h3 className={styles.title}>{document.path.split('/').pop() || document.path}</h3>
          <div className={styles.score}>
            {(document.score * 100).toFixed(0)}%
          </div>
        </div>

        {/* Metadata */}
        <div className={styles.metadata}>
          {document.custodian && (
            <span className={styles.tag}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 6C7.1 6 8 5.1 8 4C8 2.9 7.1 2 6 2C4.9 2 4 2.9 4 4C4 5.1 4.9 6 6 6ZM6 7C4.3 7 1 7.9 1 9.5V10H11V9.5C11 7.9 7.7 7 6 7Z" fill="currentColor"/>
              </svg>
              {document.custodian}
            </span>
          )}
          {document.doctype && (
            <span className={styles.tag}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 2H9V10H3V2ZM4 4H8M4 6H8M4 8H7" stroke="currentColor" strokeWidth="1"/>
              </svg>
              {document.doctype}
            </span>
          )}
        </div>

        {/* Snippet */}
        <p className={styles.snippet}>{displaySnippet}</p>

        {/* Strategy indicator */}
        {document.strategy && (
          <div className={styles.strategy}>
            <span className="mono">{document.strategy}</span>
          </div>
        )}
      </div>
    </div>
  )
}
