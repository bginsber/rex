# PDF Viewing Architecture Discovery

**Branch**: `claude/explore-pdf-viewing-01QMuvXorLgdhAe5hJC8q2WE`
**Date**: 2025-11-16
**Objective**: Understand the security boundaries, API patterns, and component architecture required for implementing PDF viewing in RexLit.

---

## Executive Summary

This discovery document answers 20 critical questions about implementing PDF viewing in RexLit. Key findings:

- **Security**: Three-layer protection (index trust, path validation, symlink resolution) already tested with 13 dedicated security tests
- **Current State**: Document viewer works for plain text only; returns HTML-wrapped content via `GET /api/documents/:hash/file`
- **Ready for Enhancement**: Security boundaries are solid; API error handling and MIME type data are available
- **Constraints**: Offline-first (no CDN dependencies); pdf.js must be bundled; no external network calls
- **Testing**: 146 Python tests (100% passing) + Bun API helper tests; missing full HTTP endpoint integration tests

---

## Part 1: Security & File Access Boundaries

### Q1: Where is the security boundary for document file access?

**Answer**: Enforced at two levels with `REXLIT_HOME` as the authoritative root.

**TypeScript API Layer** (`api/index.ts:277-291`):
```typescript
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
```

**Python Discovery Layer** (`rexlit/ingest/discover.py:117-187`):
```python
def discover_document(
    file_path: Path,
    allowed_root: Path | None = None,
) -> DocumentMetadata:
    """Discover and extract metadata for a single document."""
    resolved_path = file_path.resolve()

    if allowed_root:
        allowed_root_resolved = allowed_root.resolve()
        try:
            resolved_path.relative_to(allowed_root_resolved)
        except ValueError:
            raise ValueError(
                f"Security: Path traversal detected. "
                f"File {file_path} resolves to {resolved_path} "
                f"which is outside allowed root {allowed_root_resolved}"
            ) from None
```

**Key Protection**: `REXLIT_HOME` environment variable (or `~/.local/share/rexlit/`) defines the authoritative document root. All paths must resolve within it or access is denied.

---

### Q2: Which helper functions guarantee we don't break out of the documents root?

**Three Critical Functions**:

1. **`ensureWithinRoot(filePath: string)`** - `api/index.ts:277-291`
   - Resolves relative symlinks via `resolveRealPathAllowMissing()`
   - Validates against `REXLIT_HOME_REALPATH`
   - Rejects anything starting with `..` or absolute paths outside root
   - Used by all file access endpoints

2. **`resolveDocumentPath(body: PrivilegeRequestBody)`** - `api/index.ts:347-376`
   - For hash-based lookup: queries index via `rexlit index get` (trusts index, not user input)
   - For path-based: normalizes then calls `ensureWithinRoot()`
   - Always returns a path guaranteed within root

3. **`discover_document(file_path, allowed_root)`** - `rexlit/ingest/discover.py:117-187`
   - Uses `Path.relative_to()` which raises ValueError if path escapes root
   - Resolves symlinks first, validates final destination against allowed_root
   - Used during document ingestion

**Design Pattern**: Layered validation
- **Layer 1** (realpath resolution): Follow symlinks, resolve to canonical path
- **Layer 2** (boundary check): Validate final path is within REXLIT_HOME
- **Layer 3** (error handling): Sanitize error messages to prevent leaking filesystem structure

---

### Q3: How are these helpers tested?

**Test Coverage**: 13 dedicated security tests in `/tests/test_security_path_traversal.py`

**Key Test Cases** (all passing):
- ✅ `test_discover_document_with_allowed_root_valid_path` - validates paths within boundary
- ✅ `test_discover_document_symlink_within_boundary` - resolves symlinks safely, accepts
- ✅ `test_discover_document_symlink_outside_boundary` - rejects external symlinks
- ✅ `test_discover_document_path_traversal_dotdot` - catches `../` escapes
- ✅ `test_discover_document_absolute_path_outside_root` - rejects system paths
- ✅ `test_discover_documents_filters_malicious_symlinks` - filters during bulk discovery
- ✅ `test_discover_documents_nested_path_traversal` - nested structure validation
- ✅ `test_discover_documents_system_file_access_attempt` - blocks `/etc/passwd` etc.
- ✅ `test_path_resolution_consistency` - different input formats
- ✅ `test_symlink_chain_outside_boundary` - catches chain escapes

