/**
 * Search-related types
 */

/**
 * Search query with filters
 */
export interface SearchQuery {
  query: string
  filters?: SearchFilters
}

/**
 * Search filters
 */
export interface SearchFilters {
  privileged?: boolean
  responsive?: boolean
  production?: boolean
  custodian?: string
  doctype?: string
}

/**
 * Search mode - GUI or CLI
 */
export type SearchMode = 'gui' | 'cli'

/**
 * Search strategy type
 */
export type SearchStrategy = 'lexical' | 'dense' | 'hybrid'
