import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'
import { homedir } from 'node:os'
import { randomUUID } from 'node:crypto'
import { realpathSync } from 'node:fs'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path'

export const REXLIT_BIN = Bun.env.REXLIT_BIN ?? 'rexlit'
export const PORT = Number(Bun.env.PORT ?? 3000)
export const REXLIT_HOME = resolve(
  Bun.env.REXLIT_HOME ?? join(homedir(), '.local', 'share', 'rexlit')
)
const REXLIT_HOME_REALPATH = resolveRealPathAllowMissing(REXLIT_HOME)

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

export const ROOT_PREFIX = `${REXLIT_HOME_REALPATH}${sep}`

function resolveRealPathAllowMissing(target: string): string {
  try {
    return realpathSync(target)
  } catch (error) {
    const err = error as NodeJS.ErrnoException
    if (err.code === 'ENOENT') {
      const parent = dirname(target)
      if (!parent || parent === target) {
        return resolve(target)
      }
      const resolvedParent = resolveRealPathAllowMissing(parent)
      return resolve(resolvedParent, basename(target))
    }
    throw error
  }
}

export function ensureWithinRoot(filePath: string) {
  if (!filePath) {
    throw new Error('Path traversal detected')
  }
  const absolute = resolve(filePath)
  const resolved = resolveRealPathAllowMissing(absolute)
  const relativePath = relative(REXLIT_HOME_REALPATH, resolved)
  if (
    relativePath === '' ||
    (!relativePath.startsWith('..') && !isAbsolute(relativePath))
  ) {
    return resolved
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

function parsePolicyStage(value: string | number | undefined): number {
  const stageNumber = Number(value)
  if (!Number.isInteger(stageNumber) || stageNumber < 1 || stageNumber > 3) {
    throw new Error('stage must be 1, 2, or 3')
  }
  return stageNumber
}

function handlePolicyError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  const normalized = message.toLowerCase()

  if (normalized.includes('stage must be')) {
    return jsonError(message, 400)
  }
  if (normalized.includes('text is required')) {
    return jsonError(message, 400)
  }
  if (normalized.includes('policy template is empty')) {
    return jsonError(message, 400)
  }
  if (normalized.includes('path traversal detected')) {
    return jsonError(message, 400)
  }
  if (normalized.includes('document not found') || normalized.includes('policy template missing')) {
    return jsonError(message, 404)
  }
  if (normalized.includes('timed out')) {
    return jsonError(message, 504)
  }
  return jsonError(message, 500)
}

export async function resolveDocumentPath(body: PrivilegeRequestBody) {
  if (typeof body?.hash === 'string' && body.hash.trim()) {
    const metadata = (await runRexlit([
      'index',
      'get',
      body.hash.trim(),
      '--json'
    ])) as { path?: unknown }
    const path = metadata?.path
    if (typeof path !== 'string' || !path) {
      throw new Error('Document not found')
    }
    return ensureWithinRoot(path)
  }

  if (body?.hash && typeof body.hash !== 'string') {
    throw new Error('hash must be provided as a string')
  }

  const inputPath = typeof body?.path === 'string' ? body.path.trim() : ''
  if (!inputPath) {
    throw new Error('Either hash or path is required')
  }

  const normalized = isAbsolute(inputPath)
    ? resolve(inputPath)
    : resolve(REXLIT_HOME, inputPath)

  return ensureWithinRoot(normalized)
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

function sanitizePatternMatch(entry: unknown): PatternMatch | null {
  if (!entry || typeof entry !== 'object') {
    return null
  }
  const candidate = entry as Record<string, unknown>
  const sanitized: PatternMatch = {}
  let hasField = false

  if (typeof candidate.rule === 'string' && candidate.rule.trim()) {
    sanitized.rule = candidate.rule
    hasField = true
  }
  if (
    typeof candidate.confidence === 'number' &&
    Number.isFinite(candidate.confidence)
  ) {
    sanitized.confidence = candidate.confidence
    hasField = true
  }
  if (candidate.stage === null || typeof candidate.stage === 'string') {
    sanitized.stage = candidate.stage ?? null
    hasField = true
  }
  if (candidate.snippet === null) {
    sanitized.snippet = null
    hasField = true
  } else if (
    typeof candidate.snippet === 'string' &&
    !/[\\/]/.test(candidate.snippet)
  ) {
    sanitized.snippet = candidate.snippet
    hasField = true
  }

  return hasField ? sanitized : null
}

function sanitizePatternMatches(value: unknown): PatternMatch[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((entry) => sanitizePatternMatch(entry))
    .filter((entry): entry is PatternMatch => Boolean(entry))
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
    .get('/api/policy', async () => {
      try {
        return await runRexlit(['privilege', 'policy', 'list', '--json'])
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        return jsonError(message, 500)
      }
    })
    .get('/api/policy/:stage', async ({ params }) => {
      try {
        const stage = parsePolicyStage(params.stage)
        return await runRexlit([
          'privilege',
          'policy',
          'show',
          '--stage',
          stage.toString(),
          '--json'
        ])
      } catch (error) {
        return handlePolicyError(error)
      }
    })
    .put('/api/policy/:stage', async ({ params, body }) => {
      try {
        const stage = parsePolicyStage(params.stage)
        const text = typeof body?.text === 'string' ? body.text : ''
        if (!text.trim()) {
          return jsonError('text is required', 400)
        }

        const tempDir = join(REXLIT_HOME, 'tmp', 'policy')
        await mkdir(tempDir, { recursive: true })
        const tempPath = join(
          tempDir,
          `stage${stage}-${randomUUID()}.txt`
        )
        await writeFile(tempPath, text, { encoding: 'utf-8' })

        try {
          return await runRexlit([
            'privilege',
            'policy',
            'apply',
            '--stage',
            stage.toString(),
            '--file',
            tempPath,
            '--json'
          ])
        } finally {
          await rm(tempPath, { force: true })
        }
      } catch (error) {
        return handlePolicyError(error)
      }
    })
    .post('/api/policy/:stage/validate', async ({ params }) => {
      try {
        const stage = parsePolicyStage(params.stage)
        return await runRexlit([
          'privilege',
          'policy',
          'validate',
          '--stage',
          stage.toString(),
          '--json'
        ])
      } catch (error) {
        return handlePolicyError(error)
      }
    })
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
    .get('/api/documents/:hash/file', async ({ params }) => {
      try {
        const metadata = (await runRexlit([
          'index',
          'get',
          params.hash,
          '--json'
        ])) as { path?: unknown }

        if (!metadata || typeof metadata.path !== 'string') {
          return new Response(JSON.stringify({ error: 'Document not found' }), {
            status: 404
          })
        }

        const trustedPath = ensureWithinRoot(metadata.path)
        const file = Bun.file(trustedPath)

        if (!(await file.exists())) {
          return new Response(JSON.stringify({ error: 'File not found on disk' }), {
            status: 404
          })
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
        const patternMatches = sanitizePatternMatches(
          decision?.pattern_matches
        )

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
        const patternMatches = sanitizePatternMatches(
          decision?.pattern_matches
        )

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