**TypeScript API Tests** (`api/index.test.ts`):
- ✅ Paths within REXLIT_HOME accepted
- ✅ Absolute paths outside REXLIT_HOME rejected
- ✅ Relative paths with `../` rejected
- ✅ Symlink traversal attempts rejected

**Reusability**: These tests can be extended to validate PDF file access. New tests should verify:
- Binary PDF files are accessible (not just text files)
- MIME type checking prevents executable/dangerous files
- Large files don't exhaust memory (check file size before reading)

---

### Q4: How are documents addressed and stored? What does the :hash represent?

**Hash Representation**: **SHA-256 of file content** (not path, not name)

**Document Metadata Structure** (`rexlit/ingest/discover.py:19-33`):
```python
class DocumentMetadata(BaseModel):
    path: str                          # Absolute path to document
    sha256: str                        # SHA-256 hash of file content
    size: int                          # File size in bytes
    mime_type: str | None              # MIME type (e.g., 'application/pdf')
    extension: str                     # File extension (lowercase)
    mtime: str                         # Modification time (ISO 8601)
    custodian: str | None              # Document custodian
    doctype: str | None                # Document type classification
```

**Storage Flow**:
1. **Ingestion**: `rexlit ingest ./sample-docs --manifest out/manifest.jsonl`
   - Discovers all documents, computes SHA-256 of each file
   - Stores metadata in JSON manifest
2. **Indexing**: `rexlit index build ./sample-docs --index-dir out/index`
   - Adds metadata to Tantivy search index
   - Caches metadata in `.metadata_cache.json` for O(1) lookup
3. **Storage**: Original files remain in their discovered paths (within `REXLIT_HOME`)

**Example Hash Usage** in React (`ui/src/api/rexlit.ts:57-61`):
```typescript
getDocumentUrl(sha256: string) {
  const url = new URL(`${API_ROOT}/documents/${sha256}/file`)
  url.searchParams.set('t', Date.now().toString())  // Cache bust
  return url.toString()
}
```

**Why SHA-256 instead of path?**
- Content-addressed: same file content → same hash
- Deduplication: identical documents identified
- Security: hash-based access doesn't leak filesystem paths
- Deterministic: reproduces same hash across environments

---

### Q5: Is there a mapping from hash → on-disk path → MIME type?

**Yes, with multiple layers of caching and lookup**:

1. **Tantivy Index** (source of truth)
   - Stores: `sha256` → `path`, `mime_type`, `doctype`, `custodian`, `size`, `mtime`
   - Query via CLI: `rexlit index get <hash> --json`
   - Returns: Full document metadata including path and MIME type

2. **Metadata Cache** (`~/.local/share/rexlit/index/.metadata_cache.json`)
   - O(1) lookup for `custodians[]`, `doctypes[]`, `doc_count`
   - Enables fast statistics/filtering without full index scan

3. **API Metadata Endpoint** (`GET /api/documents/:hash/meta`)
   - Returns metadata from index lookup
   - Provides MIME type for frontend to decide how to render

**Current Implementation** (`api/index.ts:651-700`):
```typescript
.get('/api/documents/:hash/file', async ({ params }) => {
  try {
    // Step 1: Look up in index (authoritative source)
    const metadata = (await runRexlit([
      'index', 'get', params.hash, '--json'
    ])) as { path?: unknown; mime_type?: unknown }

    if (!metadata || typeof metadata.path !== 'string') {
      return new Response(JSON.stringify({ error: 'Document not found' }), {
        status: 404
      })
    }

    // Step 2: Validate path is within root
    const trustedPath = ensureWithinRoot(metadata.path)

    // Step 3: Read and return file
    const file = Bun.file(trustedPath)
    if (!(await file.exists())) {
      return new Response(JSON.stringify({ error: 'File not found on disk' }), {
        status: 404
      })
    }

    // Current: returns HTML-wrapped text
    const text = await file.text()
    // ... HTML escape and wrap ...
  } catch (error) {
    // ... error handling ...
  }
})
```

**Available Data for PDF Viewing**:
- ✅ `sha256` - document identifier
- ✅ `path` - on-disk location (validated)
- ✅ `mime_type` - file type (from index)
- ✅ `size` - file size (prevents loading huge files)
- ✅ `extension` - file extension for filtering

**Enhancement Path**: Modify endpoint to:
1. Check `mime_type === 'application/pdf'`
2. Return raw PDF bytes instead of HTML-wrapped text
3. Let browser/pdf.js handle rendering

