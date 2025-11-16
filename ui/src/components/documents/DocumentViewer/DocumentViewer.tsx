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

  // Extract document title from path
  const documentTitle = document.path.split('/').pop() || 'Untitled Document'
  const batesNumber = `DOC-${document.sha256.substring(0, 8).toUpperCase()}`

  // Detect if this is a PDF document
  const isPDF = document.mime_type?.startsWith('application/pdf') ?? false

  return (
    <div className={styles.viewer}>
      {/* Document Header */}
      <div className={styles.header}>
        <div className={styles.breadcrumb}>
          <h2 className={styles.title}>{documentTitle}</h2>
          <div className={styles.metadata}>
            <span className={`${styles.bates} bates-number`}>{batesNumber}</span>
            {isPDF && (
              <span
                className={styles.badge}
                title="PDF document"
                style={{
                  display: 'inline-block',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: '600',
                  backgroundColor: 'rgba(200, 50, 50, 0.15)',
                  color: '#ff6b6b',
                  marginRight: '8px'
                }}
              >
                📄 PDF
              </span>
            )}
            <span className={styles.path}>{document.path}</span>
          </div>
        </div>
        <div className={styles.actions}>
          <a
            href={getDocumentUrl(document.sha256)}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.actionButton}
            title={isPDF ? 'Open PDF in new tab' : 'Open document in new tab'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M3 2H10.5C10.776 2 11 2.224 11 2.5V9M13 13V6.5C13 6.224 13.224 6 13.5 6H6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M13 3L6.5 9.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </a>
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
          sandbox="allow-same-origin allow-scripts"
          onLoad={(e) => {
            // Detect if iframe loaded JSON error instead of HTML document
            const iframe = e.currentTarget
            try {
              const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
              if (iframeDoc) {
                const text = iframeDoc.body?.textContent || ''
                // Check if response looks like JSON error
                if (text.trim().startsWith('{') && text.includes('"error"')) {
                  try {
                    const errorData = JSON.parse(text)
                    if (errorData.error) {
                      // Replace iframe content with friendly error message
                      iframeDoc.body.innerHTML = `
                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto;">
                          <div style="background: rgba(255, 107, 107, 0.1); border: 1px solid rgba(255, 107, 107, 0.3); border-radius: 8px; padding: 1.5rem;">
                            <h3 style="margin: 0 0 1rem 0; color: #ff6b6b; font-size: 1.1rem;">⚠️ Document Not Available</h3>
                            <p style="margin: 0 0 1rem 0; color: #e6edf3; line-height: 1.6;">${errorData.error}</p>
                            <details style="margin-top: 1rem; padding: 1rem; background: rgba(0, 0, 0, 0.3); border-radius: 4px; cursor: pointer;">
                              <summary style="font-weight: 600; color: #e8b76a; user-select: none;">Common causes and fixes</summary>
                              <ul style="margin: 1rem 0 0 1.5rem; padding: 0; color: #9ca3af; line-height: 1.8;">
                                <li><strong>Index mismatch:</strong> The search results and document storage are in different REXLIT_HOME locations. Check that the API server's REXLIT_HOME matches where documents were indexed.</li>
                                <li><strong>Stale index:</strong> The document may have been removed after indexing. Try rebuilding the index with <code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 3px; color: #e8b76a;">rexlit index build</code></li>
                                <li><strong>Document moved/deleted:</strong> The file may no longer exist at the expected path.</li>
                              </ul>
                            </details>
                          </div>
                        </div>
                      `
                    }
                  } catch {
                    // Not JSON, ignore
                  }
                }
              }
            } catch {
              // Cross-origin or other access issue, ignore
            }
          }}
        />
      </div>
    </div>
  )
}
