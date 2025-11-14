/**
 * Privilege classification and review types
 */

/**
 * Redaction span within a document
 */
export interface RedactionSpan {
  category: string
  start: number
  end: number
  justification: string
}

/**
 * Policy decision from privilege classification
 */
export interface PolicyDecision {
  labels: string[]
  confidence: number
  needs_review: boolean
  reasoning_hash: string
  reasoning_summary: string
  full_reasoning_available: boolean
  redaction_spans: RedactionSpan[]
  model_version: string
  policy_version: string
  reasoning_effort: 'low' | 'medium' | 'high' | 'dynamic'
  decision_ts: string
  error_message: string
}

/**
 * Status of a privilege pipeline stage
 */
export interface PrivilegeStageStatus {
  stage: 'privilege' | 'responsiveness' | 'redaction'
  status: 'completed' | 'skipped' | 'pending'
  mode: 'llm' | 'pattern' | 'disabled'
  reasoning_effort?: string
  needs_review?: boolean
  notes?: string
  redaction_spans?: number
}

/**
 * Pattern match from pattern-based privilege detection
 */
export interface PatternMatch {
  rule?: string
  confidence?: number
  snippet?: string | null
  stage?: string | null
}

/**
 * Full privilege review response from API
 */
export interface PrivilegeReviewResponse {
  decision: PolicyDecision
  stages: PrivilegeStageStatus[]
  pattern_matches: PatternMatch[]
  source?: {
    hash?: string
    path?: string
    threshold?: number
    reasoning_effort?: string
  }
}

/**
 * Request payload for privilege classification
 */
export interface PrivilegeRequestPayload {
  hash?: string
  path?: string
  threshold?: number
  reasoning_effort?: 'low' | 'medium' | 'high' | 'dynamic'
}

/**
 * Classification label type for UI
 */
export type ClassificationLabel = 'privileged' | 'responsive' | 'production' | 'not_privileged'

/**
 * Confidence level for UI display
 */
export type ConfidenceLevel = 'low' | 'medium' | 'high'
