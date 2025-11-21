import type { Highlight } from '@/types'
import styles from './DocumentViewer.module.css'

interface HighlightOverlayProps {
  highlights: Highlight[]
  currentPage: number
}

export function HighlightOverlay({ highlights, currentPage }: HighlightOverlayProps) {
  const pageHighlights = highlights.filter((h) => h.page === currentPage)
  const maxEnd = pageHighlights.reduce((max, h) => Math.max(max, h.end), 1)

  return (
    <div className={styles.highlightOverlay}>
      {pageHighlights.map((h, idx) => {
        const top = (h.start / maxEnd) * 100
        const height = Math.max(((h.end - h.start) / maxEnd) * 100, 1)
        return (
          <span
            key={`${h.concept}-${idx}`}
            className={styles.highlight}
            style={{
              backgroundColor: h.color,
              opacity: h.shade_intensity,
              top: `${top}%`,
              height: `${height}%`
            }}
            title={`${h.concept} (${Math.round(h.confidence * 100)}%)`}
          />
        )
      })}
    </div>
  )
}
