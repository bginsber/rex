const API_ROOT = import.meta.env.VITE_API_URL ?? 'http://localhost:3000/api'

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

export interface AuditDecisionPayload {
  decision: 'privileged' | 'not_privileged' | 'skip'
  notes?: string
}

export interface RedactionSpan {
  category: string
  start: number
  end: number
  justification: string
}

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

export interface PrivilegeStageStatus {
  stage: 'privilege' | 'responsiveness' | 'redaction'
  status: 'completed' | 'skipped' | 'pending'
  mode: 'llm' | 'pattern' | 'disabled'
  reasoning_effort?: string
  needs_review?: boolean
  notes?: string
  redaction_spans?: number
}

export interface PatternMatch {
  rule?: string
  confidence?: number
  snippet?: string | null
  stage?: string | null
}

interface ErrorResponse {
  error: string
}

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

export interface PrivilegeRequestPayload {
  hash?: string
  path?: string
  threshold?: number
  reasoning_effort?: 'low' | 'medium' | 'high' | 'dynamic'
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed with ${response.status}`
    try {
      const data = (await response.clone().json()) as unknown
      if (data && typeof (data as ErrorResponse).error === 'string') {
        message = (data as ErrorResponse).error
      } else if (data) {
        message = JSON.stringify(data)
      }
    } catch {
      try {
        const text = await response.text()
        if (text) {
          message = text
        }
      } catch {
        // ignore secondary parsing errors
      }
    }
    throw new Error(message)
  }
  const contentType = response.headers.get('Content-Type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }
  const text = await response.text()
  return (text ? JSON.parse(text) : null) as T
}

export const rexlitApi = {
  async search(query: string): Promise<SearchResult[]> {
    const response = await fetch(`${API_ROOT}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })
    return handleResponse<SearchResult[]>(response)
  },

  getDocumentUrl(sha256: string) {
    const url = new URL(`${API_ROOT}/documents/${sha256}/file`)
    url.searchParams.set('t', Date.now().toString())
    return url.toString()
  },

  async submitDecision(docId: string, payload: AuditDecisionPayload): Promise<void> {
    const response = await fetch(`${API_ROOT}/reviews/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    await handleResponse<{ success: boolean }>(response)
  },

  async stats(): Promise<Record<string, unknown>> {
    const response = await fetch(`${API_ROOT}/stats`)
    return handleResponse<Record<string, unknown>>(response)
  },

  async privilegeClassify(payload: PrivilegeRequestPayload): Promise<PrivilegeReviewResponse> {
    const response = await fetch(`${API_ROOT}/privilege/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    return handleResponse<PrivilegeReviewResponse>(response)
  },

  async privilegeExplain(payload: PrivilegeRequestPayload): Promise<PrivilegeReviewResponse> {
    const response = await fetch(`${API_ROOT}/privilege/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    return handleResponse<PrivilegeReviewResponse>(response)
  }
}
