import { useState, useCallback } from 'react'
import type { NavigationView, SearchResult } from '@/types'
import { rexlitApi } from './api/rexlit'
import { AppLayout } from '@/components/layout/AppLayout'
import { NavRail } from '@/components/layout/NavRail'
import { SearchPanel } from '@/components/search/SearchPanel'
import { DocumentViewer } from '@/components/documents/DocumentViewer'

function App() {
  // Navigation state
  const [activeView, setActiveView] = useState<NavigationView>('search')

  // Search state
  const [results, setResults] = useState<SearchResult[]>([])
  const [selected, setSelected] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Search handler
  const handleSearch = useCallback(async (query: string) => {
    setLoading(true)
    setError(null)
    try {
      const searchResults = await rexlitApi.search(query)
      setResults(searchResults)
      // Auto-select first result if available
      if (searchResults.length > 0) {
        setSelected(searchResults[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      setResults([])
      setSelected(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Document selection handler
  const handleSelectDocument = useCallback((document: SearchResult) => {
    setSelected(document)
  }, [])

  return (
    <AppLayout
      statusBarProps={{
        caseNumber: 'CASE-2024-CV-1847',
        caseName: 'Martinez v. Apex Corp.',
        batesNumber: 'APEX-00428391',
        auditEventCount: 1847,
        isOnline: false,
        indexStatus: 'ready'
      }}
    >
      {/* Navigation Rail */}
      <NavRail activeView={activeView} onViewChange={setActiveView} />

      {/* Search Panel */}
      <SearchPanel
        results={results}
        selectedDocumentHash={selected?.sha256}
        onSearch={handleSearch}
        onSelectDocument={handleSelectDocument}
        loading={loading}
      />

      {/* Document Viewer */}
      <DocumentViewer
        document={selected}
        getDocumentUrl={rexlitApi.getDocumentUrl}
      />

      {/* Error display (if needed) */}
      {error && (
        <div style={{ position: 'fixed', bottom: '24px', right: '24px', padding: '12px 24px', background: 'var(--bg-elevated)', border: '1px solid var(--red-privilege)', borderRadius: 'var(--radius-md)', color: 'var(--red-privilege)', zIndex: 10000 }}>
          {error}
        </div>
      )}
    </AppLayout>
  )
}

export default App
