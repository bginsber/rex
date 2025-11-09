import type { FormEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { rexlitApi, type SearchResult } from './api/rexlit'

type Decision = 'privileged' | 'not_privileged' | 'skip'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [selected, setSelected] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    rexlitApi
      .stats()
      .then(setStats)
      .catch(() => {
        // stats are optional for MVP; swallow errors
      })
  }, [])

  const resultCount = useMemo(() => results.length, [results])
  const documentUrl = selected ? rexlitApi.getDocumentUrl(selected.sha256) : undefined

  async function search(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) {
      setError('Enter a query to search')
      return
    }
    setLoading(true)
    setError(null)
    setStatus(null)
    try {
      const response = await rexlitApi.search(query.trim())
      setResults(response)
      setSelected(response[0] ?? null)
      if (!response.length) {
        setStatus('No results found')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  async function decide(decision: Decision) {
    if (!selected) {
      setError('Select a document first')
      return
    }

    setError(null)
    setStatus('Recording decision…')
    try {
      await rexlitApi.submitDecision(selected.sha256, { decision })
      setStatus(`Decision "${decision}" recorded for ${selected.sha256.slice(0, 8)}…`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record decision')
      setStatus(null)
    }
  }

  return (
    <div className="layout">
      <header>
        <div>
          <h1>RexLit Review UI</h1>
          <p className="subtitle">Search, review, and log privilege decisions.</p>
        </div>
        {stats && (
          <dl className="stats">
            <div>
              <dt>Documents</dt>
              <dd>{String(stats.doc_count ?? '—')}</dd>
            </div>
            <div>
              <dt>Custodians</dt>
              <dd>{Array.isArray(stats.custodians) ? stats.custodians.length : '—'}</dd>
            </div>
          </dl>
        )}
      </header>

      <form className="search-bar" onSubmit={search}>
        <input
          name="query"
          placeholder="Search privileged, contract, discovery…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <div className="alert error">{error}</div>}
      {status && <div className="alert info">{status}</div>}

      <main className="workspace">
        <aside>
          <div className="panel-header">
            <h2>Results ({resultCount})</h2>
          </div>
          <ul className="results">
            {results.map((hit) => {
              const isActive = selected?.sha256 === hit.sha256
              return (
                <li key={hit.sha256}>
                  <button
                    className={isActive ? 'result active' : 'result'}
                    onClick={() => {
                      setSelected(hit)
                      setStatus(null)
                    }}
                  >
                    <span className="result-path">{hit.path}</span>
                    <span className="result-meta">
                      {(hit.custodian || 'unknown').toUpperCase()} · {hit.doctype || 'document'}
                    </span>
                    {hit.snippet && <span className="result-snippet">{hit.snippet}</span>}
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>

        <section className="viewer">
          {selected ? (
            <>
              <header className="panel-header">
                <div>
                  <h2>{selected.path}</h2>
                  <p>
                    SHA-256 {selected.sha256.slice(0, 16)}… · Score {selected.score.toFixed(2)} ·{' '}
                    {selected.strategy || 'lexical'}
                  </p>
                </div>
              </header>
              <iframe
                key={selected.sha256}
                src={documentUrl}
                title={selected.path}
                sandbox="allow-same-origin allow-scripts"
              />
              <div className="decision-bar">
                <button onClick={() => decide('privileged')}>Privileged</button>
                <button onClick={() => decide('not_privileged')}>Not Privileged</button>
                <button onClick={() => decide('skip')}>Skip</button>
              </div>
            </>
          ) : (
            <div className="empty-state">Search and select a document to begin.</div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
