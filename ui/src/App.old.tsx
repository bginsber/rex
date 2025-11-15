import type { FormEvent } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  rexlitApi,
  type PatternMatch,
  type PrivilegePolicyDetail,
  type PrivilegePolicyMetadata,
  type PrivilegePolicyValidation,
  type PrivilegeReviewResponse,
  type SearchResult
} from './api/rexlit'

const POLICY_STAGE_LABELS: Record<number, string> = {
  1: 'Stage 1 · Privilege',
  2: 'Stage 2 · Responsiveness',
  3: 'Stage 3 · Redaction'
}

type DiffLine = {
  type: 'equal' | 'add' | 'remove'
  text: string
}

function buildLineDiff(original: string, updated: string): DiffLine[] {
  const originalLines = original.split('\n')
  const updatedLines = updated.split('\n')
  const maxLength = Math.max(originalLines.length, updatedLines.length)
  const diff: DiffLine[] = []

  for (let index = 0; index < maxLength; index += 1) {
    const before = originalLines[index] ?? ''
    const after = updatedLines[index] ?? ''

    if (before === after) {
      if (before) {
        diff.push({ type: 'equal', text: before })
      }
      continue
    }

    if (before) {
      diff.push({ type: 'remove', text: before })
    }
    if (after) {
      diff.push({ type: 'add', text: after })
    }
  }

  return diff
}

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
  const [policyOverview, setPolicyOverview] = useState<PrivilegePolicyMetadata[]>([])
  const [policyStage, setPolicyStage] = useState<number>(1)
  const [policyMetadata, setPolicyMetadata] = useState<PrivilegePolicyDetail | null>(null)
  const [policyText, setPolicyText] = useState('')
  const [editedPolicyText, setEditedPolicyText] = useState('')
  const [policyLoading, setPolicyLoading] = useState(false)
  const [policySaving, setPolicySaving] = useState(false)
  const [policyMessage, setPolicyMessage] = useState<string | null>(null)
  const [policyError, setPolicyError] = useState<string | null>(null)
  const [policyValidation, setPolicyValidation] = useState<PrivilegePolicyValidation | null>(null)
  const [showPolicyDiff, setShowPolicyDiff] = useState(false)
  const [policyReloadKey, setPolicyReloadKey] = useState(0)

  useEffect(() => {
    rexlitApi
      .stats()
      .then(setStats)
      .catch(() => {
        // stats are optional for MVP; swallow errors
      })
  }, [])

  useEffect(() => {
    rexlitApi
      .listPolicies()
      .then(setPolicyOverview)
      .catch(() => {
        // Policy overview is informative; ignore errors silently.
      })
  }, [])

  useEffect(() => {
    let cancelled = false
    setPolicyLoading(true)
    setPolicyError(null)
    setPolicyMessage(null)
    setPolicyValidation(null)
    setShowPolicyDiff(false)

    rexlitApi
      .getPolicy(policyStage)
      .then((detail) => {
        if (cancelled) {
          return
        }
        setPolicyMetadata(detail)
        setPolicyText(detail.text)
        setEditedPolicyText(detail.text)
      })
      .catch((err) => {
        if (cancelled) {
          return
        }
        setPolicyMetadata(null)
        setPolicyText('')
        setEditedPolicyText('')
        setPolicyError(
          err instanceof Error ? err.message : 'Failed to load privilege policy'
        )
      })
      .finally(() => {
        if (!cancelled) {
          setPolicyLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [policyStage, policyReloadKey])

  const resultCount = useMemo(() => results.length, [results])
  const documentUrl = selected ? rexlitApi.getDocumentUrl(selected.sha256) : undefined
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
  const policyHasChanges = editedPolicyText !== policyText
  const policyDiff = useMemo(
    () => buildLineDiff(policyText, editedPolicyText),
    [policyText, editedPolicyText]
  )
  const selectedPolicyOverview = useMemo(
    () => policyOverview.find((item) => item.stage === policyStage),
    [policyOverview, policyStage]
  )
  const policyModifiedAt = policyMetadata?.modified_at
    ? new Date(policyMetadata.modified_at).toLocaleString()
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
      .privilegeClassify({ hash })
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
  }, [selected?.sha256])

  const refreshReview = useCallback(() => {
    if (!selected?.sha256) {
      setReviewError('Select a document first')
      return
    }
    setReviewLoading(true)
    setReviewError(null)
    rexlitApi
      .privilegeClassify({ hash: selected.sha256 })
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
  }, [selected?.sha256])

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
      const response = await rexlitApi.privilegeExplain({ hash: selected.sha256 })
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
  }, [explainReview, selected?.sha256, showExplain])

  const handlePolicyStageChange = useCallback((stage: number) => {
    setPolicyStage(stage)
    setPolicyMessage(null)
    setPolicyError(null)
  }, [])

  const handlePolicyReload = useCallback(() => {
    setPolicyReloadKey((key) => key + 1)
  }, [])

  const handlePolicySave = useCallback(async () => {
    if (!policyHasChanges) {
      return
    }

    setPolicySaving(true)
    setPolicyMessage(null)
    setPolicyError(null)

    try {
      const metadata = await rexlitApi.updatePolicy(policyStage, editedPolicyText)
      setPolicyText(editedPolicyText)
      setPolicyMetadata((current) =>
        current
          ? { ...current, ...metadata, text: editedPolicyText }
          : { ...metadata, text: editedPolicyText }
      )
      setPolicyValidation(null)
      setPolicyMessage('Policy updated successfully.')
      const overview = await rexlitApi.listPolicies()
      setPolicyOverview(overview)
    } catch (err) {
      setPolicyError(
        err instanceof Error ? err.message : 'Failed to update privilege policy'
      )
    } finally {
      setPolicySaving(false)
    }
  }, [editedPolicyText, policyHasChanges, policyStage])

  const handlePolicyValidate = useCallback(async () => {
    setPolicyValidation(null)
    setPolicyError(null)
    setPolicyMessage(null)

    try {
      const result = await rexlitApi.validatePolicy(policyStage)
      setPolicyValidation(result)
    } catch (err) {
      setPolicyError(
        err instanceof Error ? err.message : 'Failed to validate privilege policy'
      )
    }
  }, [policyStage])

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
      <section className="policy-panel">
        <header className="panel-header">
          <div>
            <h2>Privilege Policies</h2>
            <p className="subtitle">
              Edit the offline policy templates used by the CLI and review UI.
            </p>
          </div>
          <div className="policy-stage">
            <label>
              Stage
              <select
                value={policyStage}
                onChange={(event) => handlePolicyStageChange(Number(event.target.value))}
                disabled={policyLoading || policySaving}
              >
                {[1, 2, 3].map((stage) => (
                  <option key={stage} value={stage}>
                    {POLICY_STAGE_LABELS[stage] ?? `Stage ${stage}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>

        {policyOverview.length > 0 && (
          <div className="policy-overview">
            {policyOverview.map((meta) => (
              <span
                key={meta.stage}
                className={`policy-chip ${meta.source ?? 'default'}`}
                title={meta.path}
              >
                {POLICY_STAGE_LABELS[meta.stage] ?? `Stage ${meta.stage}`}
                <small>{meta.source ?? 'default'}</small>
              </span>
            ))}
          </div>
        )}

        {policyError && <div className="alert error">{policyError}</div>}
        {policyMessage && <div className="alert success">{policyMessage}</div>}

        {policyValidation && (
          <div className={`alert ${policyValidation.passed ? 'success' : 'error'}`}>
            {policyValidation.passed
              ? 'Policy validation passed.'
              : 'Policy validation found issues.'}
            {!policyValidation.passed && policyValidation.errors.length > 0 && (
              <ul className="policy-errors">
                {policyValidation.errors.map((err, index) => (
                  <li key={`${err}-${index}`}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="policy-meta">
          <span>Path: {policyMetadata?.path ?? '—'}</span>
          <span>
            Source: {policyMetadata?.source ?? selectedPolicyOverview?.source ?? 'default'}
          </span>
          <span>Updated: {policyModifiedAt ?? '—'}</span>
        </div>

        <p className="policy-note">
          Policies are Markdown templates. PDF previews are not yet supported; edit the text
          directly to update instructions.
        </p>

        <textarea
          className="policy-editor"
          value={editedPolicyText}
          onChange={(event) => {
            const nextValue = event.target.value
            setEditedPolicyText(nextValue)
            setPolicyMessage(null)
            setPolicyError(null)
            setPolicyValidation(null)
            if (nextValue === policyText) {
              setShowPolicyDiff(false)
            }
          }}
          disabled={policyLoading || policySaving}
          spellCheck={false}
          rows={16}
        />

        <div className="policy-controls">
          <button
            type="button"
            onClick={handlePolicyReload}
            disabled={policyLoading || policySaving}
          >
            Reload
          </button>
          <button
            type="button"
            onClick={handlePolicyValidate}
            disabled={policyLoading || policySaving || policyHasChanges}
          >
            Validate
          </button>
          <button
            type="button"
            onClick={() => setShowPolicyDiff((value) => !value)}
            disabled={!policyHasChanges}
          >
            {showPolicyDiff ? 'Hide diff' : 'Show diff'}
          </button>
          <button
            type="button"
            className="primary"
            onClick={handlePolicySave}
            disabled={!policyHasChanges || policySaving}
          >
            {policySaving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        {policyLoading && (
          <div className="policy-status">Loading policy template…</div>
        )}

        {!policyLoading && showPolicyDiff && policyHasChanges && (
          <pre className="policy-diff">
            {policyDiff.map((line, index) => (
              <div key={`${line.type}-${index}`} className={`diff-line ${line.type}`}>
                {line.type === 'add' ? '+' : line.type === 'remove' ? '−' : ' '}
                {line.text}
              </div>
            ))}
          </pre>
        )}
      </section>
    </div>
  )
}

export default App
