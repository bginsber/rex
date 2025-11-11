import type { FormEvent } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  rexlitApi,
  type PatternMatch,
  type PrivilegeReviewResponse,
  type SearchResult
} from './api/rexlit'

type Decision = 'privileged' | 'not_privileged' | 'skip'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [selected, setSelected] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [review, setReview] = useState<PrivilegeReviewResponse | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [explainReview, setExplainReview] = useState<PrivilegeReviewResponse | null>(null)
  const [showExplain, setShowExplain] = useState(false)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)

  useEffect(() => {
    rexlitApi
      .stats()
      .then(setStats)
      .catch(() => {
        // stats are optional for MVP; swallow errors
      })
  }, [])

  const resultCount = useMemo(() => results.length, [results])
  const documentUrl = selected ? rexlitApi.getDocumentUrl(selected.sha256, selected.path) : undefined
  const activeReview = showExplain && explainReview ? explainReview : review
  const activeDecision = activeReview?.decision
  const patternMatches: PatternMatch[] = activeReview?.pattern_matches ?? []
  const stageStatuses = activeReview?.stages ?? []
  const classificationLabels = activeDecision?.labels?.length
    ? activeDecision.labels.join(', ')
    : 'Non-privileged'
  const isPrivileged = activeDecision?.labels?.some((label) =>
    label.toUpperCase().includes('PRIVILEGED')
  )
  const needsReview = activeDecision?.needs_review ?? false
  const confidencePercent = activeDecision
    ? `${(activeDecision.confidence * 100).toFixed(1)}%`
    : '—'
  const reasoningHash = activeDecision?.reasoning_hash
  const truncatedHash = reasoningHash ? `${reasoningHash.slice(0, 16)}…` : '—'
  const initialSummary = review?.decision.reasoning_summary
  const detailedSummary = explainReview?.decision.reasoning_summary
  const showInitialSummary = Boolean(
    showExplain && explainReview && initialSummary && detailedSummary && initialSummary !== detailedSummary
  )
  const decisionTimestamp = activeDecision?.decision_ts
  const formattedDecisionTs = decisionTimestamp
    ? new Date(decisionTimestamp).toLocaleString()
    : null

  useEffect(() => {
    const hash = selected?.sha256
    if (!hash) {
      setReview(null)
      setExplainReview(null)
      setShowExplain(false)
      setReviewError(null)
      setExplainError(null)
      setReviewLoading(false)
      setExplainLoading(false)
      return
    }

    let cancelled = false
    setReview(null)
    setExplainReview(null)
    setShowExplain(false)
    setReviewError(null)
    setExplainError(null)
    setReviewLoading(true)

    rexlitApi
      .privilegeClassify({ hash, path: selected.path })
      .then((response) => {
        if (!cancelled) {
          setReview(response)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setReviewError(
            err instanceof Error ? err.message : 'Privilege review failed'
          )
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReviewLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [selected?.sha256, selected?.path])

  const refreshReview = useCallback(() => {
    if (!selected?.sha256) {
      setReviewError('Select a document first')
      return
    }
    setReviewLoading(true)
    setReviewError(null)
    rexlitApi
      .privilegeClassify({ hash: selected.sha256, path: selected.path })
      .then((response) => {
        setReview(response)
        setExplainReview(null)
        setShowExplain(false)
      })
      .catch((err) => {
        setReviewError(
          err instanceof Error ? err.message : 'Privilege review failed'
        )
      })
      .finally(() => {
        setReviewLoading(false)
      })
  }, [selected?.sha256, selected?.path])

  const toggleExplanation = useCallback(async () => {
    if (!selected?.sha256) {
      setExplainError('Select a document first')
      return
    }

    if (showExplain) {
      setShowExplain(false)
      return
    }

    if (explainReview) {
      setShowExplain(true)
      return
    }

    setExplainLoading(true)
    setExplainError(null)
    try {
      const response = await rexlitApi.privilegeExplain({ hash: selected.sha256, path: selected.path })
      setExplainReview(response)
      setShowExplain(true)
    } catch (err) {
      setExplainError(
        err instanceof Error ? err.message : 'Failed to load explanation'
      )
      setShowExplain(false)
    } finally {
      setExplainLoading(false)
    }
  }, [explainReview, selected?.sha256, selected?.path, showExplain])

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
              <div className="review-panel">
                <div className="review-header">
                  <div>
                    <h3>Privilege Review</h3>
                    {formattedDecisionTs && (
                      <p className="review-meta">
                        {formattedDecisionTs} · Model {activeDecision?.model_version ?? '—'} · Policy {activeDecision?.policy_version ?? '—'}
                      </p>
                    )}
                    {!formattedDecisionTs && (
                      <p className="review-meta">Model {activeDecision?.model_version ?? '—'} · Policy {activeDecision?.policy_version ?? '—'}</p>
                    )}
                  </div>
                  <div className="review-actions">
                    <button onClick={refreshReview} disabled={reviewLoading}>
                      {reviewLoading ? 'Reviewing…' : 'Re-run review'}
                    </button>
                    <button
                      onClick={toggleExplanation}
                      disabled={reviewLoading || explainLoading || !review}
                    >
                      {explainLoading
                        ? 'Loading…'
                        : showExplain
                        ? 'Hide explanation'
                        : 'View full explanation'}
                    </button>
                  </div>
                </div>

                {reviewError && <div className="alert error">{reviewError}</div>}
                {explainError && <div className="alert error">{explainError}</div>}

                {reviewLoading && (
                  <div className="review-status">Running privilege review…</div>
                )}

                {!reviewLoading && !review && !reviewError && (
                  <div className="review-status">Privilege decision will appear here.</div>
                )}

                {!reviewLoading && activeDecision && (
                  <>
                    {showExplain && explainReview && (
                      <div className="alert info subtle">
                        Viewing high-effort explanation (reasoning effort {activeDecision.reasoning_effort}).
                      </div>
                    )}
                    <div className="review-metrics">
                      <div className="metric-card">
                        <span className="metric-label">Classification</span>
                        <span
                          className={
                            isPrivileged
                              ? 'metric-value privileged'
                              : 'metric-value non-privileged'
                          }
                        >
                          {classificationLabels}
                        </span>
                      </div>
                      <div className="metric-card">
                        <span className="metric-label">Confidence</span>
                        <span className="metric-value">{confidencePercent}</span>
                      </div>
                      <div className="metric-card">
                        <span className="metric-label">Needs Review</span>
                        <span
                          className={needsReview ? 'metric-value warning' : 'metric-value'}
                        >
                          {needsReview ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div className="metric-card">
                        <span className="metric-label">Reasoning Effort</span>
                        <span className="metric-value">{activeDecision.reasoning_effort}</span>
                      </div>
                    </div>

                    <div className="stage-badges">
                      {stageStatuses.map((stage) => (
                        <div key={stage.stage} className={`stage-badge ${stage.status}`}>
                          <div className="stage-title">{stage.stage}</div>
                          <div className="stage-state">
                            {stage.status === 'completed' ? 'Completed' : 'Skipped'}
                          </div>
                          {stage.notes && <p>{stage.notes}</p>}
                        </div>
                      ))}
                    </div>

                    <div className="reasoning-panel">
                      <div className="reasoning-row">
                        <span className="reasoning-label">Reasoning summary</span>
                        <p>{activeDecision.reasoning_summary || 'No summary returned.'}</p>
                      </div>
                      {showInitialSummary && (
                        <div className="reasoning-row muted">
                          <span className="reasoning-label">Initial summary</span>
                          <p>{initialSummary}</p>
                        </div>
                      )}
                      <div className="reasoning-row hash">
                        <span className="reasoning-label">Reasoning hash</span>
                        <code title={reasoningHash ?? ''}>{truncatedHash}</code>
                      </div>
                      <div className="reasoning-flags">
                        <span
                          className={
                            activeDecision.full_reasoning_available
                              ? 'badge success'
                              : 'badge muted'
                          }
                        >
                          {activeDecision.full_reasoning_available
                            ? 'Full CoT stored in encrypted vault'
                            : 'Full CoT not retained'}
                        </span>
                        {activeDecision.error_message && (
                          <span className="badge warning">{activeDecision.error_message}</span>
                        )}
                      </div>
                    </div>

                    {patternMatches.length > 0 && (
                      <div className="pattern-panel">
                        <h4>Pattern signals</h4>
                        <ul>
                          {patternMatches.map((match, index) => (
                            <li key={`${match.rule ?? 'pattern'}-${index}`}>
                              <div className="pattern-header">
                                <span className="pattern-rule">{match.rule ?? match.stage ?? `Rule ${index + 1}`}</span>
                                {typeof match.confidence === 'number' && (
                                  <span className="pattern-confidence">
                                    {(match.confidence * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                              {match.snippet && <p>{match.snippet}</p>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}
              </div>
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