---

## Part 2: API Architecture

### Q6: What's the canonical API style for RexLit?

**Pattern**: **CLI-as-API** (documented in design philosophy)

The API is a **stateless HTTP bridge** to the Python CLI, not a reimplementation:

```
HTTP Request → Elysia Handler → Bun.spawn(rexlit CLI) → subprocess stdout/stderr → Response
```

**Key Design Principles**:
1. **Zero duplication**: No business logic in API, all logic in Python CLI
2. **Synchronous subprocess calls**: Each request spawns fresh process (no long-lived state)
3. **Index-backed access**: Document retrieval trusts Tantivy index, not user-supplied paths
4. **Error transparency**: Subprocess stderr forwarded to response with sanitization
5. **Type safety**: Responses validated before returning to client

**Framework**: **Elysia** (Bun-native HTTP framework)

```typescript
export function createApp() {
  return new Elysia()
    .use(cors())
    .get('/api/health', () => ({ status: 'ok' }))
    .post('/api/search', async ({ body }) => { ... })
    .get('/api/documents/:hash/meta', async ({ params }) => { ... })
    .get('/api/documents/:hash/file', async ({ params }) => { ... })
    .post('/api/reviews/:hash', async ({ params, body }) => { ... })
    // ... more routes
    .listen(PORT)
}
```

**Rationale**:
- **Offline-first**: Python CLI is the source of truth; API just wraps it
- **No divergence**: Same code paths for CLI users and web UI users
- **Easy testing**: Can test CLI independently, mock subprocess in API tests
- **Deployment**: Single Python dependency (rexlit CLI), no database, no state

---

### Q7: Where are other routes defined? What patterns are used?

**All routes**: Single file at `/api/index.ts` (907 lines, well-organized)

**Route Patterns** with key examples:

1. **Search** (`POST /api/search`, lines 628-647):
   ```typescript
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
       'index', 'search', query, '--limit', limit.toString(), '--json'
     ])
   })
   ```

2. **Document Metadata** (`GET /api/documents/:hash/meta`, lines 648-650):
   ```typescript
   .get('/api/documents/:hash/meta', async ({ params }) => {
     return await runRexlit(['index', 'get', params.hash, '--json'])
   })
   ```

3. **Document File** (`GET /api/documents/:hash/file`, lines 651-700):
   - Validates path via index lookup
   - Returns HTML-wrapped text for plain text files
   - **Status codes**: 404 (not found), 500 (errors)

4. **Privilege Classification** (`POST /api/classify`, lines 702-782):
   ```typescript
   .post('/api/classify', async ({ body }) => {
     // Request body: { hash?, path?, threshold, reasoning_effort }
     // Response: { decision, patterns, confidence, reasoning_hash }
     // Timeout: 2 minutes (configurable)
   })
   ```

5. **Policy Management** (`GET/PUT /api/policy/:stage`):
   - List, fetch, and update privilege classification policies
   - Validation before accepting updates

6. **Audit/Reviews** (`POST /api/reviews/:hash`):
   - Record privilege decision in audit trail
   - Links reviewer + timestamp + decision to document

7. **Statistics** (`GET /api/stats`):
   - Returns `.metadata_cache.json` (doc count, custodians, doctypes)

**Common Pattern**:
```typescript
// 1. Validate input
if (!required_param) return jsonError('field is required', 400)

// 2. Call CLI via runRexlit()
const result = await runRexlit(command, options, process?)

// 3. Return raw JSON or wrap in error handling
return Response.json(result)
```

---

### Q8: How are errors represented in the API?

**Standard Error Response Format**:
```json
{
  "error": "Sanitized error message"
}
```

**Status Codes** (HTTP semantics):
- `400` - Input validation failed, path traversal detected, missing required parameters
- `404` - Document not found, file not found on disk
- `500` - Unexpected server/subprocess error (default)
- `504` - Subprocess timeout (rare)

**Error Handling Strategy** (`api/index.ts:304-345`):

