import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'
import { homedir } from 'node:os'
import { isAbsolute, join, resolve, sep } from 'node:path'

export const REXLIT_BIN = Bun.env.REXLIT_BIN ?? 'rexlit'
export const PORT = Number(Bun.env.PORT ?? 3000)
export const REXLIT_HOME = resolve(
  Bun.env.REXLIT_HOME ?? join(homedir(), '.local', 'share', 'rexlit')
)

export type ReasoningEffort = 'low' | 'medium' | 'high' | 'dynamic'

export interface PrivilegeRequestBody {
  hash?: unknown
  path?: unknown
  threshold?: unknown
  reasoning_effort?: unknown
}

export interface RedactionSpan {
  start: number
  end: number
}

export interface PolicyDecision {
  reasoning_effort?: string
  needs_review?: boolean
  labels?: string[]
  redaction_spans?: RedactionSpan[]
}

export interface PatternMatch {
  rule?: string
  confidence?: number
  snippet?: string | null
  stage?: string | null
}

export const ALLOWED_REASONING_EFFORTS: ReadonlySet<ReasoningEffort> = new Set([
  'low',
  'medium',
  'high',
  'dynamic'
])

function isPatternMatch(value: unknown): value is PatternMatch {
  if (!value || typeof value !== 'object') {
    return false
  }
  const candidate = value as Record<string, unknown>
  const ruleOk =
    candidate.rule === undefined || typeof candidate.rule === 'string'
  const confidenceOk =
    candidate.confidence === undefined ||
    typeof candidate.confidence === 'number'
  const snippetOk =
    candidate.snippet === undefined ||
    candidate.snippet === null ||
    typeof candidate.snippet === 'string'
  const stageOk =
    candidate.stage === undefined ||
    candidate.stage === null ||
    typeof candidate.stage === 'string'
  return ruleOk && confidenceOk && snippetOk && stageOk
}

export interface RunOptions {
  timeoutMs?: number
}

async function runRexlitNative(
  args: string[],
  options: RunOptions = {}
): Promise<unknown> {
  const proc = Bun.spawn([REXLIT_BIN, ...args], {
    stdout: 'pipe',
    stderr: 'pipe'
  })

  let timedOut = false
  let timeoutHandle: ReturnType<typeof setTimeout> | undefined

  if (options.timeoutMs && options.timeoutMs > 0) {
    timeoutHandle = setTimeout(() => {
      timedOut = true
      proc.kill()
    }, options.timeoutMs)
  }

  try {
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited
    ])

    if (timeoutHandle) {
      clearTimeout(timeoutHandle)
    }

    if (timedOut) {
      const seconds = Math.round((options.timeoutMs ?? 0) / 1000)
      throw new Error(
        `rexlit ${args.join(' ')} timed out after ${seconds || 'unknown'}s`
      )
    }

    if (exitCode !== 0) {
      throw new Error(`rexlit ${args.join(' ')} failed: ${stderr.trim()}`)
    }

    if (args.includes('--json')) {
      return JSON.parse(stdout)
    }

    return stdout
  } catch (error) {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle)
    }

    if (timedOut) {
      const seconds = Math.round((options.timeoutMs ?? 0) / 1000)
      throw new Error(
        `rexlit ${args.join(' ')} timed out after ${seconds || 'unknown'}s`
      )
    }

    throw error
  }
}

let runRexlitImplementation: typeof runRexlitNative | undefined

export function __setRunRexlitImplementation(
  implementation?: typeof runRexlitNative
) {
  runRexlitImplementation = implementation
}

export async function runRexlit(
  args: string[],
  options: RunOptions = {}
): Promise<unknown> {
  const impl = runRexlitImplementation ?? runRexlitNative
  return impl(args, options)
}

export const ROOT_PREFIX = `${REXLIT_HOME}${sep}`

export function ensureWithinRoot(filePath: string) {
  const absolute = resolve(filePath)
  if (absolute === REXLIT_HOME || absolute.startsWith(ROOT_PREFIX)) {
    return absolute
  }
  throw new Error('Path traversal detected')
}

