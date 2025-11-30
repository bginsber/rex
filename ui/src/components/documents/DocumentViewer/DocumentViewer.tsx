import type { SearchResult } from '@/types'
import type { HighlightData, Highlight } from '@/types'
import { useEffect, useState, useCallback } from 'react'
import { rexlitApi } from '@/api/rexlit'
import { HighlightOverlay } from './HighlightOverlay'
import { HeatmapBar } from './HeatmapBar'
import { HighlightLegend } from './HighlightLegend'
import { ConceptFilter } from './ConceptFilter'
import styles from './DocumentViewer.module.css'

export interface DocumentViewerProps {
  document: SearchResult | null
  getDocumentUrl: (sha256: string) => string
  showFilters?: boolean
}

export function DocumentViewer({ document, getDocumentUrl, showFilters = true }: DocumentViewerProps) {
  const [highlights, setHighlights] = useState<HighlightData | null>(null)
  const [filteredHighlights, setFilteredHighlights] = useState<Highlight[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const [loadingHighlights, setLoadingHighlights] = useState(false)
  const [selectedHighlight, setSelectedHighlight] = useState<Highlight | null>(null)

  useEffect(() => {
    if (document?.sha256) {
      setLoadingHighlights(true)
      rexlitApi
        .getHighlights(document.sha256)
        .then((data) => {
          setHighlights(data)
          setFilteredHighlights(data?.highlights || [])
        })
        .catch(() => {
          setHighlights(null)
          setFilteredHighlights([])
        })
        .finally(() => setLoadingHighlights(false))
    } else {
      setHighlights(null)
      setFilteredHighlights([])
      setCurrentPage(1)
    }
  }, [document?.sha256])

  const handleFilterChange = useCallback((filtered: Highlight[]) => {
    setFilteredHighlights(filtered)
  }, [])

  const handleHighlightClick = useCallback((highlight: Highlight) => {
    setSelectedHighlight(highlight)
    if (highlight.page) {
      setCurrentPage(highlight.page)
    }
  }, [])

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

  // Build heatmap from filtered highlights
  const filteredHeatmap = highlights?.heatmap?.map(entry => {
    const pageHighlights = filteredHighlights.filter(h => h.page === entry.page)
    const maxTemp = pageHighlights.length > 0
      ? Math.max(...pageHighlights.map(h => h.shade_intensity || 0))
      : 0
    return {
      ...entry,
      temperature: maxTemp,
      highlight_count: pageHighlights.length
    }
  }) || []

  return (
    <div className={styles.viewer}>
      {/* Document Header */}
      <div className={styles.header}>
        <div className={styles.breadcrumb}>
          <h2 className={styles.title}>{documentTitle}</h2>
          <div className={styles.metadata}>
            <span className={`${styles.bates} bates-number`}>{batesNumber}</span>
            <span className={styles.path}>{document.path}</span>
          </div>
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

      {/* Document Content with Sidebar */}
      <div className={styles.contentWrapper}>
        {/* Concept Filter Sidebar */}
        {showFilters && highlights && highlights.highlights.length > 0 && (
          <ConceptFilter
            highlights={highlights.highlights}
            onFilterChange={handleFilterChange}
          />
        )}

        <div className={styles.content}>
          {filteredHeatmap.length > 0 && (
            <HeatmapBar 
              heatmap={filteredHeatmap} 
              currentPage={currentPage} 
              onSelectPage={setCurrentPage} 
            />
          )}

          <div className={styles.documentPane}>
            <iframe
              src={getDocumentUrl(document.sha256)}
              title={`Document: ${document.path}`}
              className={styles.iframe}
              sandbox="allow-same-origin allow-scripts"
              onLoad={(e) => {
                // Detect if iframe loaded JSON error instead of HTML document
                const iframe = e.currentTarget
                setCurrentPage(1)
                try {
                  const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
                  if (iframeDoc) {
                    const text = iframeDoc.body?.textContent || ''
                    if (text.trim().startsWith('{') && text.includes('"error"')) {
                      try {
                        const errorData = JSON.parse(text)
                        if (errorData.error) {
                          iframeDoc.body.innerHTML = `
                            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto;">
                              <div style="background: rgba(255, 107, 107, 0.1); border: 1px solid rgba(255, 107, 107, 0.3); border-radius: 8px; padding: 1.5rem;">
                                <h3 style="margin: 0 0 1rem 0; color: #ff6b6b; font-size: 1.1rem;">⚠️ Document Not Available</h3>
                                <p style="margin: 0 0 1rem 0; color: #e6edf3; line-height: 1.6;">${errorData.error}</p>
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
            {filteredHighlights.length > 0 && (
              <HighlightOverlay
                highlights={filteredHighlights}
                currentPage={currentPage}
                onHighlightClick={handleHighlightClick}
              />
            )}
          </div>
        </div>
      </div>

      {/* Footer with legend and selected highlight info */}
      <div className={styles.footer}>
        {highlights?.color_legend && <HighlightLegend legend={highlights.color_legend} />}
        
        {selectedHighlight && (
          <div className={styles.selectedInfo}>
            <span className={styles.selectedLabel}>Selected:</span>
            <span className={styles.selectedConcept}>
              {selectedHighlight.concept.replace(/_/g, ' ')}
            </span>
            <span className={styles.selectedConfidence}>
              {Math.round(selectedHighlight.confidence * 100)}% confidence
            </span>
          </div>
        )}
      </div>

      {loadingHighlights && (
        <div className={styles.loading}>
          <span className={styles.loadingSpinner} />
          Loading highlights…
        </div>
      )}
    </div>
  )
}