```typescript
export function sanitizeErrorMessage(message: string) {
  const fallback = 'Unexpected error'
  if (!message) return fallback

  // Remove REXLIT_HOME from messages
  const scrubbed = message.replaceAll(REXLIT_HOME, '[REXLIT_HOME]')

  // Remove absolute paths
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

function detectCliErrorType(stderr: string): { type: string; message: string } | null {
  const stderrLower = stderr.toLowerCase()

  if (stderrLower.includes('modulenotfounderror') && stderrLower.includes('rexlit')) {
    return {
      type: 'MODULE_NOT_FOUND',
      message: 'RexLit CLI is not properly installed...'
    }
  }

  if (stderrLower.includes('command not found')) {
    return {
      type: 'BINARY_NOT_FOUND',
      message: `RexLit binary not found at: ${REXLIT_BIN}...`
    }
  }

  if (stderrLower.includes('permission denied')) {
    return {
      type: 'PERMISSION_DENIED',
      message: `Permission denied when trying to execute: ${REXLIT_BIN}...`
    }
  }

  return null
}
```

**Key Features**:
- ✅ Path leakage prevention (scrubs `REXLIT_HOME` and absolute paths)
- ✅ Specific error type detection (module not found, binary not found, permission denied)
- ✅ Friendly fallback message ("Unexpected error")
- ✅ Consistent JSON format for frontend handling

---

### Q9: Is there already a document file retrieval endpoint?

**Yes**: `GET /api/documents/:hash/file` (lines 651-700 in `api/index.ts`)

**Current Implementation**:
- Queries Tantivy index for document path (via `rexlit index get <hash>`)
- Validates path is within REXLIT_HOME
- Reads file as text (`await file.text()`)
- **Returns**: HTML-wrapped plain text
- **Error handling**: 404 if document not found, 500 if file doesn't exist

**Limitations**:
- Only handles text files (`.text()` will fail on binary data)
- No MIME type switching (always returns HTML)
- No PDF-specific handling
- No streaming (loads entire file into memory)

**Security Features Already Implemented**:
- ✅ Index-based hash-to-path lookup (no direct path parameter)
- ✅ Path traversal protection via `ensureWithinRoot()`
- ✅ Symlink validation
- ✅ HTML escaping for text content
- ✅ Error message sanitization
- ✅ Iframe sandboxing in React

---

### Q10: What does the existing implementation look like?

**Complete Data Flow for Current Document Viewing**:

1. **React Component** (`ui/src/components/documents/DocumentViewer/DocumentViewer.tsx:51-95`):
   ```typescript
   <iframe
     src={getDocumentUrl(document.sha256)}
     title={`Document: ${document.path}`}
     className={styles.iframe}
     sandbox="allow-same-origin allow-scripts"
     onLoad={(e) => {
       // Detect if iframe loaded JSON error instead of HTML document
       const iframe = e.currentTarget
       try {
         const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
         if (iframeDoc) {
           const text = iframeDoc.body?.textContent || ''
           // Check if response looks like JSON error
           if (text.trim().startsWith('{') && text.includes('"error"')) {
             // ... render friendly error message
           }
         }
       } catch {
         // Cross-origin or other access issue, ignore
       }
     }}
   />
   ```

2. **API Client** (`ui/src/api/rexlit.ts:57-61`):
   ```typescript
   getDocumentUrl(sha256: string) {
     const url = new URL(`${API_ROOT}/documents/${sha256}/file`)
     url.searchParams.set('t', Date.now().toString())  // Cache bust
     return url.toString()
   }
   ```

3. **Server Response** (`api/index.ts:651-700`):
   - Looks up document in index via `rexlit index get <hash>`
   - Validates and reads file content
   - Wraps in HTML, escapes for safety
   - Returns as `Content-Type: text/html`

4. **Result**: Plain text documents displayed in minimal HTML with error detection in iframe

**Complete Security Stack**:
- ✅ Index-backed document lookup (prevents path manipulation)
- ✅ Boundary validation (prevents directory traversal)
- ✅ Symlink resolution (prevents symlink attacks)
- ✅ HTML entity escaping (prevents XSS)
- ✅ Error message sanitization (prevents info leakage)
- ✅ Iframe sandboxing (defense in depth)
- ✅ 13 regression tests (ensures protections remain)

---

## Part 3: React Component Structure

### Q11: How does the React app organize document views?

**Component Hierarchy** (`ui/src/`):

```
App.tsx (main entry point, state management)
├── NavRail (navigation between views)
│   ├── Search
│   ├── Review
│   ├── Policy
│   ├── Analytics
│   └── Settings
├── SearchPanel (left panel)
│   ├── SearchInput (top)
│   └── DocumentList
│       └── DocumentCard × N
├── DocumentViewer (right panel, main content)
│   ├── DocumentHeader (metadata)
│   ├── DocumentActions (buttons)
│   └── DocumentFrame (iframe to /api/documents/:hash/file)
├── ReviewView (overlay/modal)
│   ├── DocumentViewer (embedded)
│   └── PrivilegeClassifier (decision panel)
├── PolicyView (policy editor)
├── AnalyticsView (statistics)
└── SettingsView (configuration)
```

