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

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with ${response.status}`)
  }
  return response.json() as Promise<T>
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

  getDocumentUrl(sha256: string, path?: string) {
    const url = new URL(`${API_ROOT}/documents/${sha256}/file`)
    if (path) {
      url.searchParams.set('path', path)
    }
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
  }
}
