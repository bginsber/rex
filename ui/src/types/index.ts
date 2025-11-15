/**
 * Central type exports for RexLit UI
 *
 * Organized by domain:
 * - document: Document metadata and search results
 * - privilege: Privilege classification and review
 * - policy: Policy management
 * - audit: Audit trail and decisions
 * - search: Search queries and filters
 * - ui: UI state and interactions
 */

// Document types
export type {
  SearchResult,
  DocumentRef,
  Document
} from './document'

// Privilege types
export type {
  RedactionSpan,
  PolicyDecision,
  PrivilegeStageStatus,
  PatternMatch,
  PrivilegeReviewResponse,
  PrivilegeRequestPayload,
  ClassificationLabel,
  ConfidenceLevel
} from './privilege'

// Policy types
export type {
  PrivilegePolicyMetadata,
  PrivilegePolicyDetail,
  PrivilegePolicyValidation,
  PolicyStage
} from './policy'

// Audit types
export type {
  AuditDecisionPayload,
  AuditEvent,
  AuditTimelineEntry
} from './audit'

// Search types
export type {
  SearchQuery,
  SearchFilters,
  SearchMode,
  SearchStrategy
} from './search'

// UI types
export type {
  NavigationView,
  Toast,
  ModalState,
  LoadingState,
  ErrorState,
  DiffLine,
  PolicyStageLabels,
  AlertType
} from './ui'