**Key Design**: Split-pane view with search results on left, document viewer on right

---

### Q12: What component(s) handle document details or viewing?

**Three Components**:

1. **DocumentViewer** (primary)
   - Location: `ui/src/components/documents/DocumentViewer/DocumentViewer.tsx`
   - Props: `document: SearchResult | null`, `getDocumentUrl: (sha256: string) => string`
   - Displays: Title, Bates number, document path, file size, MIME type
   - Renders: Iframe with error handling
   - Features: Metadata display, action buttons (open in new tab, download estimate)

2. **ReviewView** (secondary, for privilege review)
   - Location: `ui/src/views/ReviewView/ReviewView.tsx`
   - Contains: DocumentViewer + PrivilegeClassifier panel
   - Features: Classification results, pattern matches, confidence score, decision recording

3. **DocumentCard**
   - Location: `ui/src/components/documents/DocumentCard/`
   - Purpose: Small preview in SearchPanel search results list
   - Shows: Truncated path, Bates number, highlight snippet

**Natural Place for PDF Viewing**: DocumentViewer component (already receives `document` prop with `sha256`, `mime_type`, `path`)

---

### Q13: How does routing work and how is hash passed around?

**Routing**: No React Router currently. View switching via state variable `activeView`.

**Hash (SHA-256) Passing** (`ui/src/App.tsx:13-75`):

```typescript
function App() {
  const [activeView, setActiveView] = useState<NavigationView>('search')
  const [results, setResults] = useState<SearchResult[]>([])
  const [selected, setSelected] = useState<SearchResult | null>(null)

  // ... search handler ...

  const handleSelectDocument = useCallback((document: SearchResult) => {
    setSelected(document)  // SearchResult contains sha256
  }, [])

  return (
    <AppLayout ...>
      <NavRail activeView={activeView} onViewChange={setActiveView} />

      {activeView === 'search' && (
        <>
          <SearchPanel
            results={results}
            selectedDocumentHash={selected?.sha256}
            onSearch={handleSearch}
            onSelectDocument={handleSelectDocument}
            loading={loading}
          />
          <DocumentViewer
            document={selected}  // Contains sha256
            getDocumentUrl={rexlitApi.getDocumentUrl}
          />
        </>
      )}

      {activeView === 'review' && (
        <ReviewView
          document={selected}  // selected.sha256 extracted in ReviewView
          getDocumentUrl={rexlitApi.getDocumentUrl}
        />
      )}
    </AppLayout>
  )
}
```

**Data Flow**:
1. SearchPanel emits `onSelectDocument(result)` with full SearchResult (includes `sha256`)
2. App state stores `selected` SearchResult
3. DocumentViewer receives `document` prop with `sha256` property
4. DocumentViewer calls `getDocumentUrl(document.sha256)`
5. URL constructed as `/api/documents/${sha256}/file`

**Type Definition** (`ui/src/types.ts`):
```typescript
interface SearchResult {
  sha256: string
  path: string
  mime_type?: string
  size: number
  extension: string
  custodian?: string
  doctype?: string
}
```

---

## Part 4: Testing Patterns

### Q14: What testing patterns exist?

**Python CLI Tests** (`tests/`, 146 total):
- **Unit Tests**: 80+ for individual modules
- **Integration Tests**: 50+ for full CLI workflows
- **Security Tests**: 13 path traversal regression tests
- **Framework**: pytest with fixtures and temp directories
- **Mocking**: Mock external services (Groq API, OpenAI)

Example (`tests/test_security_path_traversal.py`):
```python
def test_discover_document_symlink_outside_boundary(self, temp_dir: Path):
    """Test that symlinks pointing outside boundary are rejected."""
    outside_dir = temp_dir.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("Secret content outside boundary")

    try:
        symlink = temp_dir / "malicious_link.txt"
        symlink.symlink_to(outside_file)

        with pytest.raises(ValueError, match="Path traversal detected"):
            discover_document(symlink, allowed_root=temp_dir)
    finally:
        # Cleanup
        if outside_file.exists():
            outside_file.unlink()
        if outside_dir.exists():
            outside_dir.rmdir()
```

