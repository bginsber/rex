import { useCallback, useEffect, useMemo, useState } from 'react'
import type {
  PrivilegePolicyDetail,
  PrivilegePolicyMetadata,
  PrivilegePolicyValidation
} from '@/types'
import { rexlitApi } from '@/api/rexlit'
import styles from './PolicyView.module.css'

type DiffLine = {
  type: 'equal' | 'add' | 'remove'
  text: string
}

const POLICY_STAGE_LABELS: Record<number, string> = {
  1: 'Stage 1 · Privilege',
  2: 'Stage 2 · Responsiveness',
  3: 'Stage 3 · Redaction'
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

export function PolicyView() {
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
      .listPolicies()
      .then(setPolicyOverview)
      .catch(() => {
        // overview is informational; ignore errors
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

  const handlePolicyStageChange = useCallback((stage: number) => {
    setPolicyStage(stage)
    setPolicyMessage(null)
    setPolicyError(null)
  }, [])

  const handlePolicyReload = useCallback(() => {
    setPolicyReloadKey((value) => value + 1)
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

  return (
    <section className={styles.policyView}>
      <header className={styles.panelHeader}>
        <div>
          <h2>Privilege Policies</h2>
          <p className={styles.subtitle}>
            Edit the offline policy templates used by the CLI and review UI.
          </p>
        </div>
        <label className={styles.stagePicker}>
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
      </header>

      {policyOverview.length > 0 && (
        <div className={styles.policyOverview}>
          {policyOverview.map((meta) => (
            <span
              key={meta.stage}
              className={styles.policyChip}
              title={meta.path}
              data-source={meta.source ?? 'default'}
            >
              {POLICY_STAGE_LABELS[meta.stage] ?? `Stage ${meta.stage}`}
              <small>{meta.source ?? 'default'}</small>
            </span>
          ))}
        </div>
      )}

      {policyError && <div className={`${styles.alert} ${styles.error}`}>{policyError}</div>}
      {policyMessage && (
        <div className={`${styles.alert} ${styles.success}`}>{policyMessage}</div>
      )}

      {policyValidation && (
        <div
          className={`${styles.alert} ${
            policyValidation.passed ? styles.success : styles.error
          }`}
        >
          {policyValidation.passed
            ? 'Policy validation passed.'
            : 'Policy validation found issues.'}
          {!policyValidation.passed && policyValidation.errors.length > 0 && (
            <ul className={styles.validationList}>
              {policyValidation.errors.map((err, index) => (
                <li key={`${err}-${index}`}>{err}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className={styles.policyMeta}>
        <span>Path: {policyMetadata?.path ?? '—'}</span>
        <span>
          Source: {policyMetadata?.source ?? selectedPolicyOverview?.source ?? 'default'}
        </span>
        <span>Updated: {policyModifiedAt ?? '—'}</span>
      </div>

      <textarea
        className={styles.policyEditor}
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
        rows={20}
      />

      <div className={styles.controls}>
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
          className={styles.primary}
          onClick={handlePolicySave}
          disabled={!policyHasChanges || policySaving}
        >
          {policySaving ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      {policyLoading && (
        <div className={styles.status}>Loading policy template…</div>
      )}

      {!policyLoading && showPolicyDiff && policyHasChanges && (
        <pre className={styles.policyDiff}>
          {policyDiff.map((line, index) => (
            <div key={`${line.type}-${index}`} className={`${styles.diffLine} ${styles[line.type]}`}>
              {line.type === 'add' ? '+' : line.type === 'remove' ? '−' : ' '}
              {line.text}
            </div>
          ))}
        </pre>
      )}
    </section>
  )
}
