/**
 * UI state and interaction types
 */

/**
 * Navigation view type
 */
export type NavigationView = 'search' | 'review' | 'policy' | 'analytics' | 'settings'

/**
 * Toast notification type
 */
export interface Toast {
  id: string
  message: string
  type?: 'info' | 'success' | 'error' | 'warning'
  duration?: number
}

/**
 * Modal state
 */
export interface ModalState {
  isOpen: boolean
  type?: 'shortcuts' | 'confirm' | 'info'
  data?: unknown
}

/**
 * Loading state for async operations
 */
export interface LoadingState {
  isLoading: boolean
  message?: string
}

/**
 * Error state
 */
export interface ErrorState {
  hasError: boolean
  message?: string
  details?: string
}

/**
 * Diff line for policy comparison
 */
export interface DiffLine {
  type: 'equal' | 'add' | 'remove'
  text: string
}

/**
 * Policy stage labels mapping
 */
export type PolicyStageLabels = Record<number, string>

/**
 * Alert type for notifications
 */
export type AlertType = 'info' | 'success' | 'error' | 'warning'
