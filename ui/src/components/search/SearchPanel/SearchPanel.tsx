import { useState, type FormEvent } from 'react'
import type { SearchResult } from '@/types'
import { DocumentList } from '@/components/documents/DocumentList'
import styles from './SearchPanel.module.css'

export interface SearchPanelProps {
  results: SearchResult[]
  selectedDocumentHash?: string
  onSearch: (query: string) => void
  onSelectDocument?: (document: SearchResult) => void
  loading?: boolean
}

export function SearchPanel({
  results,
  selectedDocumentHash,
  onSearch,
  onSelectDocument,
  loading = false
}: SearchPanelProps) {
  const [query, setQuery] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [lastSearchedQuery, setLastSearchedQuery] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmedQuery = query.trim()
    if (trimmedQuery) {
      onSearch(trimmedQuery)
      setHasSearched(true)
      setLastSearchedQuery(trimmedQuery)
    }
  }

  const emptyMessage = loading
    ? 'Searching...'
    : hasSearched
      ? `No results for "${lastSearchedQuery}"`
      : 'Enter a query to search documents'

  return (
    <aside className={styles.searchPanel}>
      {/* Search Header */}
      <div className={styles.header}>
        <h2 className={styles.title}>Document Search</h2>
      </div>

      {/* Search Form */}
      <form className={styles.searchForm} onSubmit={handleSubmit}>
        <div className={styles.inputWrapper}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={styles.searchIcon}>
            <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M10 10L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents..."
            className={styles.searchInput}
            disabled={loading}
          />
        </div>
        <button type="submit" className={styles.searchButton} disabled={loading || !query.trim()}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {/* Results */}
      <div className={styles.results}>
        <DocumentList
          documents={results}
          selectedDocumentHash={selectedDocumentHash}
          onSelectDocument={onSelectDocument}
          emptyMessage={emptyMessage}
        />
      </div>
    </aside>
  )
}
