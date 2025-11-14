/**
 * Document metadata and search result types
 */

export interface SearchResult {
  path: string
  sha256: string
  custodian?: string | null
  doctype?: string | null
  score: number
  snippet?: string | null
  strategy?: string
  lexical_score?: number | null
  dense_score?: number | null
}

/**
 * Document reference - minimal identifying info
 */
export interface DocumentRef {
  sha256: string
  path: string
}

/**
 * Extended document with full metadata
 */
export interface Document extends SearchResult {
  // Can be extended with additional fields as needed
  batesNumber?: string
  tags?: string[]
}
