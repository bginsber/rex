import type { HeatmapEntry } from '@/types'
import styles from './DocumentViewer.module.css'

interface HeatmapBarProps {
  heatmap: HeatmapEntry[]
  currentPage: number
  onSelectPage: (page: number) => void
}

export function HeatmapBar({ heatmap, currentPage, onSelectPage }: HeatmapBarProps) {
  if (!heatmap?.length) return null

  const total = heatmap.length

  return (
    <div className={styles.heatmapBar}>
      {heatmap.map((entry) => (
        <button
          key={entry.page}
          type="button"
          className={`${styles.heatmapSegment} ${entry.page === currentPage ? styles.heatmapActive : ''}`}
          style={{
            height: `${100 / total}%`,
            backgroundColor: `rgba(255,0,0,${entry.temperature || 0})`
          }}
          onClick={() => onSelectPage(entry.page)}
          title={`Page ${entry.page} • ${entry.highlight_count} highlights`}
        />
      ))}
    </div>
  )
}
