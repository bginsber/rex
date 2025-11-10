import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'
import { homedir } from 'node:os'
import { isAbsolute, join, resolve, sep } from 'node:path'

const REXLIT_BIN = Bun.env.REXLIT_BIN ?? 'rexlit'
const PORT = Number(Bun.env.PORT ?? 3000)
const REXLIT_HOME = resolve(
  Bun.env.REXLIT_HOME ?? join(homedir(), '.local', 'share', 'rexlit')
)

interface RunOptions {
  timeoutMs?: number
}

async function runRexlit(args: string[], options: RunOptions = {}) {
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

const ROOT_PREFIX = `${REXLIT_HOME}${sep}`

function ensureWithinRoot(filePath: string) {
  const absolute = resolve(filePath)
  if (absolute === REXLIT_HOME || absolute.startsWith(ROOT_PREFIX)) {
    return absolute
  }
  throw new Error('Path traversal detected')
}


function jsonError(message: string, status = 500) {
  return new Response(
    JSON.stringify({ error: message }),
    {
      status,
      headers: { 'Content-Type': 'application/json' }
    }
  )
}

async function resolveDocumentPath(body: any) {
  if (body?.hash) {
    const metadata = await runRexlit(['index', 'get', body.hash, '--json'])
    const path = metadata?.path
    if (!path) {
      throw new Error('Document not found')
    }
    return path
  }

  const inputPath = body?.path
  if (!inputPath) {
    throw new Error('Either hash or path is required')
  }

  const candidate = isAbsolute(inputPath)
    ? ensureWithinRoot(inputPath)
    : ensureWithinRoot(resolve(REXLIT_HOME, inputPath))

  return candidate
}

type StageStatus = {
  stage: 'privilege' | 'responsiveness' | 'redaction'
  status: 'completed' | 'skipped' | 'pending'
  mode: 'llm' | 'pattern' | 'disabled'
  reasoning_effort?: string
  needs_review?: boolean
  notes?: string
  redaction_spans?: number
}

function buildStageStatus(decision: any): StageStatus[] {
  const reasoningEffort = typeof decision?.reasoning_effort === 'string'
    ? decision.reasoning_effort
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
    ? decision.labels.some((label: string) =>
        typeof label === 'string' && label.toUpperCase().includes('RESPONSIVE')
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


const app = new Elysia()
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
  .get('/api/documents/:hash/file', async ({ params }) => {
    try {
      // Look up document by hash in index (authoritative source)
      const metadata = await runRexlit(['index', 'get', params.hash, '--json'])

      if (!metadata || !metadata.path) {
        return new Response(JSON.stringify({ error: 'Document not found' }), {
          status: 404
        })
      }

      // Use ONLY the path from the index (ignore any query parameters)
      const trustedPath = metadata.path
      const file = Bun.file(trustedPath)

      if (!(await file.exists())) {
        return new Response(JSON.stringify({ error: 'File not found on disk' }), {
          status: 404
        })
      }

      // For text files, return as HTML wrapped in pre
      const text = await file.text()
      const htmlEscape: Record<string, string> = { '<': '&lt;', '>': '&gt;', '&': '&amp;' }
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
      return new Response(JSON.stringify({ error: String(error) }), {
        status: 500
      })
    }
  })
  .post('/api/privilege/classify', async ({ body }: { body: any }) => {
    try {
      const filePath = await resolveDocumentPath(body ?? {})
      const args = ['privilege', 'classify', filePath, '--json']

      let threshold: number | undefined
      if (body?.threshold !== undefined) {
        const parsed = Number(body.threshold)
        if (!Number.isFinite(parsed)) {
          return jsonError('threshold must be a number between 0.0 and 1.0', 400)
        }
        if (parsed < 0 || parsed > 1) {
          return jsonError('threshold must be a number between 0.0 and 1.0', 400)
        }
        threshold = parsed
        args.push('--threshold', parsed.toString())
      }

      const effortRaw = typeof body?.reasoning_effort === 'string'
        ? body.reasoning_effort.toLowerCase()
        : undefined
      if (effortRaw) {
        const allowed = new Set(['low', 'medium', 'high', 'dynamic'])
        if (!allowed.has(effortRaw)) {
          return jsonError(
            'reasoning_effort must be one of low, medium, high, or dynamic',
            400
          )
        }
        args.push('--reasoning-effort', effortRaw)
      }

      const decision = await runRexlit(args, { timeoutMs: 2 * 60 * 1000 })
      const patternMatches = Array.isArray(decision?.pattern_matches)
        ? decision.pattern_matches
        : []

      return {
        decision,
        stages: buildStageStatus(decision),
        pattern_matches: patternMatches,
        source: {
          hash: typeof body?.hash === 'string' ? body.hash : undefined,
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
  })
  .post('/api/privilege/explain', async ({ body }: { body: any }) => {
    try {
      const filePath = await resolveDocumentPath(body ?? {})
      const decision = await runRexlit(
        ['privilege', 'explain', filePath, '--json'],
        { timeoutMs: 3 * 60 * 1000 }
      )
      const patternMatches = Array.isArray(decision?.pattern_matches)
        ? decision.pattern_matches
        : []

      return {
        decision,
        stages: buildStageStatus(decision),
        pattern_matches: patternMatches,
        source: {
          hash: typeof body?.hash === 'string' ? body.hash : undefined,
          path: filePath
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const normalized = message.toLowerCase()
      if (normalized.includes('either hash or path is required')) {
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
  })
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

app.listen(PORT)

console.log(`RexLit API listening on http://localhost:${PORT}`)
