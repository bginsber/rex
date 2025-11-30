import { useState } from 'react'
import type { Highlight } from '@/types'
import styles from './DocumentViewer.module.css'

interface HighlightBox {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
}

interface HighlightOverlayProps {
  highlights: Highlight[]
  currentPage: number
  onHighlightClick?: (highlight: Highlight) => void
}

// Map category to accessible color with better contrast
const CATEGORY_COLORS: Record<string, string> = {
  communication: 'rgba(0, 180, 216, 0.35)', // Cyan
  privilege: 'rgba(186, 85, 211, 0.35)', // Purple (more distinguishable than magenta)
  entity: 'rgba(255, 193, 7, 0.35)', // Amber
  hotdoc: 'rgba(239, 68, 68, 0.45)', // Red - higher opacity for critical items
  responsive: 'rgba(34, 197, 94, 0.35)', // Green
}

// Hover colors with increased opacity
const CATEGORY_HOVER_COLORS: Record<string, string> = {
  communication: 'rgba(0, 180, 216, 0.55)',
  privilege: 'rgba(186, 85, 211, 0.55)',
  entity: 'rgba(255, 193, 7, 0.55)',
  hotdoc: 'rgba(239, 68, 68, 0.65)',
  responsive: 'rgba(34, 197, 94, 0.55)',
}

function getHighlightColor(category: string, intensity: number, isHovered: boolean): string {
  const baseColor = isHovered
    ? CATEGORY_HOVER_COLORS[category] || 'rgba(255, 193, 7, 0.55)'
    : CATEGORY_COLORS[category] || 'rgba(255, 193, 7, 0.35)'
  
  // Parse rgba and adjust opacity based on intensity
  const match = baseColor.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/)
  if (match) {
    const [, r, g, b, baseOpacity] = match
    const adjustedOpacity = parseFloat(baseOpacity) * Math.max(0.5, intensity)
    return `rgba(${r}, ${g}, ${b}, ${adjustedOpacity.toFixed(2)})`
  }
  return baseColor
}

export function HighlightOverlay({ highlights, currentPage, onHighlightClick }: HighlightOverlayProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const pageHighlights = highlights.filter((h) => h.page === currentPage)
  const maxEnd = pageHighlights.reduce((max, h) => Math.max(max, h.end), 1)

  const renderHighlight = (h: Highlight, idx: number) => {
    const boxes = (h as any).boxes as HighlightBox[] | undefined
    const highlightId = `${h.concept}-${h.page}-${h.start}-${idx}`
    const isHovered = hoveredId === highlightId

    // If we have precise bounding boxes from layout sidecars, use them
    if (boxes && boxes.length > 0) {
      const pageBoxes = boxes.filter((box) => box.page === currentPage)
      if (pageBoxes.length === 0) return null

      return pageBoxes.map((box, boxIdx) => (
        <span
          key={`${highlightId}-box-${boxIdx}`}
          className={`${styles.highlight} ${styles.highlightPrecise}`}
          style={{
            backgroundColor: getHighlightColor(h.category, h.shade_intensity, isHovered),
            left: `${box.x0 * 100}%`,
            top: `${box.y0 * 100}%`,
            width: `${Math.max((box.x1 - box.x0) * 100, 0.5)}%`,
            height: `${Math.max((box.y1 - box.y0) * 100, 0.5)}%`,
            transform: isHovered ? 'scale(1.02)' : 'scale(1)',
            zIndex: isHovered ? 10 : 1,
          }}
          onMouseEnter={() => setHoveredId(highlightId)}
          onMouseLeave={() => setHoveredId(null)}
          onClick={() => onHighlightClick?.(h)}
          title={`${h.concept} (${Math.round(h.confidence * 100)}% confidence)`}
        />
      ))
    }

    // Fallback to approximation-based positioning
    const top = (h.start / maxEnd) * 100
    const height = Math.max(((h.end - h.start) / maxEnd) * 100, 1)

    return (
      <span
        key={highlightId}
        className={`${styles.highlight} ${styles.highlightApprox}`}
        style={{
          backgroundColor: getHighlightColor(h.category, h.shade_intensity, isHovered),
          top: `${top}%`,
          height: `${height}%`,
          transform: isHovered ? 'scale(1.02)' : 'scale(1)',
          zIndex: isHovered ? 10 : 1,
        }}
        onMouseEnter={() => setHoveredId(highlightId)}
        onMouseLeave={() => setHoveredId(null)}
        onClick={() => onHighlightClick?.(h)}
        title={`${h.concept} (${Math.round(h.confidence * 100)}% confidence)`}
      />
    )
  }

  return (
    <div className={styles.highlightOverlay}>
      {pageHighlights.map((h, idx) => renderHighlight(h, idx))}
      
      {/* Tooltip for hovered highlight */}
      {hoveredId && (
        <div className={styles.highlightTooltip}>
          {pageHighlights.find((h, idx) => 
            `${h.concept}-${h.page}-${h.start}-${idx}` === hoveredId
          )?.concept.replace(/_/g, ' ')}
        </div>
      )}
    </div>
  )
}
