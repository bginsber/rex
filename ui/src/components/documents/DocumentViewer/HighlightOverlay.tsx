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
        const boxes = (h as any).boxes as
          | Array<{ page: number; x0: number; y0: number; x1: number; y1: number }>
          | undefined
        if (boxes && boxes.length) {
          return boxes
            .filter((box) => box.page === currentPage)
            .map((box, boxIdx) => (
            <span
              key={`${h.concept}-${idx}-box-${boxIdx}`}
              className={styles.highlight}
              style={{
                backgroundColor: h.color,
                opacity: h.shade_intensity,
                left: `${box.x0 * 100}%`,
                top: `${box.y0 * 100}%`,
                width: `${Math.max((box.x1 - box.x0) * 100, 1)}%`,
                height: `${Math.max((box.y1 - box.y0) * 100, 1)}%`
              }}
              title={`${h.concept} (${Math.round(h.confidence * 100)}%)`}
            />
          ))
        }
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
