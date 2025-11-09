import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'
import { homedir } from 'node:os'
import { isAbsolute, join, resolve, sep } from 'node:path'

const REXLIT_BIN = Bun.env.REXLIT_BIN ?? 'rexlit'
const PORT = Number(Bun.env.PORT ?? 3000)
const REXLIT_HOME = resolve(
  Bun.env.REXLIT_HOME ?? join(homedir(), '.local', 'share', 'rexlit')
)

async function runRexlit(args: string[]) {
  const proc = Bun.spawn([REXLIT_BIN, ...args], {
    stdout: 'pipe',
    stderr: 'pipe'
  })

  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited
  ])

  if (exitCode !== 0) {
    throw new Error(`rexlit ${args.join(' ')} failed: ${stderr.trim()}`)
  }

  if (args.includes('--json')) {
    return JSON.parse(stdout)
  }

  return stdout
}

const ROOT_PREFIX = `${REXLIT_HOME}${sep}`

function ensureWithinRoot(filePath: string) {
  const absolute = resolve(filePath)
  if (absolute === REXLIT_HOME || absolute.startsWith(ROOT_PREFIX)) {
    return absolute
  }
  throw new Error('Path traversal detected')
}

// Validate that a document path is safe to read
function validateDocumentPath(filePath: string): string {
  const absolute = resolve(filePath)
  // Reject paths with suspicious patterns
  if (absolute.includes('..') || !absolute.startsWith('/')) {
    throw new Error('Invalid document path')
  }
  return absolute
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
  .get('/api/documents/:hash/file', async ({ params, query }: { params: any; query: any }) => {
    try {
      // First, try to use a provided path (safer if from search results)
      let pathCandidate = query?.path as string | undefined

      // If no path provided, search for the document
      if (!pathCandidate) {
        const searchResults = await runRexlit(['index', 'search', params.hash, '--limit', '1', '--json'])

        if (!Array.isArray(searchResults) || searchResults.length === 0) {
          return new Response(JSON.stringify({ error: 'Document not found' }), {
            status: 404
          })
        }

        const doc = searchResults[0]
        pathCandidate = doc.path
      }

      if (!pathCandidate) {
        return new Response(JSON.stringify({ error: 'Document path unavailable' }), {
          status: 500
        })
      }

      const originPath = isAbsolute(pathCandidate) ? pathCandidate : join(REXLIT_HOME, pathCandidate)
      const safePath = validateDocumentPath(originPath)

      // Check if file exists
      const file = Bun.file(safePath)
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