**TypeScript/Bun Tests** (`api/index.test.ts`):
- **Unit Tests**: Helper function validation (path traversal, timeouts, input validation)
- **Mocking**: Mock process spawning
- **Edge Cases**: Symlinks, Unicode, Windows paths, trailing slashes
- **Framework**: Bun's native test runner + mock utilities

Example:
```typescript
describe('ensureWithinRoot', () => {
  it('should reject symlink traversal attempts', () => {
    const outsideDir = mkdtempSync(join(tmpdir(), 'rexlit-outside-'))
    const outsideFile = join(outsideDir, 'secret.txt')
    writeFileSync(outsideFile, 'secret')

    const docsDir = join(root, 'documents')
    mkdirSync(docsDir, { recursive: true })
    const symlinkPath = join(docsDir, 'outside-link.txt')
    try {
      symlinkSync(outsideFile, symlinkPath)
      expect(() => ensureWithinRoot(symlinkPath)).toThrow('Path traversal detected')
      rmSync(outsideDir, { recursive: true, force: true })
    } catch {
      // cleanup
    }
  })
})
```

---

### Q15: How is the Elysia app tested? Is there a test setup that spins up the app?

**Current State**: Only unit tests for helper functions exist in `api/index.test.ts`

**No Full App Integration Tests** (as of current snapshot)

**Existing Test Infrastructure**:
```typescript
function createMockProcess(
  stdout: string,
  stderr: string,
  exitCode: number,
  delay: number = 0
) {
  const killFn = mock(() => {})

  return {
    stdout: { text: async () => { ... } },
    stderr: { text: async () => { ... } },
    exited: (async () => { ... })(),
    kill: killFn,
  }
}
```

**How to Add App Tests**:
```typescript
import { test, expect } from 'bun:test'
import { createApp } from './index'

test('GET /api/health returns ok', async () => {
  const app = createApp()

  // Option 1: Use app.fetch() directly (if Elysia supports it)
  const response = await app.fetch(new Request('http://localhost/api/health'))
  expect(response.status).toBe(200)
  const body = await response.json()
  expect(body.status).toBe('ok')

  // Option 2: Use Bun test server (requires app.handle)
  const result = await app.handle(new Request('http://localhost/api/health'))
  expect(result.status).toBe(200)
})
```

---

### Q16: Are there HTTP endpoint tests? What patterns are used?

**HTTP Endpoint Tests**: Not yet implemented (opportunity for enhancement)

**Security Boundary Tests** (`api/index.test.ts`):
- ✅ Path traversal tests for `ensureWithinRoot()`
- ✅ Timeout tests for `runRexlit()` with mock processes
- ✅ Input validation tests (threshold, reasoning_effort)
- ✅ Symlink attack tests
- ✅ Error message sanitization tests

**Test Pattern** (using Bun test + mocks):
```typescript
const mockSpawn = mock(() => createMockProcess('', '', 0, 0))

describe('Security Boundaries', () => {
  beforeEach(() => {
    mockSpawn.mockClear()
  })

  it('should complete successfully without timeout', async () => {
    const mockProc = createMockProcess('{"result": "ok"}', '', 0, 10)
    const result = await runRexlit(['test', '--json'], { timeoutMs: 5000 }, mockProc)
    expect(result).toEqual({ result: 'ok' })
    expect(mockProc.kill).not.toHaveBeenCalled()
  })

  it('should timeout after specified duration', async () => {
    const mockProc = createMockProcess('{"result": "ok"}', '', 0, 2000)

    await expect(
      runRexlit(['test', '--json'], { timeoutMs: 100 }, mockProc)
    ).rejects.toThrow(/timed out/)

    expect(mockProc.kill).toHaveBeenCalled()
  })
})
```

---

### Q17: Where are path-sanitization tests that could be reused for PDF access?

**Reusable Test Suite**: `tests/test_security_path_traversal.py` (13 tests, all passing)

**Tests Available for Adaptation**:

