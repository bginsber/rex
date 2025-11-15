import type {
  SearchResult,
  AuditDecisionPayload,
  PrivilegeReviewResponse,
  PrivilegeRequestPayload,
  PrivilegePolicyMetadata,
  PrivilegePolicyDetail,
  PrivilegePolicyValidation
} from '@/types'

const API_ROOT = import.meta.env.VITE_API_URL ?? 'http://localhost:3000/api'

interface ErrorResponse {
  error: string
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
  },

  async listPolicies(): Promise<PrivilegePolicyMetadata[]> {
    const response = await fetch(`${API_ROOT}/policy`)
    return handleResponse<PrivilegePolicyMetadata[]>(response)
  },

  async getPolicy(stage: number): Promise<PrivilegePolicyDetail> {
    const response = await fetch(`${API_ROOT}/policy/${stage}`)
    return handleResponse<PrivilegePolicyDetail>(response)
  },

  async updatePolicy(stage: number, text: string): Promise<PrivilegePolicyMetadata> {
    const response = await fetch(`${API_ROOT}/policy/${stage}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    })
    return handleResponse<PrivilegePolicyMetadata>(response)
  },

  async validatePolicy(stage: number): Promise<PrivilegePolicyValidation> {
    const response = await fetch(`${API_ROOT}/policy/${stage}/validate`, {
      method: 'POST'
    })
    return handleResponse<PrivilegePolicyValidation>(response)
  }
}
