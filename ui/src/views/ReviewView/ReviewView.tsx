import { useCallback, useEffect, useMemo, useState } from 'react'
import type { PrivilegeReviewResponse, SearchResult } from '@/types'
import { rexlitApi } from '@/api/rexlit'
import { DocumentViewer } from '@/components/documents/DocumentViewer'
import styles from './ReviewView.module.css'

type Decision = 'privileged' | 'not_privileged' | 'skip'

export interface ReviewViewProps {
  document: SearchResult | null
  getDocumentUrl: (sha256: string) => string
}

export function ReviewView({ document, getDocumentUrl }: ReviewViewProps) {
  const [review, setReview] = useState<PrivilegeReviewResponse | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [explainReview, setExplainReview] = useState<PrivilegeReviewResponse | null>(null)
  const [showExplain, setShowExplain] = useState(false)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null)
  const [decisionError, setDecisionError] = useState<string | null>(null)

  useEffect(() => {
    if (!document?.sha256) {
      setReview(null)
      setExplainReview(null)
      setShowExplain(false)
      setReviewError(null)
      setExplainError(null)
      setDecisionMessage(null)
      setDecisionError(null)
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
    setDecisionMessage(null)
    setDecisionError(null)
    setReviewLoading(true)

    rexlitApi
      .privilegeClassify({ hash: document.sha256 })
      .then((response) => {
        if (!cancelled) {
          setReview(response)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setReviewError(err instanceof Error ? err.message : 'Privilege review failed')
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
  }, [document?.sha256])

  const refreshReview = useCallback(() => {
    if (!document?.sha256) {
      setReviewError('Select a document first')
      return
    }

    setReviewLoading(true)
    setReviewError(null)
    setDecisionMessage(null)
    setDecisionError(null)

    rexlitApi
      .privilegeClassify({ hash: document.sha256 })
      .then((response) => {
        setReview(response)
        setExplainReview(null)
        setShowExplain(false)
      })
      .catch((err) => {
        setReviewError(err instanceof Error ? err.message : 'Privilege review failed')
      })
      .finally(() => {
        setReviewLoading(false)
      })
  }, [document?.sha256])

  const toggleExplanation = useCallback(async () => {
    if (!document?.sha256) {
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
      const response = await rexlitApi.privilegeExplain({ hash: document.sha256 })
      setExplainReview(response)
      setShowExplain(true)
    } catch (err) {
      setExplainError(err instanceof Error ? err.message : 'Failed to load explanation')
      setShowExplain(false)
    } finally {
      setExplainLoading(false)
    }
  }, [document?.sha256, explainReview, showExplain])

  const decide = useCallback(
    async (decision: Decision) => {
      if (!document?.sha256) {
        setDecisionError('Select a document first')
        return
      }

      setDecisionError(null)
      setDecisionMessage('Recording decision…')
      try {
        await rexlitApi.submitDecision(document.sha256, { decision })
        setDecisionMessage(
          `Decision "${decision}" recorded for ${document.sha256.slice(0, 8)}…`
        )
      } catch (err) {
        setDecisionError(
          err instanceof Error ? err.message : 'Failed to record decision'
        )
        setDecisionMessage(null)
      }
    },
    [document?.sha256]
  )

  const activeReview = showExplain && explainReview ? explainReview : review
  const activeDecision = activeReview?.decision
  const patternMatches = activeReview?.pattern_matches ?? []
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
    showExplain &&
      explainReview &&
      initialSummary &&
      detailedSummary &&
      initialSummary !== detailedSummary
  )
  const decisionTimestamp = activeDecision?.decision_ts
  const formattedDecisionTs = decisionTimestamp
    ? new Date(decisionTimestamp).toLocaleString()
    : null

  const reasoningEffort = activeDecision?.reasoning_effort ?? '—'
  const modelVersion = activeDecision?.model_version ?? '—'
  const policyVersion = activeDecision?.policy_version ?? '—'

  const noneSelected = !document

  const panelTitle = document ? document.path : 'No document selected'

  const explanationBadge = showExplain && explainReview
    ? `Viewing explanation (effort ${activeDecision?.reasoning_effort ?? '—'})`
    : null

  const stageMap = useMemo(() => {
    return stageStatuses.map((stage) => ({
      id: `${stage.stage}-${stage.status}`,
      label: stage.stage,
      status: stage.status,
      notes: stage.notes
    }))
  }, [stageStatuses])

  return (
    <section className={styles.reviewView}>
      {noneSelected ? (
        <div className={styles.emptyState}>
          <h3>No document selected</h3>
          <p>Select a document from the Search view to run privilege review.</p>
        </div>
      ) : (
        <>
          <div className={styles.documentColumn}>
            <DocumentViewer document={document} getDocumentUrl={getDocumentUrl} />
          </div>
          <div className={styles.panel}>
            <header className={styles.panelHeader}>
              <div>
                <h2 className={styles.panelTitle}>Privilege Review</h2>
                <p className={styles.panelMeta}>
                  {panelTitle}
                  {formattedDecisionTs ? ` · ${formattedDecisionTs}` : ''}
                </p>
                <p className={styles.panelMeta}>
                  Model {modelVersion} · Policy {policyVersion}
                </p>
              </div>
              <div className={styles.actions}>
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
                      : 'View explanation'}
                </button>
              </div>
            </header>

            {explanationBadge && (
              <div className={`${styles.alert} ${styles.info}`}>{explanationBadge}</div>
            )}
            {reviewError && <div className={`${styles.alert} ${styles.error}`}>{reviewError}</div>}
            {explainError && <div className={`${styles.alert} ${styles.error}`}>{explainError}</div>}
            {decisionError && <div className={`${styles.alert} ${styles.error}`}>{decisionError}</div>}
            {decisionMessage && (
              <div className={`${styles.alert} ${styles.success}`}>{decisionMessage}</div>
            )}

            {reviewLoading && (
              <div className={styles.status}>Running privilege review…</div>
            )}

            {!reviewLoading && !activeDecision && !reviewError && (
              <div className={styles.status}>Privilege decision will appear here.</div>
            )}

            {!reviewLoading && activeDecision && (
              <>
                <div className={styles.metrics}>
                  <div className={styles.metricCard}>
                    <span className={styles.metricLabel}>Classification</span>
                    <span
                      className={
                        isPrivileged ? styles.metricValuePrivileged : styles.metricValue
                      }
                    >
                      {classificationLabels}
                    </span>
                  </div>
                  <div className={styles.metricCard}>
                    <span className={styles.metricLabel}>Confidence</span>
                    <span className={styles.metricValue}>{confidencePercent}</span>
                  </div>
                  <div className={styles.metricCard}>
                    <span className={styles.metricLabel}>Needs Review</span>
                    <span
                      className={
                        needsReview ? styles.metricValueWarning : styles.metricValue
                      }
                    >
                      {needsReview ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className={styles.metricCard}>
                    <span className={styles.metricLabel}>Reasoning Effort</span>
                    <span className={styles.metricValue}>{reasoningEffort}</span>
                  </div>
                </div>

                {stageMap.length > 0 && (
                  <div className={styles.stageGrid}>
                    {stageMap.map((stage) => (
                      <div key={stage.id} className={styles.stageCard}>
                        <span className={styles.stageTitle}>{stage.label}</span>
                        <span className={styles.stageState}>
                          {stage.status === 'completed' ? 'Completed' : stage.status}
                        </span>
                        {stage.notes && <p>{stage.notes}</p>}
                      </div>
                    ))}
                  </div>
                )}

                <div className={styles.reasoning}>
                  <div className={styles.reasoningRow}>
                    <span className={styles.reasoningLabel}>Reasoning summary</span>
                    <p>{activeDecision.reasoning_summary || 'No summary returned.'}</p>
                  </div>
                  {showInitialSummary && (
                    <div className={`${styles.reasoningRow} ${styles.muted}`}>
                      <span className={styles.reasoningLabel}>Initial summary</span>
                      <p>{initialSummary}</p>
                    </div>
                  )}
                  <div className={`${styles.reasoningRow} ${styles.hashRow}`}>
                    <span className={styles.reasoningLabel}>Reasoning hash</span>
                    <code title={reasoningHash ?? ''}>{truncatedHash}</code>
                  </div>
                </div>

                {patternMatches.length > 0 && (
                  <div className={styles.patterns}>
                    <h4>Pattern signals</h4>
                    <ul>
                      {patternMatches.map((match, index) => (
                        <li key={`${match.rule ?? 'pattern'}-${index}`}>
                          <div className={styles.patternHeader}>
                            <span>{match.rule ?? match.stage ?? `Rule ${index + 1}`}</span>
                            {typeof match.confidence === 'number' && (
                              <span className={styles.patternConfidence}>
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

            <div className={styles.decisionBar}>
              <button onClick={() => decide('privileged')} disabled={!document}>
                Privileged
              </button>
              <button onClick={() => decide('not_privileged')} disabled={!document}>
                Not Privileged
              </button>
              <button onClick={() => decide('skip')} disabled={!document}>
                Skip
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
