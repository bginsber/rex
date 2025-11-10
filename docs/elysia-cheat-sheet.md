# Elysia ↔ RexLit Bridge Patterns

**Purpose:** Document efficient patterns for wrapping RexLit CLI with Elysia HTTP API.

**Philosophy:** CLI is source of truth. Elysia is stateless connective tissue.

---

## Core Pattern: CLI Subprocess Calls

```typescript
import { Elysia } from 'elysia'

const app = new Elysia()

// Pattern 1: Simple JSON passthrough
app.post('/api/search', async ({ body }) => {
  const { query, limit = 10 } = body

  const proc = Bun.spawn([
    'rexlit', 'index', 'search',
    query,
    '--limit', String(limit),
    '--json'
  ])

  return await new Response(proc.stdout).json()
})

// Pattern 2: Streaming results (future)
app.get('/api/search/stream', async ({ query }) => {
  const proc = Bun.spawn(['rexlit', 'index', 'search', query.q, '--json'])

  return new Response(proc.stdout, {
    headers: { 'Content-Type': 'application/x-ndjson' }
  })
})
```

---

## Document Access Pattern

```typescript
// Pattern 3: Serve document files
app.get('/api/documents/:hash', async ({ params, query }) => {
  // Get document metadata from index via CLI
  const metaProc = Bun.spawn([
    'rexlit', 'index', 'get',
    params.hash,
    '--json'
  ])

  const meta = await new Response(metaProc.stdout).json()

  // Security: Validate path is within allowed root
  const allowedRoot = Bun.env.REXLIT_HOME || '~/.local/share/rexlit'
  if (!meta.file_path.startsWith(allowedRoot)) {
    throw new Error('Path traversal attempt')
  }

  // Serve file directly (Bun handles MIME types)
  return Bun.file(meta.file_path)
})
```

---

## Audit Trail Pattern

```typescript
// Pattern 4: Audit decisions (append to ledger)
app.post('/api/reviews/:docId', async ({ params, body, headers }) => {
  const { decision, notes } = body
  const reviewerId = headers['x-user-id'] // from JWT

  // Write audit entry via CLI
  const proc = Bun.spawn([
    'rexlit', 'audit', 'log',
    '--operation', 'PRIVILEGE_DECISION',
    '--details', JSON.stringify({
      doc_id: params.docId,
      decision,
      reviewer: reviewerId,
      notes,
      interface: 'web'
    })
  ])

  await proc.exited

  if (proc.exitCode !== 0) {
    throw new Error('Audit log failed')
  }

  return { success: true }
})
```

---

## Shared Filesystem Pattern

```typescript
// Pattern 5: Read metadata cache directly
import { readFile } from 'fs/promises'

app.get('/api/index/stats', async () => {
  const cachePath = '~/.local/share/rexlit/index/.metadata_cache.json'
  const cache = JSON.parse(await readFile(cachePath, 'utf-8'))

  return {
    custodians: cache.custodians,
    doctypes: cache.doctypes,
    doc_count: cache.doc_count,
    last_updated: cache.last_updated
  }
})
```

**Why this works:**
- RexLit CLI writes cache
- Elysia reads same file
- No database sync needed
- O(1) performance

---

## Error Handling Pattern

```typescript
// Pattern 6: Structured error handling
async function callRexlit(args: string[]): Promise<any> {
  const proc = Bun.spawn(['rexlit', ...args])

  const stdout = await new Response(proc.stdout).text()
  const stderr = await new Response(proc.stderr).text()

  await proc.exited

  if (proc.exitCode !== 0) {
    throw new Error(`RexLit error (exit ${proc.exitCode}): ${stderr}`)
  }

  return args.includes('--json') ? JSON.parse(stdout) : stdout
}
```

---

## Authentication Pattern

