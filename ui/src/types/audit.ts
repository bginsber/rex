/**
 * Audit trail and decision types
 */

/**
 * Decision payload for audit trail
 */
export interface AuditDecisionPayload {
  decision: 'privileged' | 'not_privileged' | 'skip'
  notes?: string
}

/**
 * Audit event for timeline display
 */
export interface AuditEvent {
  timestamp: string
  action: string
  user?: string
  document_hash?: string
  decision?: string
  notes?: string
  hash?: string // Hash chain reference
}

/**
 * Audit timeline entry for UI display
 */
export interface AuditTimelineEntry {
  id: string
  timestamp: string
  action: string
  description: string
  isActive?: boolean
}