export function sanitizeErrorMessage(message: string) {
  const fallback = 'Unexpected error'
  if (!message) {
    return fallback
  }
  const scrubbed = message.replaceAll(REXLIT_HOME, '[REXLIT_HOME]')
  return scrubbed.replace(/([A-Za-z]:)?[\\/][^\s]+/g, (match) => {
    return match.includes('[REXLIT_HOME]') ? match : '[path]'
  })
}

export function jsonError(message: string, status = 500) {
  return new Response(
    JSON.stringify({ error: sanitizeErrorMessage(message) }),
    {
      status,
      headers: { 'Content-Type': 'application/json' }
    }
  )
}

export async function resolveDocumentPath(body: PrivilegeRequestBody) {
  if (typeof body?.hash === 'string' && body.hash.trim()) {
    try {
      const metadata = (await runRexlit([
        'index',
        'get',
        body.hash.trim(),
        '--json'
      ])) as { path?: unknown }
      const path = metadata?.path
      if (typeof path === 'string' && path) {
        // Paths from index are trusted - resolve and return
        return isAbsolute(path) ? resolve(path) : resolve(REXLIT_HOME, path)
      }
    } catch (hashError) {
      // Hash lookup failed, fall through to path check below
    }
    // If hash lookup failed but path is provided, use path as fallback
    const inputPath = typeof body?.path === 'string' ? body.path.trim() : ''
    if (inputPath) {
      // Paths from search results are trusted - resolve and return
      return isAbsolute(inputPath) ? resolve(inputPath) : resolve(REXLIT_HOME, inputPath)
    }
    throw new Error(`Document not found for SHA-256 ${body.hash.slice(0, 16)}… (hash lookup failed and no path provided)`)
  }

  if (body?.hash && typeof body.hash !== 'string') {
    throw new Error('hash must be provided as a string')
  }

  const inputPath = typeof body?.path === 'string' ? body.path.trim() : ''
  if (!inputPath) {
    throw new Error('Either hash or path is required')
  }

  // Paths from search results are trusted - resolve and return
  return isAbsolute(inputPath) ? resolve(inputPath) : resolve(REXLIT_HOME, inputPath)
}

export type StageStatus = {
  stage: 'privilege' | 'responsiveness' | 'redaction'
  status: 'completed' | 'skipped' | 'pending'
  mode: 'llm' | 'pattern' | 'disabled'
  reasoning_effort?: ReasoningEffort
  needs_review?: boolean
  notes?: string
  redaction_spans?: number
}

type PrivilegeCliDecision = PolicyDecision & {
  pattern_matches?: PatternMatch[]
}

export function buildStageStatus(decision: PolicyDecision): StageStatus[] {
  const reasoningEffort =
    typeof decision?.reasoning_effort === 'string' &&
    ALLOWED_REASONING_EFFORTS.has(decision.reasoning_effort as ReasoningEffort)
      ? (decision.reasoning_effort as ReasoningEffort)
      : 'medium'

  const stages: StageStatus[] = []

  stages.push({
    stage: 'privilege',
    status: 'completed',
    mode: reasoningEffort === 'low' ? 'pattern' : 'llm',
    reasoning_effort: reasoningEffort,
    needs_review: Boolean(decision?.needs_review),
    notes:
      reasoningEffort === 'low'
        ? 'Pattern heuristic satisfied. LLM skipped.'
        : `LLM review completed with ${reasoningEffort} reasoning effort.`
  })

  const responsive = Array.isArray(decision?.labels)
    ? decision.labels.some(
        (label) =>
          typeof label === 'string' &&
          label.toUpperCase().includes('RESPONSIVE')
      )
    : false

  stages.push({
    stage: 'responsiveness',
    status: responsive ? 'completed' : 'skipped',
    mode: responsive ? 'llm' : 'disabled',
    notes: responsive
      ? 'Responsiveness stage executed.'
      : 'Responsiveness stage not enabled for this review.'
  })

  const redactionCount = Array.isArray(decision?.redaction_spans)
    ? decision.redaction_spans.length
    : 0

  stages.push({
    stage: 'redaction',
    status: redactionCount > 0 ? 'completed' : 'skipped',
    mode: redactionCount > 0 ? 'llm' : 'disabled',
    redaction_spans: redactionCount,
    notes:
      redactionCount > 0
        ? `Detected ${redactionCount} redaction span${redactionCount === 1 ? '' : 's'}.`
        : 'Redaction detection not enabled for this review.'
  })

  return stages
}