```typescript
import { jwt } from '@elysiajs/jwt'

const app = new Elysia()
  .use(jwt({
    name: 'jwt',
    secret: Bun.env.JWT_SECRET!
  }))
  .derive(async ({ jwt, headers }) => {
    const token = headers.authorization?.split(' ')[1]
    if (!token) throw new Error('Unauthorized')

    const payload = await jwt.verify(token)
    if (!payload) throw new Error('Invalid token')

    return { user: payload }
  })

app.post('/api/search', async ({ body, user }) => {
  // user.id is available, logged in audit trail
  const result = await callRexlit([
    'index', 'search', body.query, '--json'
  ])

  // Audit access
  await callRexlit([
    'audit', 'log',
    '--operation', 'SEARCH_QUERY',
    '--details', JSON.stringify({
      query: body.query,
      user_id: user.id,
      interface: 'web'
    })
  ])

  return result
})
```

---

## Why This Architecture is Elegant

1. **Zero coupling**: API doesn't import RexLit Python code
2. **CLI as contract**: Any CLI command can become an endpoint
3. **Audit trail automatic**: CLI logs everything
4. **Determinism preserved**: Same CLI → same results
5. **Offline-first respected**: API is optional layer
6. **No import linter violations**: Separate codebase
7. **Testable**: Mock subprocess calls

---

## Performance Characteristics

**Subprocess overhead:**
- Bun spawn: ~2-5ms
- Python startup: ~30-50ms (cached after first call)
- Total API latency: ~50-100ms

**Acceptable because:**
- Legal review is human-paced (seconds, not milliseconds)
- Document retrieval is I/O bound (disk read dominates)
- Simplicity > micro-optimizations

**If optimization needed later:**
- Keep-alive Python process (FastAPI sidecar)
- Direct filesystem reads for hot paths
- But start simple

---

## Directory Structure

```
rex/
├── rexlit/           # Python core (unchanged)
├── api/              # Elysia API
│   ├── index.ts      # Main Elysia app (~100 lines)
│   ├── auth.ts       # JWT middleware
│   └── package.json
├── ui/               # React app
│   ├── src/
│   └── package.json
└── docs/
    └── elysia-cheat-sheet.md  # This file
```

---

## MVP Implementation (2 hours)

```typescript
// api/index.ts - The entire API
import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'

const app = new Elysia()
  .use(cors())

  // Search endpoint
  .post('/api/search', async ({ body }) => {
    const proc = Bun.spawn([
      'rexlit', 'index', 'search', body.query, '--json'
    ])
    return await new Response(proc.stdout).json()
  })

  // Get document
  .get('/api/documents/:hash', async ({ params }) => {
    const proc = Bun.spawn([
      'rexlit', 'index', 'get', params.hash, '--json'
    ])
    const meta = await new Response(proc.stdout).json()
    return Bun.file(meta.file_path)
  })

  // Record decision
  .post('/api/reviews/:id', async ({ params, body }) => {
    await Bun.spawn([
      'rexlit', 'audit', 'log',
      '--operation', 'PRIVILEGE_DECISION',
      '--details', JSON.stringify({
        doc_id: params.id,
        decision: body.decision
      })
    ]).exited

    return { success: true }
  })

  .listen(3000)

console.log('RexLit API running on http://localhost:3000')
```

**That's it. 35 lines. Full API.**

---

## What NOT to Do

❌ Don't import RexLit Python code into Elysia (language boundary)
❌ Don't create database cache of index (filesystem is the cache)
❌ Don't reimplement search logic in TypeScript (CLI does this)
❌ Don't build complex state management (stateless API)
❌ Don't add WebSockets v1 (HTTP long-polling sufficient)

---

## Testing Pattern

```typescript
import { describe, test, expect } from 'bun:test'

describe('RexLit API', () => {
  test('search returns results', async () => {
    const response = await fetch('http://localhost:3000/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'privileged' })
    })

    const results = await response.json()
    expect(results.hits).toBeArray()
  })
})
```

---

## Deployment Pattern

```bash
# Development
cd api && bun run dev

# Production (systemd service)
[Unit]
Description=RexLit API
After=network.target

[Service]
Type=simple
User=rexlit
WorkingDirectory=/opt/rexlit/api
ExecStart=/usr/local/bin/bun run index.ts
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Next Steps

1. Create `api/index.ts` with 3 endpoints (35 lines)
2. Create React UI with search + viewer (1 page)
3. Test: Can review 10 docs via UI?
4. If yes: Add auth, polish UX
5. If no: Re-evaluate

**Estimated time to working prototype: 4 hours**

---

**Last Updated:** 2025-11-08