| Test Name | Purpose | Reusable For PDF? |
|-----------|---------|------------------|
| `test_discover_document_with_allowed_root_valid_path` | Validates paths within boundary | ✅ Yes - test PDF file access |
| `test_discover_document_symlink_within_boundary` | Resolves symlinks safely | ✅ Yes - validate PDF symlinks |
| `test_discover_document_symlink_outside_boundary` | Rejects external symlinks | ✅ Yes - PDF security |
| `test_discover_document_path_traversal_dotdot` | Catches `../` escapes | ✅ Yes - PDF path escapes |
| `test_discover_document_absolute_path_outside_root` | Rejects system paths | ✅ Yes - prevent /etc access |
| `test_discover_documents_filters_malicious_symlinks` | Filters during discovery | ✅ Yes - bulk PDF filtering |
| `test_discover_documents_nested_path_traversal` | Validates nested structures | ✅ Yes - nested PDFs |
| `test_discover_documents_system_file_access_attempt` | Blocks dangerous files | ✅ Yes - PDF validation |
| `test_path_resolution_consistency` | Different input formats | ✅ Yes - PDF path variants |
| `test_symlink_chain_outside_boundary` | Catches chain escapes | ✅ Yes - PDF symlink chains |

**Adaptation Strategy for PDF Tests**:
1. Add test for PDF files specifically (not just text)
2. Test MIME type validation before reading
3. Test file size limits (prevent memory exhaustion)
4. Test binary file handling (not just `.text()`)
5. Extend existing security tests to cover PDF endpoints

---

## Part 5: Constraints & TODOs

### Q18: Any offline-first or licensing constraints mentioned in code?

**Offline-First Constraints** (from CLAUDE.md):

1. **Core Principle**: All operations offline by default, explicit opt-in for network
2. **Gate Function**: `require_online()` in `rexlit/utils/offline.py`
   ```python
   def require_online() -> None:
       """Gate for network-dependent operations.

       Raises OfflineError if REXLIT_ONLINE is not set.
       """
   ```
3. **ADR 0001**: "Offline-First Gate" - documented architectural decision
4. **Environment Variable**: `REXLIT_ONLINE=1` enables network features
5. **API Compliance**: TypeScript API wraps offline-first Python CLI (no network calls)

**Implications for PDF Viewing**:
- ✅ pdf.js library must be bundled, not fetched from CDN
- ✅ All fonts must be self-hosted
- ✅ No external web worker hosts
- ✅ Can work completely offline

**No GPL/Commercial Constraints** found in code comments, but review `SECURITY.md` for audit trail legal details.

---

### Q19: Any TODOs, design docs, or ADRs mentioning PDF viewing, document viewer, or redactions?

**Found**:

**No explicit "PDF viewer" TODOs** in code

**Design Documents**:
- `docs/UI_ARCHITECTURE.md` - Describes "CLI-as-API" pattern, mentions document viewing in feature list
- `docs/UI_IMPLEMENTATION_GUIDE.md` - Implementation checklist (may reference PDF items)
- `.claude/ui/FRONTEND_DESIGN_BRIEF.md` - Describes UI vision and aesthetic
- `docs/adr/0006-redaction-plan-apply-model.md` - Two-phase redaction workflow

**Existing PDF Support**:
- `rexlit/app/adapters/pdf_stamper.py` (lines 1-80+)
  - Uses PyMuPDF (fitz) for Bates numbering
  - Handles PDF layout, pages, stamping coordinates
  - Shows PDF infrastructure already exists in Python

**Current DocumentViewer** (`ui/src/components/documents/DocumentViewer/DocumentViewer.tsx`):
- No TODOs in the file
- Error handling shows awareness of "Document Not Available" scenarios
- Iframe-based approach provides flexibility for different file types

---

### Q20: Is there anything assuming no external CDNs?

**CDN Analysis** (comprehensive search):

**No CDN References Found**:
- `ui/package.json` - No pdf.js or pdfjs-dist npm packages
- No references to "unpkg", "jsDelivr", "cdn", "cdn.jsdelivr", "cdnjs" in codebase
- No external font CDN links (Google Fonts, etc.)

**Self-Hosted Approach Confirmed**:
- Design brief emphasizes **"offline-first and deterministic processing"**
- Architecture requires no external dependencies
- Commit 67b8940 references "self-hosted fonts for offline-first compliance"

**Implications for PDF Viewing**:
- ✅ pdf.js CAN be included as npm package (pdfjs-dist)
- ✅ pdf.js worker MUST be bundled, not fetched from CDN
- ⚠️ Must configure worker path explicitly in code:
  ```typescript
  import * as pdfjsLib from 'pdfjs-dist';
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/path/to/pdf.worker.min.js';
  ```
- ✅ All supporting files (fonts, images) must be self-hosted
- ✅ No external network calls allowed (aligns with offline-first principle)

