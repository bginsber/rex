/**
 * Policy management types
 */

/**
 * Metadata for a privilege policy stage
 */
export interface PrivilegePolicyMetadata {
  stage: number
  stage_name: string
  path: string
  exists?: boolean
  sha256?: string | null
  size_bytes?: number | null
  modified_at?: string | null
  source?: string
}

/**
 * Full policy detail including content
 */
export interface PrivilegePolicyDetail extends PrivilegePolicyMetadata {
  text: string
}

/**
 * Policy validation result
 */
export interface PrivilegePolicyValidation {
  stage: number
  stage_name: string
  passed: boolean
  errors: string[]
}

/**
 * Policy stage type for UI
 */
export type PolicyStage = 'privilege' | 'responsiveness' | 'redaction'
