import { useState, useMemo } from 'react'
import type { Highlight } from '@/types'
import styles from './ConceptFilter.module.css'

interface ConceptFilterProps {
  highlights: Highlight[]
  onFilterChange: (filteredHighlights: Highlight[]) => void
}

interface CategoryInfo {
  name: string
  color: string
  count: number
  enabled: boolean
}

// Category display names and accessible colors
const CATEGORY_CONFIG: Record<string, { label: string; color: string; description: string }> = {
  communication: {
    label: 'Communication',
    color: '#00b4d8',
    description: 'Email headers, sender/recipient info'
  },
  privilege: {
    label: 'Privilege',
    color: '#ba55d3',
    description: 'Attorney-client, work product'
  },
  entity: {
    label: 'Entity',
    color: '#ffc107',
    description: 'Key parties, dates, deadlines'
  },
  hotdoc: {
    label: 'Hot Document',
    color: '#ef4444',
    description: 'Potential smoking guns'
  },
  responsive: {
    label: 'Responsive',
    color: '#22c55e',
    description: 'Contract terms, relevant content'
  }
}

export function ConceptFilter({ highlights, onFilterChange }: ConceptFilterProps) {
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    new Set(Object.keys(CATEGORY_CONFIG))
  )
  const [confidenceThreshold, setConfidenceThreshold] = useState(0)
  const [showUncertainOnly, setShowUncertainOnly] = useState(false)

  // Compute category counts
  const categoryStats = useMemo(() => {
    const stats: Record<string, number> = {}
    for (const h of highlights) {
      stats[h.category] = (stats[h.category] || 0) + 1
    }
    return stats
  }, [highlights])

  // Apply filters
  const applyFilters = (
    categories: Set<string>,
    threshold: number,
    uncertainOnly: boolean
  ) => {
    const filtered = highlights.filter(h => {
      // Category filter
      if (!categories.has(h.category)) return false
      
      // Uncertain only mode logic:
      // If enabled, we strictly show 50-75% range, ignoring the slider.
      // If disabled, we respect the slider threshold.
      if (uncertainOnly) {
        if (h.confidence < 0.5 || h.confidence > 0.75) return false
      } else {
        if (h.confidence < threshold) return false
      }
      
      return true
    })
    onFilterChange(filtered)
  }

  const toggleCategory = (category: string) => {
    const newEnabled = new Set(enabledCategories)
    if (newEnabled.has(category)) {
      newEnabled.delete(category)
    } else {
      newEnabled.add(category)
    }
    setEnabledCategories(newEnabled)
    applyFilters(newEnabled, confidenceThreshold, showUncertainOnly)
  }

  const handleThresholdChange = (value: number) => {
    setConfidenceThreshold(value)
    applyFilters(enabledCategories, value, showUncertainOnly)
  }

  const handleUncertainToggle = () => {
    const newValue = !showUncertainOnly
    setShowUncertainOnly(newValue)
    applyFilters(enabledCategories, confidenceThreshold, newValue)
  }

  const selectAll = () => {
    const all = new Set(Object.keys(CATEGORY_CONFIG))
    setEnabledCategories(all)
    applyFilters(all, confidenceThreshold, showUncertainOnly)
  }

  const selectNone = () => {
    const none = new Set<string>()
    setEnabledCategories(none)
    applyFilters(none, confidenceThreshold, showUncertainOnly)
  }

  const totalHighlights = highlights.length
  // Calculate visible count for display
  const visibleCount = highlights.filter(h => {
    if (!enabledCategories.has(h.category)) return false
    if (showUncertainOnly) {
        if (h.confidence < 0.5 || h.confidence > 0.75) return false
    } else {
        if (h.confidence < confidenceThreshold) return false
    }
    return true
  }).length

  return (
    <div className={styles.filterPanel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Concept Filters</h3>
        <span className={styles.count}>
          {visibleCount}/{totalHighlights}
        </span>
      </div>

      {/* Category toggles */}
      <div className={styles.categories}>
        <div className={styles.categoryActions}>
          <button onClick={selectAll} className={styles.actionBtn}>All</button>
          <button onClick={selectNone} className={styles.actionBtn}>None</button>
        </div>
        
        {Object.entries(CATEGORY_CONFIG).map(([key, config]) => {
          const count = categoryStats[key] || 0
          const isEnabled = enabledCategories.has(key)
          
          return (
            <button
              key={key}
              className={`${styles.categoryToggle} ${isEnabled ? styles.enabled : styles.disabled}`}
              onClick={() => toggleCategory(key)}
              title={config.description}
            >
              <span
                className={styles.categoryColor}
                style={{ backgroundColor: config.color }}
              />
              <span className={styles.categoryLabel}>{config.label}</span>
              <span className={styles.categoryCount}>{count}</span>
            </button>
          )
        })}
      </div>

      {/* Confidence threshold slider */}
      <div className={`${styles.slider} ${showUncertainOnly ? styles.sliderDisabled : ''}`}>
        <label className={styles.sliderLabel}>
          Min Confidence: {Math.round(confidenceThreshold * 100)}%
        </label>
        <input
          type="range"
          min="0"
          max="100"
          value={confidenceThreshold * 100}
          onChange={(e) => handleThresholdChange(Number(e.target.value) / 100)}
          className={styles.sliderInput}
          disabled={showUncertainOnly}
        />
        <div className={styles.sliderMarks}>
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Uncertain only toggle */}
      <div className={styles.uncertainToggle}>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={showUncertainOnly}
            onChange={handleUncertainToggle}
            className={styles.checkbox}
          />
          <span className={styles.checkboxText}>
            Show only uncertain (50-75%)
          </span>
        </label>
        <p className={styles.uncertainHelp}>
          Filter to highlights that need human review
        </p>
      </div>
    </div>
  )
}

