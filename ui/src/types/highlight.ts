export interface Highlight {
  concept: string
  category: string
  confidence: number
  start: number
  end: number
  page: number
  color: string
  shade_intensity: number
}

export interface HeatmapEntry {
  page: number
  temperature: number
  highlight_count: number
}

export interface HighlightData {
  document_hash: string
  highlights: Highlight[]
  heatmap: HeatmapEntry[]
  color_legend: Record<string, string>
}
