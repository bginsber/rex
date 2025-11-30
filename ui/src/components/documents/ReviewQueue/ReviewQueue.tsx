import { useState, useEffect, useCallback } from 'react'
import type { Highlight } from '@/types'
import { rexlitApi } from '@/api/rexlit'
import styles from './ReviewQueue.module.css'

interface DocumentWithUncertainHighlights {
  sha256: string
  path: string
  uncertainHighlights: Highlight[]
  totalHighlights: number
}

interface ReviewDecision {
  highlightId: string
  decision: 'accept' | 'reject' | 'skip'
  documentSha256: string
}

interface ReviewQueueProps {
  onSelectDocument?: (sha256: string) => void
  minConfidence?: number
  maxConfidence?: number
}

export function ReviewQueue({
  onSelectDocument,
  minConfidence = 0.5,
  maxConfidence = 0.75,
}: ReviewQueueProps) {
  const [documents, setDocuments] = useState<DocumentWithUncertainHighlights[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Map<string, ReviewDecision>>(new Map())
  const [currentDocIndex, setCurrentDocIndex] = useState(0)
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(0)

  // Load documents with uncertain highlights
  useEffect(() => {
    async function loadDocuments() {
      try {
        setLoading(true)
        setError(null)

        // Get list of documents from search
        const searchResults = await rexlitApi.search({ query: '*', limit: 100 })

        // Load highlights for each document and filter for uncertain ones
        const docsWithUncertain: DocumentWithUncertainHighlights[] = []

        for (const result of searchResults) {
          try {
            const highlights = await rexlitApi.getHighlights(result.sha256)
            if (!highlights?.highlights?.length) continue

            const uncertain = highlights.highlights.filter(
              (h) => h.confidence >= minConfidence && h.confidence <= maxConfidence
            )

            if (uncertain.length > 0) {
              docsWithUncertain.push({
                sha256: result.sha256,
                path: result.path,
                uncertainHighlights: uncertain,
                totalHighlights: highlights.highlights.length,
              })
            }
          } catch {
            // Skip documents that fail to load highlights
          }
        }

        setDocuments(docsWithUncertain)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load review queue')
      } finally {
        setLoading(false)
      }
    }

    loadDocuments()
  }, [minConfidence, maxConfidence])

  const currentDoc = documents[currentDocIndex]
  const currentHighlight = currentDoc?.uncertainHighlights[currentHighlightIndex]

  const makeDecision = useCallback(
    (decision: 'accept' | 'reject' | 'skip') => {
      if (!currentHighlight || !currentDoc) return

      const highlightId = `${currentDoc.sha256}-${currentHighlight.page}-${currentHighlight.start}`

      setDecisions((prev) => {
        const next = new Map(prev)
        next.set(highlightId, {
          highlightId,
          decision,
          documentSha256: currentDoc.sha256,
        })
        return next
      })

      // Move to next highlight or document
      if (currentHighlightIndex < currentDoc.uncertainHighlights.length - 1) {
        setCurrentHighlightIndex((i) => i + 1)
      } else if (currentDocIndex < documents.length - 1) {
        setCurrentDocIndex((i) => i + 1)
        setCurrentHighlightIndex(0)
      }
    },
    [currentDoc, currentHighlight, currentHighlightIndex, currentDocIndex, documents.length]
  )

  const goToPrevious = useCallback(() => {
    if (currentHighlightIndex > 0) {
      setCurrentHighlightIndex((i) => i - 1)
    } else if (currentDocIndex > 0) {
      const prevDoc = documents[currentDocIndex - 1]
      setCurrentDocIndex((i) => i - 1)
      setCurrentHighlightIndex(prevDoc.uncertainHighlights.length - 1)
    }
  }, [currentHighlightIndex, currentDocIndex, documents])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'a':
        case 'A':
          makeDecision('accept')
          break
        case 'r':
        case 'R':
          makeDecision('reject')
          break
        case 's':
        case 'S':
        case ' ':
          e.preventDefault()
          makeDecision('skip')
          break
        case 'ArrowLeft':
          goToPrevious()
          break
        case 'ArrowRight':
          makeDecision('skip')
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [makeDecision, goToPrevious])

  // Calculate progress stats
  const totalUncertain = documents.reduce((sum, d) => sum + d.uncertainHighlights.length, 0)
  const reviewedCount = decisions.size
  const currentPosition =
    documents
      .slice(0, currentDocIndex)
      .reduce((sum, d) => sum + d.uncertainHighlights.length, 0) +
    currentHighlightIndex +
    1

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <span className={styles.spinner} />
          Loading review queue...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <h3>Error loading review queue</h3>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <circle cx="32" cy="32" r="24" stroke="currentColor" strokeWidth="2" />
            <path d="M22 32L30 40L42 24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h3>No uncertain highlights</h3>
          <p>All highlights have high confidence ({Math.round(maxConfidence * 100)}%+) or low confidence (&lt;{Math.round(minConfidence * 100)}%).</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      {/* Header with progress */}
      <header className={styles.header}>
        <div className={styles.title}>
          <h2>Highlight Review Queue</h2>
          <span className={styles.subtitle}>
            {totalUncertain} uncertain highlights across {documents.length} documents
          </span>
        </div>
        <div className={styles.progress}>
          <div className={styles.progressBar}>
            <div
              className={styles.progressFill}
              style={{ width: `${(reviewedCount / totalUncertain) * 100}%` }}
            />
          </div>
          <span className={styles.progressText}>
            {reviewedCount}/{totalUncertain} reviewed
          </span>
        </div>
      </header>

      {/* Current item */}
      {currentDoc && currentHighlight && (
        <div className={styles.reviewCard}>
          <div className={styles.cardHeader}>
            <span className={styles.position}>
              Item {currentPosition} of {totalUncertain}
            </span>
            <button
              className={styles.viewDocButton}
              onClick={() => onSelectDocument?.(currentDoc.sha256)}
            >
              View full document →
            </button>
          </div>

          <div className={styles.documentInfo}>
            <span className={styles.documentPath}>{currentDoc.path}</span>
            <span className={styles.highlightMeta}>
              Page {currentHighlight.page} • {currentHighlight.concept.replace(/_/g, ' ')}
            </span>
          </div>

          <div className={styles.highlightPreview}>
            <span
              className={styles.confidenceBadge}
              style={{
                backgroundColor: getConfidenceColor(currentHighlight.confidence),
              }}
            >
              {Math.round(currentHighlight.confidence * 100)}% confidence
            </span>
            <span className={styles.categoryBadge}>
              {currentHighlight.category}
            </span>
          </div>

          <div className={styles.decisionButtons}>
            <button
              className={`${styles.decisionButton} ${styles.accept}`}
              onClick={() => makeDecision('accept')}
            >
              <span className={styles.buttonKey}>A</span>
              Accept
            </button>
            <button
              className={`${styles.decisionButton} ${styles.reject}`}
              onClick={() => makeDecision('reject')}
            >
              <span className={styles.buttonKey}>R</span>
              Reject
            </button>
            <button
              className={`${styles.decisionButton} ${styles.skip}`}
              onClick={() => makeDecision('skip')}
            >
              <span className={styles.buttonKey}>S</span>
              Skip
            </button>
          </div>

          <div className={styles.navigation}>
            <button
              className={styles.navButton}
              onClick={goToPrevious}
              disabled={currentDocIndex === 0 && currentHighlightIndex === 0}
            >
              ← Previous
            </button>
            <span className={styles.shortcuts}>
              Keyboard: A/R/S or ←/→
            </span>
          </div>
        </div>
      )}

      {/* Summary stats */}
      <div className={styles.stats}>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {Array.from(decisions.values()).filter((d) => d.decision === 'accept').length}
          </span>
          <span className={styles.statLabel}>Accepted</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {Array.from(decisions.values()).filter((d) => d.decision === 'reject').length}
          </span>
          <span className={styles.statLabel}>Rejected</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {Array.from(decisions.values()).filter((d) => d.decision === 'skip').length}
          </span>
          <span className={styles.statLabel}>Skipped</span>
        </div>
      </div>
    </div>
  )
}

function getConfidenceColor(confidence: number): string {
  // Gradient from yellow (uncertain) to orange (more uncertain)
  const hue = 45 - (confidence - 0.5) * 90 // 45 (yellow) to 0 (red)
  return `hsl(${hue}, 80%, 50%)`
}