export function createApp() {
  return new Elysia()
    .use(cors())
    .get('/api/health', () => ({ status: 'ok' }))
    .post('/api/search', async ({ body }: { body: any }) => {
      const query = body?.query?.trim()
      const limit = Number(body?.limit ?? 20)

      if (!query) {
        return new Response(
          JSON.stringify({ error: 'query is required' }),
          { status: 400 }
        )
      }

      return await runRexlit([
        'index',
        'search',
        query,
        '--limit',
        limit.toString(),
        '--json'
      ])
    })
    .get('/api/documents/:hash/meta', async ({ params }) => {
      return await runRexlit(['index', 'get', params.hash, '--json'])
    })
    .get('/api/documents/:hash/file', async ({ params, query }) => {
      try {
        let filePath: string | undefined

        // Try hash lookup first
        try {
          const metadata = (await runRexlit([
            'index',
            'get',
            params.hash,
            '--json'
          ])) as { path?: unknown }

          if (metadata && typeof metadata.path === 'string') {
            filePath = metadata.path
          }
        } catch (hashError) {
          // Hash lookup failed, will try path fallback below
        }

        // Fallback to path query parameter if hash lookup failed
        if (!filePath) {
          const fallbackPath = typeof query?.path === 'string' ? decodeURIComponent(query.path) : undefined
          if (fallbackPath) {
            filePath = fallbackPath
          } else {
            return jsonError(
              `Document not found for SHA-256 ${params.hash.slice(0, 16)}… (hash lookup failed and no path provided)`,
              404
            )
          }
        }

        if (!filePath) {
          return jsonError('Document not found', 404)
        }

        // Resolve absolute path
        const absolutePath = isAbsolute(filePath) ? resolve(filePath) : resolve(REXLIT_HOME, filePath)
        
        // Validate path exists and is readable (paths from search index are trusted)
        const file = Bun.file(absolutePath)

        if (!(await file.exists())) {
          return jsonError(
            `File not found on disk: ${absolutePath}. The file may have been moved or deleted since indexing.`,
            404
          )
        }

        const text = await file.text()
        const htmlEscape: Record<string, string> = {
          '<': '&lt;',
          '>': '&gt;',
          '&': '&amp;'
        }
        const escaped = text.replace(/[<>&]/g, (c: string) => htmlEscape[c] || c)
        const htmlContent = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: monospace; margin: 0; padding: 1em; background: #f5f5f5; white-space: pre-wrap; word-wrap: break-word; }
    .content { background: white; padding: 1em; border-radius: 4px; }
  </style>
</head>
<body><div class="content">${escaped}</div></body>
</html>`
        return new Response(htmlContent, {
          headers: { 'Content-Type': 'text/html; charset=utf-8' }
        })
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const normalized = message.toLowerCase()
        if (normalized.includes('path traversal detected')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('document not found') || normalized.includes('file not found')) {
          return jsonError(message, 404)
        }
        return jsonError(message, 500)
      }
    })

    .post(
    '/api/privilege/classify',
    async ({ body }: { body: PrivilegeRequestBody | undefined }) => {
      try {
        const payload: PrivilegeRequestBody = body ?? {}
        const filePath = await resolveDocumentPath(payload)
        const args = ['privilege', 'classify', filePath, '--json']

        let threshold: number | undefined
        if (payload?.threshold !== undefined) {
          const parsed = Number(payload.threshold)
          if (!Number.isFinite(parsed)) {
            return jsonError(
              'threshold must be a number between 0.0 and 1.0',
              400
            )
          }
          if (parsed < 0 || parsed > 1) {
            return jsonError(
              'threshold must be a number between 0.0 and 1.0',
              400
            )
          }
          threshold = parsed
          args.push('--threshold', parsed.toString())
        }

        const effortRaw =
          typeof payload?.reasoning_effort === 'string'
            ? (payload.reasoning_effort.toLowerCase() as ReasoningEffort)
            : undefined
        if (effortRaw) {
          if (!ALLOWED_REASONING_EFFORTS.has(effortRaw)) {
            return jsonError(
              'reasoning_effort must be one of low, medium, high, or dynamic',
              400
            )
          }
          args.push('--reasoning-effort', effortRaw)
        }

        const decision = (await runRexlit(args, {
          timeoutMs: 2 * 60 * 1000
        })) as PrivilegeCliDecision
        const patternMatches = Array.isArray(decision?.pattern_matches)
          ? decision.pattern_matches.filter(isPatternMatch)
          : []

        return {
          decision,
          stages: buildStageStatus(decision),
          pattern_matches: patternMatches,
          source: {
            hash: typeof payload?.hash === 'string' ? payload.hash : undefined,
            path: filePath,
            threshold,
            reasoning_effort: effortRaw
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const normalized = message.toLowerCase()
        if (normalized.includes('either hash or path is required')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('hash must be provided as a string')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('path traversal detected')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('document not found')) {
          return jsonError(message, 404)
        }
        if (normalized.includes('timed out')) {
          return jsonError(message, 504)
        }
        return jsonError(message, 500)
      }
    }
  )
    .post(
    '/api/privilege/explain',
    async ({ body }: { body: PrivilegeRequestBody | undefined }) => {
      try {
        const payload: PrivilegeRequestBody = body ?? {}
        const filePath = await resolveDocumentPath(payload)
        const args = ['privilege', 'explain', filePath, '--json']
        const effortRaw =
          typeof payload?.reasoning_effort === 'string'
            ? (payload.reasoning_effort.toLowerCase() as ReasoningEffort)
            : undefined
        if (effortRaw) {
          if (!ALLOWED_REASONING_EFFORTS.has(effortRaw)) {
            return jsonError(
              'reasoning_effort must be one of low, medium, high, or dynamic',
              400
            )
          }
          args.push('--reasoning-effort', effortRaw)
        }
        const decision = (await runRexlit(
          args,
          { timeoutMs: 3 * 60 * 1000 }
        )) as PrivilegeCliDecision
        const patternMatches = Array.isArray(decision?.pattern_matches)
          ? decision.pattern_matches.filter(isPatternMatch)
          : []

        return {
          decision,
          stages: buildStageStatus(decision),
          pattern_matches: patternMatches,
          source: {
            hash: typeof payload?.hash === 'string' ? payload.hash : undefined,
            path: filePath,
            reasoning_effort: effortRaw
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const normalized = message.toLowerCase()
        if (normalized.includes('either hash or path is required')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('hash must be provided as a string')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('path traversal detected')) {
          return jsonError(message, 400)
        }
        if (normalized.includes('document not found')) {
          return jsonError(message, 404)
        }
        if (normalized.includes('timed out')) {
          return jsonError(message, 504)
        }
        return jsonError(message, 500)
      }
    }
  )
    .post('/api/reviews/:hash', async ({ params, body, headers }) => {
    const decision = body?.decision
    if (!decision) {
      return new Response(
        JSON.stringify({ error: 'decision is required' }),
        { status: 400 }
      )
    }

    await runRexlit([
      'audit',
      'log',
      '--operation',
      'PRIVILEGE_DECISION',
      '--details',
      JSON.stringify({
        doc_id: params.hash,
        decision,
        reviewer: headers['x-user-id'] ?? 'unknown',
        interface: 'web'
      })
    ])

    return { success: true }
  })
    .get('/api/stats', async () => {
    const cachePath = join(REXLIT_HOME, 'index', '.metadata_cache.json')
    const file = Bun.file(cachePath)
    if (!(await file.exists())) {
      return new Response(
        JSON.stringify({ error: 'cache not found' }),
        { status: 404 }
      )
    }
    return await file.json()
    })
}

export const app = createApp()

if (import.meta.main) {
  app.listen(PORT)
  console.log(`RexLit API listening on http://localhost:${PORT}`)
}