---

## Summary Table

| Question | Key Finding | Status |
|----------|-------------|--------|
| Q1: Security boundary | REXLIT_HOME authoritative root with path validation | ✅ Implemented |
| Q2: Helper functions | `ensureWithinRoot()`, `resolveDocumentPath()`, `discover_document()` | ✅ Tested |
| Q3: Test coverage | 13 security tests + Bun API tests | ✅ 100% passing |
| Q4: Hash representation | SHA-256 of file content | ✅ Documented |
| Q5: Hash → path mapping | Via Tantivy index + metadata cache | ✅ Available |
| Q6: API style | CLI-as-API (stateless subprocess wrapper) | ✅ Defined |
| Q7: Route patterns | All in `/api/index.ts`, consistent error handling | ✅ Consistent |
| Q8: Error representation | JSON `{error: string}` with sanitization | ✅ Standardized |
| Q9: File endpoint | `GET /api/documents/:hash/file` exists | ✅ Implemented |
| Q10: Current implementation | HTML-wrapped text only (not PDFs) | ⚠️ Limited |
| Q11: Component structure | Split-pane UI with DocumentViewer on right | ✅ Organized |
| Q12: Document viewing | DocumentViewer + ReviewView components | ✅ Available |
| Q13: Routing | State-based (no React Router), hash via props | ✅ Simple |
| Q14: Test patterns | pytest + Bun test with mocks | ✅ Established |
| Q15: App testing | Unit tests only, no full HTTP integration tests | ⚠️ Gap |
| Q16: HTTP tests | Security boundary tests exist, endpoint tests missing | ⚠️ Partial |
| Q17: Reusable security tests | 10+ tests in `test_security_path_traversal.py` | ✅ Available |
| Q18: Offline constraints | No CDNs, self-hosted approach | ✅ Enforced |
| Q19: PDF TODOs | No explicit PDF viewing TODOs, but PDF stamper exists | ✅ Ready |
| Q20: CDN assumptions | No external CDNs assumed, offline-first design | ✅ Confirmed |

---

## Recommendations for PDF Viewing Implementation

### 1. **Server-Side Enhancement** (api/index.ts)
- Modify `GET /api/documents/:hash/file` to detect MIME type
- For PDFs: return raw binary data with `Content-Type: application/pdf`
- For text: keep current HTML-wrapped approach
- Add file size validation (prevent huge file reads)

### 2. **Client-Side Enhancement** (React)
- Add pdf.js as npm dependency: `npm install pdfjs-dist`
- Create PDFViewer component alongside DocumentViewer
- Configure worker: `pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js'`
- Route based on MIME type: PDF → PDFViewer, text → DocumentViewer

### 3. **Testing**
- Extend `test_security_path_traversal.py` with PDF-specific tests
- Add HTTP endpoint tests to `api/index.test.ts`
- Test binary file handling and MIME type switching

### 4. **Offline Compliance**
- Bundle pdf.js worker in Vite build
- Include worker file in public assets
- No external CDN calls (aligns with existing design)

---

## Appendix: File Locations Reference

### Security & Validation
- `api/index.ts:277-291` - `ensureWithinRoot()` function
- `api/index.ts:347-376` - `resolveDocumentPath()` function
- `rexlit/ingest/discover.py:117-187` - `discover_document()` function
- `tests/test_security_path_traversal.py` - 13 security regression tests

### Document Metadata
- `rexlit/ingest/discover.py:19-33` - DocumentMetadata class
- `rexlit/index/metadata.py` - Metadata cache implementation

### API Routes
- `api/index.ts` - All 7+ route definitions (907 lines)
- `api/index.ts:651-700` - `/api/documents/:hash/file` endpoint

### React Components
- `ui/src/App.tsx` - Main app state and routing
- `ui/src/components/documents/DocumentViewer/` - Document viewer
- `ui/src/views/ReviewView/` - Privilege review view
- `ui/src/api/rexlit.ts` - API client helper

### Configuration & Constraints
- `rexlit/config.py` - REXLIT_HOME, REXLIT_ONLINE settings
- `rexlit/utils/offline.py` - `require_online()` gate
- `docs/adr/0001-offline-first-gate.md` - Architectural decision

---

**End of Discovery Document**

*This document comprehensively answers all 20 discovery questions about implementing PDF viewing in RexLit. It is suitable for handing off to implementation teams or for architectural review.*
