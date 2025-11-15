# RexLit Web UI - Quick Start (30 Minutes)

**Goal:** Get a working API + UI in 30 minutes

---

## Prerequisites Check (2 minutes)

```bash
bun --version    # Need 1.0.0+
rexlit --version # Should work
rexlit index search "test" --json  # Should return JSON
```

If RexLit not installed:
```bash
cd /home/user/rex
source .venv/bin/activate
pip install -e '.[dev]'
# or: uv sync --extra dev
```

---

## Part 1: API Setup (10 minutes)

```bash
# 1. Create API directory
cd /home/user/rex
mkdir -p api
cd api

# 2. Initialize
bun init -y
bun add elysia @elysiajs/cors

# 3. Create index.ts
cat > index.ts << 'EOF'
import { Elysia } from 'elysia'
import { cors } from '@elysiajs/cors'

async function rexlit(args: string[]) {
  const proc = Bun.spawn(['rexlit', ...args], {
    stderr: 'pipe',
    stdout: 'pipe'
  })

  const stdout = await new Response(proc.stdout).text()
  const stderr = await new Response(proc.stderr).text()
  await proc.exited

  if (proc.exitCode !== 0) {
    throw new Error(`RexLit failed: ${stderr}`)
  }

  return args.includes('--json') ? JSON.parse(stdout) : stdout
}

new Elysia()
  .use(cors())
  .get('/api/health', () => ({ status: 'ok' }))

  .post('/api/search', async ({ body }: any) => {
    return await rexlit(['index', 'search', body.query, '--limit', '20', '--json'])
  })

  .get('/api/documents/:hash/file', async ({ params }: any) => {
    const meta = await rexlit(['index', 'get', params.hash, '--json'])
    return Bun.file(meta.file_path)
  })

  .post('/api/reviews/:id', async ({ params, body }: any) => {
    await rexlit([
      'audit', 'log',
      '--operation', 'PRIVILEGE_DECISION',
      '--details', JSON.stringify({
        doc_id: params.id,
        decision: body.decision,
        interface: 'web'
      })
    ])
    return { success: true }
  })

  .listen(3000)

console.log('API: http://localhost:3000')
EOF

# 4. Start API
bun run index.ts
```

**Test in new terminal:**
```bash
curl http://localhost:3000/api/health
# Should return: {"status":"ok"}
```

---

## Part 2: UI Setup (15 minutes)

```bash
# 1. Create UI
cd /home/user/rex
bun create vite ui --template react-ts
cd ui
bun install

# 2. Create API client
mkdir -p src/api
cat > src/api/rexlit.ts << 'EOF'
const API = 'http://localhost:3000/api'

export const rexlitApi = {
  async search(query: string) {
    const res = await fetch(`${API}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })
    return res.json()
  },

  getFileUrl(hash: string) {
    return `${API}/documents/${hash}/file`
  },

  async recordDecision(docId: string, decision: string) {
    const res = await fetch(`${API}/reviews/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision })
    })
    return res.json()
  }
}
EOF

# 3. Replace App.tsx
cat > src/App.tsx << 'EOF'
import { useState } from 'react'
import { rexlitApi } from './api/rexlit'
import './App.css'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  const search = async (e: React.FormEvent) => {
    e.preventDefault()
    const data = await rexlitApi.search(query)
    setResults(data.hits || [])
  }

  const decide = async (decision: string) => {
    if (!selected) return
    await rexlitApi.recordDecision(selected, decision)
    alert(`Recorded: ${decision}`)
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h1>RexLit Review</h1>

      <form onSubmit={search} style={{ marginBottom: '2rem' }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search..."
          style={{ width: '400px', padding: '0.5rem', marginRight: '1rem' }}
        />
        <button type="submit">Search</button>
      </form>

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '2rem' }}>
        <div>
          <h3>Results ({results.length})</h3>
          {results.map(hit => (
            <div
              key={hit.doc_id}
              onClick={() => setSelected(hit.doc_id)}
              style={{
                padding: '0.5rem',
                cursor: 'pointer',
                background: selected === hit.doc_id ? '#e3f2fd' : 'white',
                marginBottom: '0.5rem',
                border: '1px solid #ddd'
              }}
            >
              <div style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>{hit.path}</div>
              <div style={{ fontSize: '0.8rem', color: '#666' }}>{hit.snippet}</div>
            </div>
          ))}
        </div>

        <div>
          {selected && (
            <>
              <iframe
                src={rexlitApi.getFileUrl(selected)}
                style={{ width: '100%', height: '500px', border: '1px solid #ddd' }}
              />
              <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                <button onClick={() => decide('privileged')} style={{ flex: 1, padding: '1rem', background: '#4caf50', color: 'white', border: 'none' }}>
                  Privileged
                </button>
                <button onClick={() => decide('not_privileged')} style={{ flex: 1, padding: '1rem', background: '#f44336', color: 'white', border: 'none' }}>
                  Not Privileged
                </button>
                <button onClick={() => decide('skip')} style={{ flex: 1, padding: '1rem', background: '#9e9e9e', color: 'white', border: 'none' }}>
                  Skip
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
EOF

# 4. Start UI
bun run dev
```

**Open browser:** http://localhost:5173

---

## Part 3: Test Full Workflow (3 minutes)

1. **Search**: Type "contract" (or whatever is in your index)
2. **Select**: Click a result
3. **View**: Document should appear in iframe
4. **Decide**: Click "Privileged" button
5. **Verify**: In terminal, run:
   ```bash
   rexlit audit verify
   # Should show PRIVILEGE_DECISION entry
   ```

---

## Success Criteria

✅ API responds to health check
✅ Search returns results
✅ Document renders in UI
✅ Decision recorded in audit log
✅ Faster than CLI + manual file opening

---

## Next Steps

**If this works:**
- Follow [UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md) for production version
- Add authentication, better styling, keyboard shortcuts

**If this doesn't work:**
- Check [UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md) troubleshooting section
- Verify RexLit index exists: `ls ~/.local/share/rexlit/index/`
- Check API logs for errors

---

## File Checklist

After setup, you should have:

```
rex/
├── api/
│   ├── index.ts         ← 50 lines
│   ├── package.json
│   └── node_modules/
├── ui/
│   ├── src/
│   │   ├── App.tsx      ← 80 lines
│   │   └── api/
│   │       └── rexlit.ts ← 20 lines
│   └── package.json
```

**Total code written: ~150 lines**
**Total time: 30 minutes**
**Result: Full working review UI**

---

That's it. You now have a working web UI for RexLit document review. 🚀
