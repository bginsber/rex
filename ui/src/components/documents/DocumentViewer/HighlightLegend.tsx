import styles from './DocumentViewer.module.css'

interface HighlightLegendProps {
  legend: Record<string, string>
}

export function HighlightLegend({ legend }: HighlightLegendProps) {
  const entries = Object.entries(legend || {})
  if (!entries.length) return null

  return (
    <div className={styles.legend}>
      {entries.map(([color, label]) => (
        <div key={color} className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{ backgroundColor: color }} />
          <span className={styles.legendLabel}>{label}</span>
        </div>
      ))}
    </div>
  )
}
