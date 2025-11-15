# RexLit Web UI Implementation Guide

**Status:** Ready for Implementation
**Architecture:** Elysia (API) + React (UI) + RexLit CLI (Backend)
**Estimated Time:** 4-6 hours for working MVP
**Last Updated:** 2025-11-08

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [API Implementation](#api-implementation)
4. [UI Implementation](#ui-implementation)
5. [Testing Guide](#testing-guide)
6. [Deployment](#deployment)
7. [Next Steps](#next-steps)

---

## Architecture Overview

### The Elegant Solution

```
┌─────────────┐
│  React UI   │ (Browser)
│  Port: 5173 │
└──────┬──────┘
       │ HTTP
       ↓
┌─────────────┐
│ Elysia API  │ (Bun Runtime)
│  Port: 3000 │
└──────┬──────┘
       │ subprocess
       ↓
┌─────────────┐
│ RexLit CLI  │ (Python)
│   (--json)  │
└──────┬──────┘
       │ reads/writes
       ↓
┌──────────────────────────┐
│ Shared Filesystem        │
│ ~/.local/share/rexlit/   │
│  ├── index/              │
│  ├── audit.jsonl         │
│  └── documents/          │
└──────────────────────────┘
```

### Key Principles

1. **CLI is Source of Truth**: All logic stays in Python
2. **Stateless API**: Elysia has zero state, pure passthrough
3. **Filesystem as Database**: No PostgreSQL, no cache sync
4. **Audit Automatic**: CLI logs everything
5. **Zero Python Changes**: Web UI is additive only

---

## Prerequisites

### System Requirements

```bash
# Verify installations
bun --version        # 1.0.0+
node --version       # 18+
python3.11 --version # 3.11+
rexlit --version     # Should show RexLit version

# Install Bun (if needed)
curl -fsSL https://bun.sh/install | bash
```

### RexLit Setup

```bash
# Ensure RexLit is installed and configured
cd /home/user/rex
source .venv/bin/activate
pip install -e '.[dev]'
# or: uv sync --extra dev

# Test CLI JSON output
rexlit index search "test" --json
# Should output valid JSON
```

---

## API Implementation

### Directory Structure

```
rex/
├── api/
│   ├── index.ts          # Main API (35 lines)
│   ├── auth.ts           # JWT middleware (week 2)
│   ├── types.ts          # TypeScript types
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
├── rexlit/               # Existing Python code (unchanged)
└── docs/
    └── elysia-cheat-sheet.md
```

### Step 1: Initialize API Project

```bash
cd /home/user/rex
mkdir -p api
cd api

# Initialize Bun project
bun init -y

# Install dependencies
bun add elysia @elysiajs/cors

# Optional for week 2
# bun add @elysiajs/jwt
```

### Step 2: Create Main API (`api/index.ts`)

```typescript
import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'

const REXLIT_HOME = process.env.REXLIT_HOME || `${process.env.HOME}/.local/share/rexlit`

/**
 * Helper: Execute RexLit CLI command and return result
 */
async function rexlit(args: string[]): Promise<any> {
  const proc = Bun.spawn(['rexlit', ...args], {
    env: { ...process.env, REXLIT_HOME },
    stderr: 'pipe',
    stdout: 'pipe'
  })

  const stdout = await new Response(proc.stdout).text()
  const stderr = await new Response(proc.stderr).text()

  await proc.exited

  if (proc.exitCode !== 0) {
    console.error('RexLit error:', stderr)
    throw new Error(`RexLit CLI failed (exit ${proc.exitCode}): ${stderr}`)
  }

  return args.includes('--json') ? JSON.parse(stdout) : stdout
}

const app = new Elysia()
  .use(cors())

  // Health check
  .get('/api/health', () => ({ status: 'ok', service: 'rexlit-api' }))

  // Search documents
  .post('/api/search', async ({ body }: { body: any }) => {
    const { query, limit = 10 } = body

    return await rexlit([
      'index', 'search',
      query,
      '--limit', String(limit),
      '--json'
    ])
  })

  // Get document metadata
  .get('/api/documents/:hash', async ({ params }: { params: any }) => {
    return await rexlit([
      'index', 'get',
      params.hash,
      '--json'
    ])
  })

  // Serve document file
  .get('/api/documents/:hash/file', async ({ params }: { params: any }) => {
    const meta = await rexlit(['index', 'get', params.hash, '--json'])

    // Security: Validate path is within REXLIT_HOME
    if (!meta.file_path.startsWith(REXLIT_HOME)) {
      throw new Error('Invalid file path')
    }

    const file = Bun.file(meta.file_path)
    if (!await file.exists()) {
      throw new Error('File not found')
    }

    return file
  })

  // Record privilege decision
  .post('/api/reviews/:docId', async ({ params, body }: { params: any, body: any }) => {
    const { decision, notes = '' } = body

    await rexlit([
      'audit', 'log',
      '--operation', 'PRIVILEGE_DECISION',
      '--details', JSON.stringify({
        doc_id: params.docId,
        decision,
        notes,
        interface: 'web',
        timestamp: new Date().toISOString()
      })
    ])

    return { success: true }
  })

  // Get index statistics
  .get('/api/stats', async () => {
    const cachePath = `${REXLIT_HOME}/index/.metadata_cache.json`
    const file = Bun.file(cachePath)

    if (!await file.exists()) {
      return { error: 'Index not built yet' }
    }

    return await file.json()
  })

  // Error handling
  .onError(({ error, set }) => {
    console.error('API Error:', error)
    set.status = 500
    return {
      error: error.message,
      timestamp: new Date().toISOString()
    }
  })

  .listen(3000)

console.log('🚀 RexLit API running on http://localhost:3000')
console.log(`📁 REXLIT_HOME: ${REXLIT_HOME}`)
```

### Step 3: Create TypeScript Types (`api/types.ts`)

```typescript
export interface SearchRequest {
  query: string
  limit?: number
}

export interface SearchResult {
  hits: Array<{
    doc_id: string
    score: number
    path: string
    snippet: string
  }>
  total: number
  query: string
}

export interface DocumentMetadata {
  doc_id: string
  sha256: string
  file_path: string
  size_bytes: number
  custodian?: string
  doctype?: string
  modified: string
}

export interface ReviewDecision {
  decision: 'privileged' | 'not_privileged' | 'skip'
  notes?: string
}

export interface IndexStats {
  custodians: string[]
  doctypes: string[]
  doc_count: number
  last_updated: string
}
```

### Step 4: Configure TypeScript (`api/tsconfig.json`)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "types": ["bun-types"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["**/*.ts"],
  "exclude": ["node_modules"]
}
```

### Step 5: Add Development Scripts (`api/package.json`)

```json
{
  "name": "rexlit-api",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "bun --watch index.ts",
    "start": "bun index.ts",
    "test": "bun test"
  },
  "dependencies": {
    "@elysiajs/cors": "^1.0.0",
    "elysia": "^1.0.0"
  },
  "devDependencies": {
    "bun-types": "latest"
  }
}
```

### Step 6: Test API

```bash
# Terminal 1: Start API
cd /home/user/rex/api
bun run dev

# Terminal 2: Test endpoints
# Health check
curl http://localhost:3000/api/health

# Search
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "privileged", "limit": 5}'

# Get stats
curl http://localhost:3000/api/stats

# Record decision
curl -X POST http://localhost:3000/api/reviews/abc123 \
  -H "Content-Type: application/json" \
  -d '{"decision": "privileged", "notes": "Attorney-client communication"}'

# Privilege policy metadata
curl http://localhost:3000/api/policy

# Stage detail (text + metadata)
curl http://localhost:3000/api/policy/1

# Save updated policy text
curl -X PUT http://localhost:3000/api/policy/1 \
  -H "Content-Type: application/json" \
  -d @policy-stage1.json

# Validate structure
curl -X POST http://localhost:3000/api/policy/1/validate
```

---

## UI Implementation

### Directory Structure

```
rex/
├── ui/
│   ├── src/
│   │   ├── App.tsx           # Main app component
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── ResultsList.tsx
│   │   │   └── DocumentViewer.tsx
│   │   ├── api/
│   │   │   └── rexlit.ts     # API client
│   │   └── types.ts
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
```

### Step 1: Initialize React Project

```bash
cd /home/user/rex
bun create vite ui --template react-ts
cd ui
bun install
```

### Step 2: Create API Client (`ui/src/api/rexlit.ts`)

```typescript
const API_BASE = 'http://localhost:3000/api'

export interface SearchParams {
  query: string
  limit?: number
}

export interface SearchResult {
  hits: Array<{
    doc_id: string
    score: number
    path: string
    snippet: string
  }>
  total: number
}

export interface DocumentMetadata {
  doc_id: string
  file_path: string
  custodian?: string
  doctype?: string
}

export const rexlitApi = {
  async search(params: SearchParams): Promise<SearchResult> {
    const response = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    })

    if (!response.ok) throw new Error('Search failed')
    return response.json()
  },

  async getDocument(hash: string): Promise<DocumentMetadata> {
    const response = await fetch(`${API_BASE}/documents/${hash}`)
    if (!response.ok) throw new Error('Document not found')
    return response.json()
  },

  getDocumentFileUrl(hash: string): string {
    return `${API_BASE}/documents/${hash}/file`
  },

  async recordDecision(docId: string, decision: string, notes?: string) {
    const response = await fetch(`${API_BASE}/reviews/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, notes })
    })

    if (!response.ok) throw new Error('Failed to record decision')
    return response.json()
  }
}
```

### Step 3: Main App Component (`ui/src/App.tsx`)

```typescript
import { useState } from 'react'
import { rexlitApi } from './api/rexlit'
import './App.css'

interface SearchHit {
  doc_id: string
  score: number
  path: string
  snippet: string
}

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchHit[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    try {
      const data = await rexlitApi.search({ query, limit: 20 })
      setResults(data.hits)
    } catch (error) {
      console.error('Search failed:', error)
      alert('Search failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDecision = async (decision: string) => {
    if (!selectedDoc) return

    try {
      await rexlitApi.recordDecision(selectedDoc, decision)
      alert(`Decision recorded: ${decision}`)

      // Move to next document
      const currentIndex = results.findIndex(r => r.doc_id === selectedDoc)
      if (currentIndex < results.length - 1) {
        setSelectedDoc(results[currentIndex + 1].doc_id)
      }
    } catch (error) {
      console.error('Failed to record decision:', error)
      alert('Failed to record decision')
    }
  }

  return (
    <div className="app">
      <header>
        <h1>RexLit Document Review</h1>
      </header>

      <main className="main-content">
        {/* Search Bar */}
        <form onSubmit={handleSearch} className="search-bar">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents (e.g., 'attorney-client privilege')"
            className="search-input"
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        <div className="content-grid">
          {/* Results List */}
          <aside className="results-panel">
            <h2>Results ({results.length})</h2>
            <ul className="results-list">
              {results.map((hit) => (
                <li
                  key={hit.doc_id}
                  className={selectedDoc === hit.doc_id ? 'active' : ''}
                  onClick={() => setSelectedDoc(hit.doc_id)}
                >
                  <div className="result-path">{hit.path}</div>
                  <div className="result-snippet">{hit.snippet}</div>
                  <div className="result-score">Score: {hit.score.toFixed(2)}</div>
                </li>
              ))}
            </ul>
          </aside>

          {/* Document Viewer */}
          <section className="viewer-panel">
            {selectedDoc ? (
              <>
                <div className="document-viewer">
                  <iframe
                    src={rexlitApi.getDocumentFileUrl(selectedDoc)}
                    title="Document Viewer"
                    className="document-frame"
                  />
                </div>

                <div className="decision-buttons">
                  <button
                    onClick={() => handleDecision('privileged')}
                    className="btn-privileged"
                  >
                    ✓ Privileged
                  </button>
                  <button
                    onClick={() => handleDecision('not_privileged')}
                    className="btn-not-privileged"
                  >
                    ✗ Not Privileged
                  </button>
                  <button
                    onClick={() => handleDecision('skip')}
                    className="btn-skip"
                  >
                    → Skip
                  </button>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <p>Search for documents or select a result to view</p>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}

export default App
```

#### Privilege Policy Panel (2025-11 Update)

- **API layer:** `/api/policy` (list), `/api/policy/:stage` (GET/PUT), and `/api/policy/:stage/validate` proxy the CLI `rexlit privilege policy ...` commands with `--json`. Temporary files are written under `${REXLIT_HOME}/tmp/policy/` and removed after each request.
- **Client helpers:** `ui/src/api/rexlit.ts` adds `listPolicies`, `getPolicy`, `updatePolicy`, and `validatePolicy`, returning typed metadata (`stage`, `source`, `sha256`, `modified_at`, etc.).
- **React UI:** `ui/src/App.tsx` now renders a “Privilege Policies” panel with stage selector, metadata chips, textarea editor, diff preview, validation status, and audited save button. Overrides are written to `~/.config/rexlit/policies/privilege_stage{N}.txt`, keeping CLI and UI in lockstep.
- **Auditability:** Every update logs `privilege.policy.update` with sanitized CLI arguments so ledger verification surfaces unauthorized edits.

### Step 4: Basic Styling (`ui/src/App.css`)

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f5f5;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

header {
  background: #1a1a1a;
  color: white;
  padding: 1rem 2rem;
}

.main-content {
  flex: 1;
  padding: 2rem;
}

.search-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
}

.search-input {
  flex: 1;
  padding: 0.75rem;
  font-size: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.search-bar button {
  padding: 0.75rem 2rem;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.search-bar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.content-grid {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 2rem;
  height: calc(100vh - 200px);
}

.results-panel {
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  overflow: hidden;
}

.results-panel h2 {
  padding: 1rem;
  background: #f5f5f5;
  border-bottom: 1px solid #ddd;
  font-size: 1rem;
}

.results-list {
  list-style: none;
  overflow-y: auto;
  height: calc(100% - 60px);
}

.results-list li {
  padding: 1rem;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background 0.2s;
}

.results-list li:hover {
  background: #f9f9f9;
}

.results-list li.active {
  background: #e3f2fd;
  border-left: 3px solid #0066cc;
}

.result-path {
  font-weight: 500;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.result-snippet {
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.5rem;
}

.result-score {
  font-size: 0.75rem;
  color: #999;
}

.viewer-panel {
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  display: flex;
  flex-direction: column;
}

.document-viewer {
  flex: 1;
  padding: 1rem;
  overflow: hidden;
}

.document-frame {
  width: 100%;
  height: 100%;
  border: none;
}

.decision-buttons {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  border-top: 1px solid #ddd;
  background: #f5f5f5;
}

.decision-buttons button {
  flex: 1;
  padding: 1rem;
  font-size: 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-privileged {
  background: #4caf50;
  color: white;
}

.btn-privileged:hover {
  background: #45a049;
}

.btn-not-privileged {
  background: #f44336;
  color: white;
}

.btn-not-privileged:hover {
  background: #da190b;
}

.btn-skip {
  background: #9e9e9e;
  color: white;
}

.btn-skip:hover {
  background: #757575;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  font-size: 1.1rem;
}
```

### Step 5: Run UI Development Server

```bash
cd /home/user/rex/ui
bun run dev
# Opens http://localhost:5173
```

---

## Testing Guide

### Manual Testing Checklist

```bash
# 1. Verify API is running
curl http://localhost:3000/api/health

# 2. Test search endpoint
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "contract", "limit": 5}'

# 3. Test document retrieval (use real doc_id from search)
curl http://localhost:3000/api/documents/abc123

# 4. Test decision recording
curl -X POST http://localhost:3000/api/reviews/abc123 \
  -H "Content-Type: application/json" \
  -d '{"decision": "privileged", "notes": "Test"}'

# 5. Verify audit log
rexlit audit verify
# Should show PRIVILEGE_DECISION entries

# 6. Exercise privilege policy endpoints
curl http://localhost:3000/api/policy
curl http://localhost:3000/api/policy/1
curl -X PUT http://localhost:3000/api/policy/1 \
  -H "Content-Type: application/json" \
  -d '{"text": "# Updated policy\\n..."}'
curl -X POST http://localhost:3000/api/policy/1/validate

# 7. Test UI workflow
# - Open http://localhost:5173
# - Search for "attorney"
# - Click result
# - View document
# - Click "Privileged" button
# - Verify decision recorded
# - Scroll to the "Privilege Policies" panel
# - Edit stage 1 text, open the diff preview, click Validate, then Save
# - Confirm `rexlit privilege policy list --json` reflects the update
```

### Automated Tests

```bash
# API regression tests (policy endpoints, search, security)
bun test api/index.test.ts

# CLI privilege policy coverage
pytest tests/test_cli_privilege_policy.py

# Optional: ensure the React build still succeeds
cd ui && bun run build
```

---

## Deployment

### Development Setup

```bash
# Terminal 1: API
cd /home/user/rex/api
bun run dev

# Terminal 2: UI
cd /home/user/rex/ui
bun run dev

# Terminal 3: RexLit operations
rexlit audit verify
```

### Production Deployment (Systemd)

**API Service** (`/etc/systemd/system/rexlit-api.service`):

```ini
[Unit]
Description=RexLit API Server
After=network.target

[Service]
Type=simple
User=rexlit
WorkingDirectory=/opt/rexlit/api
Environment="REXLIT_HOME=/var/lib/rexlit"
ExecStart=/usr/local/bin/bun run index.ts
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**UI Build**:

```bash
cd /home/user/rex/ui
bun run build
# Deploy dist/ to nginx/apache
```

**Nginx Configuration**:

```nginx
server {
    listen 80;
    server_name rexlit.example.com;

    # UI
    location / {
        root /var/www/rexlit-ui;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## Next Steps

### Week 1 Completion Criteria

- [ ] API running and responding to all endpoints
- [ ] UI can search documents
- [ ] UI can view documents (PDF/text)
- [ ] UI can record privilege decisions
- [ ] Decisions appear in `audit.jsonl` when verified with CLI
- [ ] Can review 10 documents faster than CLI workflow

### Week 2 Enhancements (If Week 1 Succeeds)

1. **Authentication**
   - Add JWT middleware
   - User login/logout
   - Role-based access (reviewer/admin)

2. **UX Improvements**
   - Keyboard shortcuts (j/k for next/prev)
   - Bulk decision exports
   - Search history
   - Filters by custodian/doctype

3. **Performance**
   - PDF.js for better PDF rendering
   - Search result caching
   - Pagination for large result sets

4. **Monitoring**
   - API latency logging
   - Error tracking
   - Usage analytics

### Future Considerations

- Collaborative review (assign docs to reviewers)
- Real-time updates (WebSockets or SSE)
- Mobile-responsive design
- Advanced search (date range, size filters)

---

## Troubleshooting

### API won't start

```bash
# Check Bun installation
bun --version

# Check port availability
lsof -i :3000

# Check RexLit CLI
rexlit --version
which rexlit
```

### Search returns empty results

```bash
# Verify index exists
ls -la ~/.local/share/rexlit/index/

# Rebuild index if needed
rexlit index build ./sample-docs --index-dir ~/.local/share/rexlit/index
```

### Document file won't load

- Check CORS headers in API
- Verify file path in metadata
- Check file permissions
- Test direct file access: `curl http://localhost:3000/api/documents/{hash}/file`

### Decisions not appearing in audit log

```bash
# Check audit log exists
cat ~/.local/share/rexlit/audit.jsonl

# Verify CLI audit command works
rexlit audit log --operation TEST --details '{"test":true}'

# Check API logs for errors
```

---

## Resources

- [Elysia Documentation](https://elysiajs.com)
- [Bun Documentation](https://bun.sh/docs)
- [React Documentation](https://react.dev)
- [RexLit CLI Guide](/home/user/rex/CLI-GUIDE.md)
- [Architecture Doc](/home/user/rex/ARCHITECTURE.md)
- [Elysia Cheat Sheet](/home/user/rex/docs/elysia-cheat-sheet.md)

---

**Ready to implement!** Follow this guide step-by-step for a working MVP in 4-6 hours.
